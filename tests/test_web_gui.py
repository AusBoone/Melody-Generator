"""Tests for the Flask based web GUI.

The web interface exposes the same melody generation functionality as the
desktop application. These tests post various form values to the Flask app and
verify that invalid input is rejected and valid input renders correctly. This
suite also asserts that required configuration such as ``FLASK_SECRET`` and
``CELERY_BROKER_URL`` is enforced in production mode. Recent tests further
ensure that oversized requests are rejected based on ``MAX_CONTENT_LENGTH``.
The suite additionally verifies that preview rendering falls back to
synchronous generation when the Celery broker is unreachable."""

import importlib
import os
import sys
import types
from pathlib import Path
import pytest

# Ensure the repository root is on ``sys.path`` so ``melody_generator`` can be
# imported when tests execute from arbitrary locations.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("flask")

# Stub mido and tkinter so the imports succeed
stub_mido = types.ModuleType("mido")


class DummyMessage:
    """Lightweight stand-in capturing the ``time`` and ``velocity`` fields."""

    def __init__(self, _type: str, **kw) -> None:
        self.type = _type
        self.time = kw.get("time", 0)
        self.note = kw.get("note")
        self.velocity = kw.get("velocity")
        self.program = kw.get("program")


class DummyMidiFile:
    """Minimal MidiFile stub with a save method."""

    def __init__(self, *a, **k):
        self.tracks: list = []

    def save(self, _path):
        pass


stub_mido.Message = DummyMessage
stub_mido.MidiFile = DummyMidiFile
stub_mido.MidiTrack = lambda *a, **k: []
stub_mido.MetaMessage = lambda *a, **k: DummyMessage("meta", **k)
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

stub_tk = types.ModuleType("tkinter")
stub_tk.filedialog = types.ModuleType("filedialog")
stub_tk.messagebox = types.ModuleType("messagebox")
stub_tk.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", stub_tk)
sys.modules.setdefault("tkinter.filedialog", stub_tk.filedialog)
sys.modules.setdefault("tkinter.messagebox", stub_tk.messagebox)
sys.modules.setdefault("tkinter.ttk", stub_tk.ttk)

# Provide required configuration so module import and the default ``create_app``
# call succeed during tests. Individual tests override these values as needed.
os.environ.setdefault("FLASK_SECRET", "testing-secret")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")

web_gui = importlib.import_module("melody_generator.web_gui")

app = web_gui.app
# Disable CSRF protection for most tests to focus on form validation logic.
app.config["WTF_CSRF_ENABLED"] = False


def test_csrf_protection_enforced():
    """Form submissions without a CSRF token are rejected with HTTP 400."""
    protected_app = web_gui.create_app()
    client = protected_app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",  # minimal payload; CSRF check occurs before validation
        },
    )
    assert resp.status_code == 400


def test_index_route():
    """Verify that the index page renders successfully."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Generate Melody" in resp.data


def test_invalid_timesig_flash():
    """Submitting an invalid time signature triggers a flash message."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4",  # invalid
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_bpm_preserves_user_input():
    """When BPM parsing fails the form should retain previous values."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C,Am",
            "bpm": "fast",
            "timesig": "4/4",
            "notes": "12",
            "motif_length": "4",
            "base_octave": "4",
            "random_chords": "1",
        },
    )

    # The invalid BPM value should remain in the input element so the user can
    # correct it without retyping other settings. The ``input-error`` class is
    # also expected to highlight the problematic field.
    assert b'value="fast"' in resp.data
    assert b'field-control input-error' in resp.data
    assert b'name="random_chords" value="1" checked' in resp.data


def test_invalid_harmony_lines_marks_field():
    """Invalid harmony line counts are highlighted and preserved."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "12",
            "motif_length": "4",
            "base_octave": "4",
            "harmony_lines": "abc",
        },
    )

    # The user supplied text remains in the control and the element receives
    # the error styling class for visual feedback.
    assert b'Harmony lines must be an integer.' in resp.data
    assert b'value="abc"' in resp.data
    assert b'name="harmony_lines"' in resp.data
    assert b'field-control input-error' in resp.data


def test_invalid_timesig_with_zero_harmony():
    """Invalid time signatures should be validated even when harmony is off."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4",  # invalid
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "harmony_lines": "0",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_numerator_flash():
    """Numerator outside the valid range triggers an error flash."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "0/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_negative_numerator_flash():
    """Negative numerators result in an error flash."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "-3/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_denominator_flash():
    """Denominators outside the common set should trigger a flash."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/5",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_key_flash():
    """Posting an unknown musical key returns an error message."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "InvalidKey",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Invalid key selected" in resp.data


def test_motif_exceeds_notes_flash():
    """Motif lengths longer than the note count flash an error."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "2",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Motif length cannot exceed" in resp.data


