#!/usr/bin/env python3
"""Flask web interface for Melody Generator.

This module provides a minimal web front-end mirroring the command-line and
Tkinter interfaces. Users choose musical parameters through a form and the
server renders a temporary MIDI (and optionally WAV) file for download and
preview.

The latest revision introduces several changes:

* **CSRF protection** – Flask-WTF's :class:`~flask_wtf.csrf.CSRFProtect` now
  injects and validates tokens for every POST request, securing the form
  against cross-site request forgery attacks.
* **WSGI-friendly entry point** – a :func:`create_app` factory builds and
  configures the Flask application so production servers like Gunicorn can
  serve it directly.
* **Request size limiting** – Flask's ``MAX_CONTENT_LENGTH`` bounds the size of
  uploaded form data so oversized payloads are rejected early.
* **Rate limiting** – An in-memory per-IP throttle curbs abusive clients by
  capping requests per minute.
* **Retry guidance** – When the limit is exceeded the ``429`` response now
  carries a ``Retry-After`` header indicating how many seconds remain in the
  current window.
* **Shared chord parsing** – Both the CLI and web interface now rely on
  :func:`melody_generator.utils.parse_chord_progression` so manual and random
  chord options behave identically across entry points.
* **Thread-safe rate limiting** – The throttle now uses a lock for concurrent
  access and purges stale entries each request to bound memory usage.
"""
# This revision introduces validation for the ``base_octave`` input so
# out-of-range values (anything not between ``MIN_OCTAVE`` and
# ``MAX_OCTAVE``) trigger a flash message instead of causing errors when
# generating the melody.
# The original implementation attempted to render the generated MIDI to WAV
# using FluidSynth so that browsers lacking MIDI support could preview the
# melody. This update flashes an informative message when that rendering
# fails because either FluidSynth itself or a compatible SoundFont is missing.
# The play template now displays flash messages so users are aware that the
# preview audio is unavailable.
#
# The current update extends the form with options to enable machine-learning
# based weighting and to choose a predefined style embedding. When the user
# activates these features but required dependencies such as PyTorch are not
# installed, the view now flashes a clear error instead of returning a server
# error.
#
# This revision also ensures Celery tasks receive keyword arguments. The
# ``index`` view now dispatches ``generate_preview_task`` using
# ``delay(**params)`` so that asynchronous workers get the same named
# parameters as the synchronous path.
#
# This update also detects Celery broker connection failures. When a
# ``delay`` call cannot reach the broker a flash message informs the user
# and the preview is generated synchronously so the request still succeeds.
#
# Rhythm generation now honors the requested number of notes. When the
# "Random Rhythm" option is enabled the backend invokes
# ``generate_random_rhythm_pattern`` with ``notes`` so the durations list
# matches the melody length.
#
# The latest revision validates numeric fields such as tempo and motif
# length. ``bpm``, ``notes``, ``motif_length`` and ``harmony_lines`` must all
# be positive integers. If the user submits a value less than or equal to
# zero, the form re-renders with an explanatory flash message so invalid
# input never reaches the melody generation helpers.
#
# This update refines validation and resource management:
#   * ``harmony_lines`` may now be zero so users can preview monophonic
#     melodies. Negative values still trigger a flash message.
#   * The time-signature denominator is restricted to common values
#     (1, 2, 4, 8 or 16) matching the CLI and Tkinter GUIs.
#   * ``_generate_preview`` cleans up temporary MIDI and WAV files even when
#     generation fails so no stale files accumulate under ``/tmp``.
#   * ``load_sequence_model`` caches models by path and vocabulary size to
#     avoid repeatedly loading the same weights from disk during preview.
#   * Flash message for invalid harmony line counts now clarifies that zero is
#     permitted.
#   * Unchecked "Humanize performance" checkbox now correctly disables the
#     feature by treating a missing form field as ``False``.
#   * Asynchronous preview rendering now waits only a bounded time for Celery
#     workers. If no result arrives within the timeout the request falls back
#     to synchronous generation and the timeout is logged for diagnostics.
# To further harden input handling, integer conversions for numeric form fields
# now guard against ``ValueError``. When a user submits non-numeric text, the
# view flashes a clear message and redisplays the form instead of bubbling up
# an exception.
#
# The current revision enforces critical configuration in production
# deployments. The application factory now emits ``CRITICAL`` log messages and
# raises :class:`RuntimeError` when either ``FLASK_SECRET`` or
# ``CELERY_BROKER_URL`` are missing while debug mode is disabled. This prevents
# accidentally running the web interface with insecure default settings.
#
# This update adds two lightweight abuse protections:
#   * ``MAX_CONTENT_LENGTH`` caps the size of incoming requests, guarding
#     against accidental or malicious large uploads.
#   * A simple in-memory rate limiter throttles clients making too many
#     requests per minute to reduce the risk of denial-of-service attacks.