def test_invalid_base_octave_flash():
    """Out-of-range ``base_octave`` values return an error flash."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "9",
        },
    )
    assert b"Base octave must be" in resp.data


def test_invalid_chord_flash():
    """Unknown chords in the form post return an error flash."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C,Unknown",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Unknown chord" in resp.data


def test_invalid_instrument_flash():
    """Posting an instrument not in ``INSTRUMENTS`` shows an error."""

    client = app.test_client()

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "instrument": "Banjo",
        },
    )

    assert b"Unknown instrument" in resp.data


def test_non_positive_bpm_flash():
    """Zero or negative tempo should trigger a validation message."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "0",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"BPM must be greater than 0" in resp.data


def test_non_positive_notes_flash():
    """A note count of zero should be rejected with a flash message."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "0",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Number of notes must be greater than 0" in resp.data


def test_non_positive_motif_length_flash():
    """Motif length should be validated as a positive integer."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "0",
            "base_octave": "4",
        },
    )
    assert b"Motif length must be greater than 0" in resp.data


def test_non_integer_bpm_flash():
    """Textual tempo values should return a helpful validation message."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "fast",  # invalid string that cannot be cast to int
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"BPM must be an integer" in resp.data


def test_non_integer_notes_flash():
    """Non-numeric note counts should be rejected with a flash message."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "many",  # invalid
            "motif_length": "4",
            "base_octave": "4",
        },
    )
    assert b"Number of notes must be an integer" in resp.data


def test_non_integer_motif_length_flash():
    """Motif length entered as text should prompt the user to enter a number."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "long",  # invalid
            "base_octave": "4",
        },
    )
    assert b"Motif length must be an integer" in resp.data


def test_non_integer_base_octave_flash():
    """Base octave must be a number; strings trigger a flash message."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "low",  # invalid
        },
    )
    assert b"Base octave must be an integer" in resp.data


def test_non_integer_harmony_lines_flash():
    """Harmony line counts must be numeric to avoid crashes."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "harmony_lines": "two",  # invalid
        },
    )
    assert b"Harmony lines must be an integer" in resp.data


def test_negative_harmony_lines_flash():
    """Negative harmony line counts are rejected."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "harmony_lines": "-1",
        },
    )
    # The form should explicitly allow zero harmony lines but reject negatives.
    assert b"Harmony lines must be non-negative" in resp.data


def test_include_chords_flag(monkeypatch):
    """Setting the ``include_chords`` checkbox should be accepted."""

    # Avoid exercising the full melody generator and MIDI writer which would
    # require complex stubs. Returning minimal placeholders keeps the test
    # focused on form handling.
    monkeypatch.setattr(web_gui, "generate_melody", lambda *a, **k: ["C4"] * 8)
    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "include_chords": "1",
            "chords_same": "1",
        },
    )
    assert resp.status_code == 200


def test_ornament_flag_forwarded(monkeypatch):
    """The ornament checkbox should set the preview's ornament flag."""

    called: dict = {}

    monkeypatch.setattr(web_gui, "generate_melody", lambda *a, **k: ["C4"] * 4)

    def record_create(*args, **kwargs):
        called["ornaments"] = kwargs.get("ornaments")

    monkeypatch.setattr(web_gui, "create_midi_file", record_create)

    client = app.test_client()
    client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "4",
            "motif_length": "2",
            "base_octave": "4",
            "ornaments": "1",
        },
    )

    assert called.get("ornaments") is True


def test_plagal_cadence_forwarded(monkeypatch):
    """Checking the plagal cadence box forwards the option to the engine."""

    captured: dict[str, object] = {}

    def record_melody(*args, **kwargs):
        captured["plagal"] = kwargs.get("plagal_cadence")
        return ["C4"] * 4

    monkeypatch.setattr(web_gui, "generate_melody", record_melody)
    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    client = app.test_client()
    client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "4",
            "motif_length": "2",
            "base_octave": "4",
            "plagal_cadence": "1",
        },
    )

    assert captured.get("plagal") is True