from __future__ import annotations

from importlib import import_module
from tempfile import NamedTemporaryFile
from time import monotonic
from typing import Dict, List, Optional, Tuple

from melody_generator import playback
from melody_generator.playback import MidiPlaybackError
from melody_generator.utils import parse_chord_progression, validate_time_signature

# Celery is an optional dependency. When present we import the main class and
# the ``TimeoutError`` used when a task exceeds its allotted runtime.  Each
# import is guarded so the module gracefully degrades when Celery is missing.
try:
    from celery import Celery
except Exception:  # pragma: no cover - optional dependency
    Celery = None

try:  # pragma: no cover - optional dependency
    from celery.exceptions import TimeoutError as CeleryTimeoutError
except Exception:
    CeleryTimeoutError = TimeoutError

from flask import (
    Flask,
    render_template,
    request,
    flash,
    current_app,
    make_response,
    Response,
)
from flask_wtf.csrf import CSRFProtect
import base64
import logging
import math
import os
import secrets
from threading import Lock

# Import the core melody generation package dynamically so the
# Flask app can live in a separate module without circular imports.
melody_generator = import_module("melody_generator")

# Pull the functions and data structures we need from the loaded module.
# Doing this makes the rest of the code look as if we had imported them
# normally with ``from melody_generator import ...``.
generate_melody = melody_generator.generate_melody
create_midi_file = melody_generator.create_midi_file
SCALE = melody_generator.SCALE
CHORDS = melody_generator.CHORDS
canonical_key = melody_generator.canonical_key
canonical_chord = melody_generator.canonical_chord
generate_random_rhythm_pattern = melody_generator.generate_random_rhythm_pattern
generate_harmony_line = melody_generator.generate_harmony_line
generate_counterpoint_melody = melody_generator.generate_counterpoint_melody
MIN_OCTAVE = melody_generator.MIN_OCTAVE
MAX_OCTAVE = melody_generator.MAX_OCTAVE
load_sequence_model = melody_generator.load_sequence_model
STYLE_VECTORS = melody_generator.style_embeddings.STYLE_VECTORS
get_style_vector = melody_generator.style_embeddings.get_style_vector

INSTRUMENTS = {
    "Piano": 0,
    "Guitar": 24,
    "Bass": 32,
    "Violin": 40,
    "Flute": 73,
}

# Logger used throughout the module for diagnostic messages.
logger = logging.getLogger(__name__)

# CSRF protection instance. ``init_app`` is invoked inside ``create_app`` so
# tests can control when protection is enabled.
csrf = CSRFProtect()

# Optional Celery application used to offload melody rendering so the Flask
# thread remains responsive. The broker defaults to the in-memory backend which
# requires no external services for small deployments.
celery_app = None
if Celery is not None:
    celery_app = Celery(
        __name__, broker=os.environ.get("CELERY_BROKER_URL", "memory://")
    )


# In-memory store tracking request counts per IP address. Each entry maps the
# client IP to a ``(window_start, count)`` tuple representing the beginning of
# the current rate-limit window and the number of requests seen in that window.
# Access to this dictionary is synchronized by ``REQUEST_LOCK`` because Flask's
# development server can process requests on multiple threads.
REQUEST_LOG: Dict[str, Tuple[float, int]] = {}

# Lock guarding ``REQUEST_LOG`` to prevent race conditions when multiple
# requests attempt to read or modify the structure concurrently. Using a lock
# keeps the rate limiter's bookkeeping consistent and avoids crashes from
# unsynchronized dictionary mutations.
REQUEST_LOCK = Lock()

# Duration of a single rate-limit window in seconds. ``monotonic`` timestamps
# ensure the calculation is unaffected by system clock adjustments.
RATE_LIMIT_WINDOW = 60.0


def rate_limit() -> Optional[Response]:
    """Enforce a naive per-IP request limit.

    The function is registered as a ``before_request`` hook and consults the
    application configuration for ``RATE_LIMIT_PER_MINUTE``. When the limit is
    exceeded, a ``429`` response is returned with a ``Retry-After`` header
    indicating how long the client should wait before retrying. Missing or
    invalid configuration disables rate limiting entirely. The log of requests
    is protected by a :class:`threading.Lock` so concurrent threads cannot
    corrupt state, and stale entries are purged before each new request is
    recorded.

    Returns:
        Optional[Response]: ``Response`` object when the limit is exceeded,
        otherwise ``None`` to allow the request to proceed.
    """

    limit_raw = current_app.config.get("RATE_LIMIT_PER_MINUTE")
    if limit_raw is None:
        # Configuration missing – treat as disabled so deployments that do not
        # opt in to throttling behave exactly as before the rate limiter was
        # introduced.
        return None

    try:
        # ``int`` handles ``bool`` and string representations of integers. The
        # conversion occurs before validation so values such as ``"10"`` are
        # accepted while clearly invalid inputs (``"fast"`` or complex objects)
        # trigger the ``ValueError`` path below.
        limit = int(limit_raw)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid RATE_LIMIT_PER_MINUTE %r; disabling rate limiting", limit_raw
        )
        return None

    if limit <= 0:
        # ``0`` is treated as “disabled” while negative values are rejected as
        # invalid. In both cases we fall back to allowing the request through so
        # a misconfiguration never blocks legitimate traffic. Only log when the
        # value is negative to avoid noisy warnings for installations that
        # intentionally set the limit to zero.
        if limit < 0:
            logger.warning(
                "RATE_LIMIT_PER_MINUTE must be positive; disabling rate limiting (received %r)",
                limit_raw,
            )
        return None

    now = monotonic()
    ip_addr = request.remote_addr or "unknown"

    # ``REQUEST_LOG`` is shared across requests, so mutate it only while holding
    # the lock. This prevents race conditions where two threads could
    # simultaneously read and update the counters for the same IP.
    with REQUEST_LOCK:
        # Remove stale entries for all clients. Purging here keeps the data
        # structure small and ensures old counts do not affect new windows.
        expired = [
            ip for ip, (start, _) in REQUEST_LOG.items()
            if now - start >= RATE_LIMIT_WINDOW
        ]
        for ip in expired:
            del REQUEST_LOG[ip]

        window_start, count = REQUEST_LOG.get(ip_addr, (now, 0))

        if now - window_start >= RATE_LIMIT_WINDOW:
            # A new window begins; reset the count for this IP.
            REQUEST_LOG[ip_addr] = (now, 1)
            return None

        if count >= limit:
            # Limit exceeded. Build an explicit ``Response`` so we can supply a
            # ``Retry-After`` header. The remaining time is calculated using
            # ``math.ceil`` to avoid telling the client to retry immediately
            # when fractional seconds remain in the window.
            remaining = math.ceil(
                max(0.0, RATE_LIMIT_WINDOW - (now - window_start))
            )
            response = make_response("Too many requests", 429)
            response.headers["Retry-After"] = str(remaining)
            return response

        # Increment the counter for this IP within the current window.
        REQUEST_LOG[ip_addr] = (window_start, count + 1)

    return None