def test_successful_post_returns_audio(monkeypatch):
    """Valid form submissions embed a WAV audio preview."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)
    monkeypatch.setattr(
        web_gui.playback,
        "render_midi_to_wav",
        lambda mid, wav, soundfont=None: Path(wav).write_bytes(b"wav"),
    )

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )
    assert b"audio/wav" in resp.data


def test_summary_section_lists_user_choices(monkeypatch):
    """Successful previews include a human-readable summary of the inputs."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "generate_melody", lambda *a, **k: ["C4"])
    monkeypatch.setattr(web_gui, "generate_harmony_line", lambda melody: melody)
    monkeypatch.setattr(
        web_gui, "generate_counterpoint_melody", lambda melody, _key: melody
    )
    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)
    monkeypatch.setattr(
        web_gui.playback,
        "render_midi_to_wav",
        lambda mid, wav, soundfont=None: Path(wav).write_bytes(b"wav"),
    )
    class DummyModel:
        """Predictable sequence model used to satisfy the ML toggle."""

        def predict_logits(self, history):  # pragma: no cover - trivial stub
            return [0.1, 0.2]

    monkeypatch.setattr(web_gui, "load_sequence_model", lambda *a, **k: DummyModel())

    style_name = sorted(web_gui.STYLE_VECTORS.keys())[0]

    response = client.post(
        "/",
        data={
            "key": "C",
            "chords": "",
            "random_chords": "1",
            "bpm": "140",
            "timesig": "3/4",
            "notes": "4",
            "motif_length": "2",
            "base_octave": "5",
            "instrument": "Guitar",
            "harmony": "1",
            "harmony_lines": "2",
            "counterpoint": "1",
            "include_chords": "1",
            "chords_same": "1",
            "random_rhythm": "1",
            "ornaments": "1",
            "enable_ml": "1",
            "style": style_name,
            "plagal_cadence": "1",
        },
    )

    html = response.get_data(as_text=True)
    # The summary panel should report the user's selections so they can
    # immediately confirm tempo, instrumentation and toggles without revisiting
    # the form.
    assert "Session Summary" in html
    assert "Core Settings" in html
    assert "140 BPM" in html
    assert "3/4" in html
    assert "Instrument" in html and "Guitar" in html
    assert "randomised" in html  # chord progression flagged as randomised
    assert "Machine learning weighting" in html
    assert "Plagal cadence" in html


def test_lowercase_inputs(monkeypatch):
    """Form values in lowercase should still be processed correctly."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)
    monkeypatch.setattr(
        web_gui.playback,
        "render_midi_to_wav",
        lambda mid, wav, soundfont=None: Path(wav).write_bytes(b"wav"),
    )

    resp = client.post(
        "/",
        data={
            "key": "c",
            "chords": "c,am",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
        },
    )

    assert resp.status_code == 200 and b"audio/wav" in resp.data


def test_playback_failure_flash(monkeypatch):
    """Failed audio rendering notifies the user via flash message."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    def raise_error(_mid, _wav, soundfont=None):
        raise web_gui.MidiPlaybackError("no synth")

    monkeypatch.setattr(web_gui.playback, "render_midi_to_wav", raise_error)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    assert resp.status_code == 200
    assert b"Preview audio could not be generated" in resp.data