def _generate_preview(
    key: str,
    bpm: int,
    timesig: tuple[int, int],
    notes: int,
    motif_length: int,
    base_octave: int,
    instrument: str,
    harmony: bool,
    random_rhythm: bool,
    counterpoint: bool,
    harmony_lines: int,
    include_chords: bool,
    chords_same: bool,
    enable_ml: bool,
    style: Optional[str],
    chords: List[str],
    humanize: bool,
    ornaments: bool,
) -> tuple[str, str]:
    """Render a short preview of the requested melody to audio and MIDI.

    The ``random_rhythm`` option now calls ``generate_random_rhythm_pattern``
    with ``notes`` so the resulting duration list matches the melody length.
    Returns a base64 encoded WAV preview and MIDI file.
    """

    seq_model = None
    if enable_ml:
        try:
            seq_model = load_sequence_model(None, len(SCALE[key]))
        except RuntimeError as exc:
            # Propagate dependency errors so the caller can display a message
            raise RuntimeError(str(exc)) from exc

    melody = generate_melody(
        key,
        notes,
        chords,
        motif_length=motif_length,
        base_octave=base_octave,
        sequence_model=seq_model,
        style=style or None,
    )
    # When random rhythmic patterns are requested, generate a list of durations
    # equal in length to ``notes`` so each pitch receives a corresponding value.
    rhythm = generate_random_rhythm_pattern(notes) if random_rhythm else None
    extra: List[List[str]] = []
    for _ in range(max(0, harmony_lines)):
        extra.append(generate_harmony_line(melody))
    if counterpoint:
        extra.append(generate_counterpoint_melody(melody, key))

    tmp = NamedTemporaryFile(suffix=".mid", delete=False)
    wav_tmp = NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp_path = tmp.name
        wav_path = wav_tmp.name
    finally:
        tmp.close()
        wav_tmp.close()

    midi_bytes = b""
    wav_data = None
    try:
        numerator, denominator = timesig
        create_midi_file(
            melody,
            bpm,
            (numerator, denominator),
            tmp_path,
            harmony=harmony,
            pattern=rhythm,
            extra_tracks=extra,
            chord_progression=chords if include_chords else None,
            chords_separate=not chords_same,
            program=INSTRUMENTS.get(instrument, 0),
            humanize=humanize,
            ornaments=ornaments,
        )

        with open(tmp_path, "rb") as fh:
            midi_bytes = fh.read()

        try:
            playback.render_midi_to_wav(tmp_path, wav_path)
        except MidiPlaybackError:
            wav_data = None
        else:
            with open(wav_path, "rb") as fh:
                wav_data = fh.read()
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    audio_encoded = base64.b64encode(wav_data).decode("ascii") if wav_data else ""
    midi_encoded = base64.b64encode(midi_bytes).decode("ascii")
    return audio_encoded, midi_encoded


if celery_app is not None:
    generate_preview_task = celery_app.task(_generate_preview)  # type: ignore