def test_enable_ml_missing_dependency(monkeypatch):
    """Enabling ML without PyTorch should flash an error message."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    def raise_dep(*_a, **_k):
        raise RuntimeError("PyTorch is required")

    monkeypatch.setattr(web_gui, "load_sequence_model", raise_dep)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "enable_ml": "1",
        },
    )

    assert resp.status_code == 200
    assert b"PyTorch is required" in resp.data



def test_generation_dispatched_to_celery(monkeypatch):
    """When Celery is available ``index`` should send work to a task."""
    celery_mod = types.ModuleType("celery")
    called = {}

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, **kwargs):
            """Capture keyword arguments supplied to ``delay`` for assertion."""
            called["kwargs"] = kwargs

            class Res:
                def get(self, timeout=None):
                    return ("", "")

            return Res()

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            called["task"] = True
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    gui.app.config["WTF_CSRF_ENABLED"] = False
    client = gui.app.test_client()

    monkeypatch.setattr(gui, "_generate_preview", lambda **kw: ("", ""))

    client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    assert called.get("task")
    assert called["kwargs"]["key"] == "C"
    assert called["kwargs"]["bpm"] == 120
    assert called["kwargs"]["notes"] == 1


def test_delay_arguments_match_preview_parameters(monkeypatch):
    """Ensure ``delay`` receives only keyword arguments matching preview params."""

    # Capture all arguments passed to ``delay`` for later inspection.
    called = {}

    celery_mod = types.ModuleType("celery")

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, *args, **kwargs):
            """Record positional and keyword arguments supplied by ``index``."""
            called["args"] = args
            called["kwargs"] = kwargs

            class Res:
                def get(self, timeout=None):
                    return ("", "")

            return Res()

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            called["task"] = True
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    gui.app.config["WTF_CSRF_ENABLED"] = False
    client = gui.app.test_client()

    # Avoid heavy processing during the test by stubbing the actual generator.
    monkeypatch.setattr(gui, "_generate_preview", lambda **kw: ("", ""))

    client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    expected_params = {
        "key": "C",
        "bpm": 120,
        "timesig": (4, 4),
        "notes": 1,
        "motif_length": 1,
        "base_octave": 4,
        "instrument": "Piano",
        "harmony": False,
        "random_rhythm": False,
        "counterpoint": False,
        "harmony_lines": 1,
        "include_chords": False,
        "chords_same": False,
        "ornaments": False,
        # The web GUI forwards the humanize option to ``create_midi_file``.
        # When the checkbox is unchecked the default ``False`` should be sent.
        "humanize": False,
        "enable_ml": False,
        "style": None,
        "chords": ["C"],
        "plagal_cadence": False,
    }

    assert called.get("task")
    assert called.get("args") == ()
    assert called.get("kwargs") == expected_params


def test_preview_falls_back_on_broker_failure(monkeypatch):
    """Unreachable brokers should trigger in-process preview rendering."""

    # Point the web GUI at an invalid Celery broker to simulate network
    # connectivity issues.
    monkeypatch.setenv("CELERY_BROKER_URL", "amqp://invalid")

    celery_mod = types.ModuleType("celery")
    called: dict = {}

    class DummyTask:
        """Task wrapper that raises when dispatched to simulate failure."""

        def __init__(self, fn):
            self.fn = fn

        def delay(self, **_kw):
            # Record that the async path was attempted before raising an error
            # as a real Celery client would when the broker is unreachable.
            called["delay"] = True
            raise RuntimeError("broker unreachable")

    class DummyCelery:
        """Minimal stand-in returning the dummy task."""

        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    # Reload the module so it picks up the patched environment variable and the
    # stub Celery implementation.
    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    gui.app.config["WTF_CSRF_ENABLED"] = False
    client = gui.app.test_client()

    called_sync: dict = {}

    def fake_preview(**_kw):
        """Return empty preview data and record synchronous execution."""

        called_sync["called"] = True
        return "", ""

    # Replace the heavy preview generator so the test remains fast and
    # deterministic.
    monkeypatch.setattr(gui, "_generate_preview", fake_preview)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    assert resp.status_code == 200
    assert called.get("delay")
    assert called_sync.get("called")
    # Users should be informed that the background worker could not be reached
    # and the preview was generated synchronously instead.
    assert b"background worker" in resp.data


def test_celery_failure_falls_back_to_sync(monkeypatch):
    """Preview generation should continue if the Celery broker is unreachable."""

    celery_mod = types.ModuleType("celery")
    called = {}

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, **_kw):
            """Simulate a broker connection error when dispatching."""
            called["delay"] = True
            raise RuntimeError("broker unreachable")

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    gui.app.config["WTF_CSRF_ENABLED"] = False
    client = gui.app.test_client()

    called_sync = {}

    def fake_preview(**_kw):
        called_sync["called"] = True
        return "", ""

    monkeypatch.setattr(gui, "_generate_preview", fake_preview)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    assert resp.status_code == 200
    assert called.get("delay")
    assert called_sync.get("called")
    # The user should be notified that asynchronous dispatch failed so
    # the preview was generated synchronously instead of silently falling
    # back.
    assert b"background worker" in resp.data


def test_celery_timeout_falls_back_to_sync(monkeypatch):
    """Timed-out Celery tasks should trigger a synchronous fallback."""

    celery_mod = types.ModuleType("celery")
    called: dict = {}

    class DummyAsyncResult:
        """Stand-in that always times out when fetching the result."""

        def get(self, timeout=None):
            # Record the timeout parameter to ensure the code waits only a
            # bounded period for the worker.
            called["timeout"] = timeout
            raise celery_mod.exceptions.TimeoutError("timeout")

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, **_kw):
            """Return an async result that will trigger a timeout."""
            called["delay"] = True
            return DummyAsyncResult()

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            return DummyTask(fn)

    # Provide a placeholder TimeoutError so the module under test can import it.
    exceptions_mod = types.ModuleType("celery.exceptions")

    class DummyTimeout(Exception):
        pass

    exceptions_mod.TimeoutError = DummyTimeout
    celery_mod.Celery = DummyCelery
    celery_mod.exceptions = exceptions_mod
    monkeypatch.setitem(sys.modules, "celery", celery_mod)
    monkeypatch.setitem(sys.modules, "celery.exceptions", exceptions_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    gui.app.config["WTF_CSRF_ENABLED"] = False
    client = gui.app.test_client()

    called_sync: dict = {}

    def fake_preview(**_kw):
        called_sync["called"] = True
        return "", ""

    # Replace the real preview generator so the test remains fast and
    # deterministic.
    monkeypatch.setattr(gui, "_generate_preview", fake_preview)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
            "harmony_lines": "1",
        },
    )

    assert resp.status_code == 200
    assert called.get("delay")
    assert called_sync.get("called")
    # Verify that ``get`` was invoked with the expected timeout parameter.
    assert called.get("timeout") == 10
    # The user should see a notice that the worker timed out.
    assert b"timed out" in resp.data


def test_random_rhythm_length_matches_notes(monkeypatch):
    """Random rhythm option should produce a pattern equal to the note count."""

    captured = {}

    # Stub heavy generation functions to keep the test fast and predictable.
    monkeypatch.setattr(web_gui, "generate_melody", lambda *a, **k: ["C4"] * 4)

    def fake_pattern(n):
        captured["length"] = n
        return [0.25] * n

    monkeypatch.setattr(web_gui, "generate_random_rhythm_pattern", fake_pattern)

    def fake_create(mel, bpm, ts, path, *, pattern=None, **_kw):
        captured["pattern"] = pattern
        Path(path).write_text("midi")

    monkeypatch.setattr(web_gui, "create_midi_file", fake_create)
    monkeypatch.setattr(web_gui.playback, "render_midi_to_wav", lambda *a, **k: None)

    web_gui._generate_preview(
        key="C",
        bpm=120,
        timesig=(4, 4),
        notes=4,
        motif_length=2,
        base_octave=4,
        instrument="Piano",
        harmony=False,
        random_rhythm=True,
        counterpoint=False,
        harmony_lines=0,
        include_chords=False,
        chords_same=False,
        enable_ml=False,
        style=None,
        chords=["C"],
        humanize=False,
        ornaments=False,
        plagal_cadence=False,
    )

    assert captured.get("length") == 4
    assert captured.get("pattern") == [0.25] * 4


def test_temp_files_cleaned_on_failure(tmp_path, monkeypatch):
    """Temporary preview files should be removed even if generation fails."""

    created: list[Path] = []

    def fake_tmpfile(suffix="", delete=False):
        path = tmp_path / f"tmp{len(created)}{suffix}"
        path.touch()

        class Dummy:
            def __init__(self, name):
                self.name = str(name)

            def close(self):
                pass

        created.append(path)
        return Dummy(path)

    def raise_error(*_a, **_k):
        raise RuntimeError("fail")

    monkeypatch.setattr(web_gui, "NamedTemporaryFile", fake_tmpfile)
    monkeypatch.setattr(web_gui, "create_midi_file", raise_error)
    monkeypatch.setattr(web_gui.playback, "render_midi_to_wav", lambda *a, **k: None)

    with pytest.raises(RuntimeError):
        web_gui._generate_preview(
            key="C",
            bpm=120,
            timesig=(4, 4),
            notes=1,
            motif_length=1,
            base_octave=4,
            instrument="Piano",
            harmony=False,
            random_rhythm=False,
            counterpoint=False,
            harmony_lines=0,
            include_chords=False,
            chords_same=False,
            enable_ml=False,
            style=None,
            chords=["C"],
            humanize=False,
            ornaments=False,
            plagal_cadence=False,
        )

    for path in created:
        assert not path.exists()


def test_create_app_requires_flask_secret(monkeypatch):
    """Factory aborts when ``FLASK_SECRET`` is missing in production."""
    monkeypatch.delenv("FLASK_SECRET", raising=False)
    monkeypatch.setenv("CELERY_BROKER_URL", "memory://")
    with pytest.raises(RuntimeError):
        web_gui.create_app()


def test_create_app_requires_broker(monkeypatch):
    """Factory aborts when ``CELERY_BROKER_URL`` is missing in production."""
    monkeypatch.setenv("FLASK_SECRET", "testing-secret")
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    with pytest.raises(RuntimeError):
        web_gui.create_app()


def test_rejects_oversized_request():
    """Payloads larger than ``MAX_CONTENT_LENGTH`` are rejected with HTTP 413."""

    oversized_app = web_gui.create_app()
    # Keep CSRF disabled to isolate the size check from token validation.
    oversized_app.config["WTF_CSRF_ENABLED"] = False
    # Limit uploads to an intentionally tiny size to trigger the 413 response.
    oversized_app.config["MAX_CONTENT_LENGTH"] = 100

    client = oversized_app.test_client()
    large_value = "x" * 200  # Exceeds the 100-byte limit.
    resp = client.post("/", data={"payload": large_value})
    assert resp.status_code == 413