def index():
    """Render the form and handle submissions.

    On ``GET`` the function simply renders the input form so the user can
    specify parameters for the melody generation. When submitted via ``POST``
    a MIDI file is generated in memory and returned to the browser. Invalid
    numeric form values display a flash message and redisplay the form so the
    user can correct the input instead of triggering an exception.

    @returns Response: Rendered template or audio playback page.
    """

    if request.method == 'POST':
        # Extract user selections, applying sensible defaults when
        # values are missing.
        key = request.form.get('key') or 'C'
        try:
            key = canonical_key(key)
        except ValueError:
            flash("Invalid key selected. Please choose a valid key.")
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        # Convert tempo to an integer, flashing an error when non-numeric text
        # is supplied. The surrounding ``try`` guards against ``ValueError``
        # raised by ``int`` when the input cannot be parsed.
        try:
            bpm = int(request.form.get('bpm') or 120)
        except ValueError:
            flash("BPM must be an integer.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        timesig = request.form.get('timesig') or '4/4'

        # Number of notes must parse as an integer so generation knows how many
        # pitches to create. Invalid strings are reported to the user via a
        # flash message.
        try:
            notes = int(request.form.get('notes') or 16)
        except ValueError:
            flash("Number of notes must be an integer.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        # Motif length likewise requires whole numbers; reject malformed input
        # early so no downstream logic sees invalid data.
        try:
            motif_length = int(request.form.get('motif_length') or 4)
        except ValueError:
            flash("Motif length must be an integer.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        # Users may enter a textual ``base_octave`` which would otherwise crash
        # ``int``. Handle the failure gracefully and re-render the form.
        try:
            base_octave = int(request.form.get('base_octave') or 4)
        except ValueError:
            flash("Base octave must be an integer.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        instrument = request.form.get('instrument') or 'Piano'

        # ``harmony_lines`` may legally be zero but must still parse as an
        # integer. Non-numeric input results in a flash message.
        try:
            harmony_lines = int(request.form.get('harmony_lines') or 0)
        except ValueError:
            flash("Harmony lines must be an integer.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        # Basic sanity checks for numeric inputs. Values less than or equal to
        # zero cannot produce a valid melody so the form is redisplayed with an
        # informative message.
        if bpm <= 0:
            flash("BPM must be greater than 0.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        if notes <= 0:
            flash("Number of notes must be greater than 0.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        if motif_length <= 0:
            flash("Motif length must be greater than 0.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        if harmony_lines < 0:
            # Inform the user that negative values are invalid while zero is
            # acceptable so monophonic melodies remain supported.
            flash("Harmony lines must be non-negative.")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        # Validate the selected instrument against the known General MIDI
        # mapping. Unknown values likely mean the form was tampered with.
        if instrument not in INSTRUMENTS:
            flash("Unknown instrument")
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )
        harmony = bool(request.form.get('harmony'))
        random_rhythm = bool(request.form.get('random_rhythm'))
        counterpoint = bool(request.form.get('counterpoint'))
        include_chords = bool(request.form.get('include_chords'))
        chords_same = bool(request.form.get('chords_same'))
        ornaments = bool(request.form.get('ornaments'))
        # Treat a missing checkbox as ``False`` so unchecking actually
        # disables the humanize feature.
        humanize = bool(request.form.get('humanize'))
        enable_ml = bool(request.form.get('enable_ml'))
        style = request.form.get('style') or None

        try:
            # ``parse_chord_progression`` unifies manual entry, checkbox-driven
            # randomisation and fallback behaviour so the web view mirrors the
            # CLI. When the random toggle is enabled we ignore any typed text
            # and rely entirely on the helper to generate a fresh progression.
            chords = parse_chord_progression(
                request.form.get('chords'),
                key=key,
                force_random=bool(request.form.get('random_chords')),
            )
        except ValueError as exc:
            flash(str(exc))
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        try:
            numerator, denominator = validate_time_signature(timesig)
        except ValueError:
            flash(
                "Time signature must be in the form 'numerator/denominator' with numerator > 0 and denominator one of 1, 2, 4, 8 or 16."
            )
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        if motif_length > notes:
            flash("Motif length cannot exceed the number of notes.")
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        if not MIN_OCTAVE <= base_octave <= MAX_OCTAVE:
            flash(
                f"Base octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}."
            )
            return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        if style:
            try:
                get_style_vector(style)
            except KeyError:
                flash(f"Unknown style: {style}")
                return render_template('index.html', scale=sorted(SCALE.keys()), instruments=INSTRUMENTS.keys(), styles=STYLE_VECTORS.keys())

        params = dict(
            key=key,
            bpm=bpm,
            timesig=(numerator, denominator),
            notes=notes,
            motif_length=motif_length,
            base_octave=base_octave,
            instrument=instrument,
            harmony=harmony,
            random_rhythm=random_rhythm,
            counterpoint=counterpoint,
            harmony_lines=harmony_lines,
            include_chords=include_chords,
            chords_same=chords_same,
            humanize=humanize,
            enable_ml=enable_ml,
            style=style,
            chords=chords,
            ornaments=ornaments,
        )

        try:
            if celery_app is not None:
                try:
                    # ``delay`` may raise immediately if the broker cannot be
                    # reached.  Wrapping the call ensures we handle that case
                    # and still generate the preview in-process so the user sees
                    # a result instead of an error page.
                    async_result = generate_preview_task.delay(**params)
                    try:
                        # ``get`` could otherwise block indefinitely if the
                        # worker is unavailable. A short timeout keeps the
                        # request responsive.
                        result = async_result.get(timeout=10)
                    except CeleryTimeoutError as exc:
                        # Log the timeout for debugging and fall back to a
                        # synchronous preview so the user still receives a
                        # response.
                        logger.exception(
                            "Timed out waiting for background worker: %s", exc
                        )
                        flash(
                            "Background worker timed out; generating preview synchronously."
                        )
                        result = _generate_preview(**params)
                except Exception:  # pragma: no cover - triggered via tests
                    flash(
                        "Could not connect to the background worker; generating preview synchronously."
                    )
                    result = _generate_preview(**params)
            else:
                # Execute synchronously when Celery is unavailable.
                result = _generate_preview(**params)
        except RuntimeError as exc:
            flash(str(exc))
            return render_template(
                'index.html',
                scale=sorted(SCALE.keys()),
                instruments=INSTRUMENTS.keys(),
                styles=STYLE_VECTORS.keys(),
            )

        audio_encoded, midi_encoded = result
        if not audio_encoded:
            flash(
                "Preview audio could not be generated because FluidSynth or a soundfont is unavailable."
            )
        return render_template("play.html", audio=audio_encoded, midi=midi_encoded)

    # On a normal GET request simply render the form so the user can
    # enter their parameters.
    return render_template(
        "index.html",
        scale=sorted(SCALE.keys()),
        instruments=INSTRUMENTS.keys(),
        styles=STYLE_VECTORS.keys(),
    )


def create_app() -> Flask:
    """Build and configure the Flask application instance.

    This factory enables running the web interface under a production WSGI
    server such as Gunicorn. It configures the session secret, attaches CSRF
    protection, and registers the routes defined in this module. In production
    (non-debug) mode the factory requires ``FLASK_SECRET`` and
    ``CELERY_BROKER_URL`` to be present. Missing values trigger a
    :class:`RuntimeError` after emitting a ``CRITICAL`` log entry so the
    application never runs with insecure defaults. Additional safeguards limit
    request size via ``MAX_CONTENT_LENGTH`` and optionally throttle clients
    using ``RATE_LIMIT_PER_MINUTE``.

    Returns:
        Flask: Configured application ready for use by a WSGI server.
    Raises:
        RuntimeError: If required environment variables are absent when debug
            mode is disabled.
    """

    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Read security-related environment variables so we can validate their
    # presence and configure optional protections.
    secret = os.environ.get("FLASK_SECRET")
    broker = os.environ.get("CELERY_BROKER_URL")
    try:
        max_mb = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    except ValueError:
        max_mb = 5
        logger.warning("Invalid MAX_UPLOAD_MB value; defaulting to 5 MB.")
    rate_limit_env = os.environ.get("RATE_LIMIT_PER_MINUTE")
    try:
        rate_limit_per_minute = int(rate_limit_env) if rate_limit_env else None
    except ValueError:
        logger.warning(
            "RATE_LIMIT_PER_MINUTE must be an integer. Disabling rate limiting."
        )
        rate_limit_per_minute = None

    if not app.debug:
        # Running without these variables in production would leave sessions
        # unsigned or Celery unable to dispatch tasks. Treat missing values as
        # fatal configuration errors.
        if not secret:
            logger.critical("FLASK_SECRET environment variable must be set in production.")
            raise RuntimeError("Missing FLASK_SECRET")
        if not broker:
            logger.critical("CELERY_BROKER_URL environment variable must be set in production.")
            raise RuntimeError("Missing CELERY_BROKER_URL")

    if not secret:
        secret = secrets.token_urlsafe(32)
        logger.warning(
            "FLASK_SECRET environment variable not set. "
            "Using a randomly generated key; sessions will not persist across restarts."
        )
    app.secret_key = secret
    # Bound the size of incoming requests to protect the server from excessive
    # memory usage. Flask will automatically return HTTP 413 when the limit is
    # exceeded.
    app.config["MAX_CONTENT_LENGTH"] = max_mb * 1024 * 1024
    # Store the optional per-IP request limit for use by the ``rate_limit``
    # hook. A ``None`` value disables the limiter.
    app.config["RATE_LIMIT_PER_MINUTE"] = rate_limit_per_minute

    # Enable CSRF protection so every form submission must include a valid
    # token. ``csrf_token`` is injected into templates via context processor.
    csrf.init_app(app)

    # Register the primary form handler.
    app.add_url_rule("/", view_func=index, methods=["GET", "POST"])

    # Apply the rate limiter to all requests.
    app.before_request(rate_limit)

    @app.errorhandler(413)
    def handle_request_too_large(_err):
        """Return a concise message when the client uploads too much data."""
        return "Request exceeds configured size limit.", 413

    return app


# Instantiate a default application for ad-hoc scripts and tests while still
# exposing ``create_app`` for production WSGI servers.
app = create_app()
