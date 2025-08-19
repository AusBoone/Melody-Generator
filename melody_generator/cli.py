"""Command line helpers for Melody Generator.

Modification summary
--------------------
* Expanded module docstring with an explicit usage example and notes on design
  assumptions.
* Added validation and error handling for ``--random-chords`` values.
* Logged playback failures before falling back to the system's default MIDI
  player so users still hear results while developers retain the traceback for
  debugging.
* Ensured the output directory exists and gracefully handles ``OSError`` when
  writing MIDI files.
* Linked the ``--style`` argument help text to style weight documentation.

This module implements the console entry points for the project. The
``run_cli`` function parses command line arguments and performs melody
generation while :func:`main` decides whether to show the GUI or process CLI
options.  A ``--settings-file`` argument is recognised so the GUI can load and
save user preferences at a custom path.

Keeping the CLI logic separated from the GUI widgets simplifies testing and
allows other applications to reuse the generation routines without importing
``tkinter``.

Example
-------
Running ``python -m melody_generator.cli --key C --chords C,G,Am,F --bpm 120 \
    --timesig 4/4 --notes 16 --output out.mid`` will create a 16-note melody in
the key of C and save it to ``out.mid``. The CLI assumes FluidSynth is installed
for playback if requested and relies on ``--settings-file`` only when the GUI is
launched without additional arguments.
"""

from __future__ import annotations

import argparse
import logging
import sys
import random
from importlib import import_module
from pathlib import Path
from typing import List

from . import (
    CHORDS,
    canonical_chord,
    canonical_key,
    MAX_OCTAVE,
    MIN_OCTAVE,
    SCALE,
)
from .utils import validate_time_signature


__all__ = ["run_cli", "main"]


def run_cli() -> None:
    """Parse CLI arguments and generate a MIDI file.

    The ``--settings-file`` option is recognised for parity with the GUI even
    though it has no effect when running purely from the command line. When
    ``--play`` is supplied the generated MIDI will be previewed; any failures
    during FluidSynth playback are logged and the system's default player is
    invoked so users still hear the result.
    """

    if "--list-keys" in sys.argv[1:]:
        print("\n".join(sorted(SCALE.keys())))
        return
    if "--list-chords" in sys.argv[1:]:
        print("\n".join(sorted(CHORDS.keys())))
        return
    parser = argparse.ArgumentParser(
        description="Generate a random melody and save as a MIDI file."
    )
    parser.add_argument("--list-keys", action="store_true", help="List all supported keys and exit")
    parser.add_argument("--list-chords", action="store_true", help="List all supported chords and exit")
    parser.add_argument("--key", type=str, required=True, help="Musical key (e.g., C, Dm, etc.).")
    parser.add_argument("--chords", type=str, help="Comma-separated chord progression (e.g., C,Am,F,G).")
    parser.add_argument("--random-chords", type=int, metavar="N", help="Generate a random chord progression of N chords, ignoring --chords.")
    parser.add_argument("--bpm", type=int, required=True, help="Beats per minute (integer).")
    parser.add_argument("--timesig", type=str, required=True, help="Time signature in numerator/denominator format (e.g., 4/4).")
    parser.add_argument("--notes", type=int, required=True, help="Number of notes in the melody.")
    parser.add_argument("--output", type=str, required=True, help="Output MIDI file path.")
    parser.add_argument("--motif_length", type=int, default=4, help="Length of the initial motif (default: 4).")
    parser.add_argument("--harmony", action="store_true", help="Add a simple harmony track.")
    parser.add_argument("--random-rhythm", action="store_true", help="Generate a random rhythmic pattern.")
    parser.add_argument("--counterpoint", action="store_true", help="Generate a counterpoint line.")
    parser.add_argument("--harmony-lines", type=int, default=0, metavar="N", help="Number of harmony lines to add in parallel")
    parser.add_argument(
        "--base-octave",
        type=int,
        default=4,
        help=f"Starting octave for the melody ({MIN_OCTAVE}-{MAX_OCTAVE}, default: 4).",
    )
    parser.add_argument("--include-chords", action="store_true", help="Add the chord progression to the MIDI output")
    parser.add_argument("--chords-same-track", action="store_true", help="Write chords on the melody track instead of a new one")
    parser.add_argument("--instrument", type=int, default=0, help="MIDI program number for the melody instrument")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible output")
    parser.add_argument("--no-humanize", dest="humanize", action="store_false", help="Disable timing and velocity randomization")
    parser.add_argument("--enable-ml", action="store_true", help="Activate ML-based weighting using a small sequence model")
    parser.add_argument(
        "--style",
        type=str,
        help=(
            "Optional style name to bias note selection; see "
            "docs/README_STYLE_WEIGHTS.md for presets"
        ),
    )
    parser.add_argument("--soundfont", type=str, help="Path to a SoundFont (.sf2) file used when previewing with --play")
    parser.add_argument("--play", action="store_true", help="Play the MIDI file after it is created")
    parser.add_argument(
        "--settings-file",
        type=str,
        help="Path to the JSON settings file used by the GUI",
    )
    args = parser.parse_args()

    if args.bpm <= 0:
        logging.error("BPM must be a positive integer.")
        sys.exit(1)
    if args.notes <= 0:
        logging.error("Number of notes must be a positive integer.")
        sys.exit(1)
    if args.motif_length <= 0:
        logging.error("Motif length must be a positive integer.")
        sys.exit(1)
    if args.motif_length > args.notes:
        logging.error("Motif length cannot exceed the number of notes.")
        sys.exit(1)
    if args.instrument < 0 or args.instrument > 127:
        logging.error("Instrument must be between 0 and 127.")
        sys.exit(1)

    if args.harmony_lines < 0:
        logging.error("Harmony lines must be non-negative")
        sys.exit(1)

    if not MIN_OCTAVE <= args.base_octave <= MAX_OCTAVE:
        logging.error(f"Base octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}.")
        sys.exit(1)
    # Ensure random chord generation requests specify a positive count.
    if args.random_chords is not None and args.random_chords <= 0:
        logging.error("Random chord count must be a positive integer.")
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)
        try:  # pragma: no cover - numpy may be absent
            import numpy as _np

            _np.random.seed(args.seed)
        except Exception:
            pass

    try:
        from . import (
            generate_random_chord_progression,
            generate_random_rhythm_pattern,
            generate_melody,
            generate_harmony_line,
            generate_counterpoint_melody,
            create_midi_file,
            load_sequence_model,
            get_style_vector,
            _open_default_player,
        )
        args.key = canonical_key(args.key)
    except ValueError:
        logging.error("Invalid key provided.")
        sys.exit(1)

    if args.random_chords:
        # Attempt to generate a random progression while surfacing validation errors
        try:
            chord_progression = generate_random_chord_progression(
                args.key, args.random_chords
            )
        except ValueError as exc:
            logging.error(str(exc))
            sys.exit(1)
    else:
        if not args.chords:
            logging.error("Chord progression required unless --random-chords is used.")
            sys.exit(1)
        chord_names = [chord.strip() for chord in args.chords.split(",")]
        chord_progression = []
        for chord in chord_names:
            try:
                chord_progression.append(canonical_chord(chord))
            except ValueError:
                logging.error(f"Invalid chord in progression: {chord}")
                sys.exit(1)

    try:
        numerator, denominator = validate_time_signature(args.timesig)
    except ValueError:
        logging.error(
            "Time signature must be in the form 'numerator/denominator' with numerator > 0 and denominator one of 1, 2, 4, 8 or 16."
        )
        sys.exit(1)

    if args.style:
        try:
            get_style_vector(args.style)
        except KeyError:
            logging.error(f"Unknown style: {args.style}")
            sys.exit(1)

    seq_model = None
    if args.enable_ml:
        try:
            seq_model = load_sequence_model(None, len(SCALE[args.key]))
        except RuntimeError as exc:
            logging.error(str(exc))
            sys.exit(1)

    rhythm = generate_random_rhythm_pattern(args.notes) if args.random_rhythm else None
    melody = generate_melody(
        args.key,
        args.notes,
        chord_progression,
        motif_length=args.motif_length,
        base_octave=args.base_octave,
        sequence_model=seq_model,
        style=args.style,
        pattern=rhythm,
    )
    extra: List[List[str]] = []
    for _ in range(max(0, args.harmony_lines)):
        extra.append(generate_harmony_line(melody))
    if args.counterpoint:
        extra.append(generate_counterpoint_melody(melody, args.key))
    # Ensure the destination directory exists before attempting to write the
    # MIDI file. ``exist_ok=True`` permits reusing pre-existing directories
    # while still creating nested paths as needed.
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    try:
        create_midi_file(
            melody,
            args.bpm,
            (numerator, denominator),
            args.output,
            harmony=args.harmony,
            pattern=rhythm,
            extra_tracks=extra,
            chord_progression=chord_progression if args.include_chords else None,
            chords_separate=not args.chords_same_track,
            program=args.instrument,
            humanize=args.humanize,
        )
    except OSError as exc:
        # Permission issues or full disks may surface as ``OSError``. Logging
        # the exception gives users insight into the failure and exiting with a
        # non-zero code signals that generation did not succeed.
        logging.error("Could not write MIDI file: %s", exc)
        sys.exit(1)
    if args.play:
        try:
            from . import playback

            playback.play_midi(args.output, soundfont=args.soundfont)
        except Exception:  # noqa: BLE001 - broad to ensure fallback
            # ``logging.exception`` records the stack trace so developers can
            # diagnose issues such as missing FluidSynth or audio driver
            # misconfiguration. The user experience is preserved by falling
            # back to the operating system's default player regardless of the
            # failure cause.
            logging.exception(
                "FluidSynth playback failed; using system default player as fallback.",
            )
            _open_default_player(args.output)
    logging.info("Melody generation complete.")


def main() -> None:
    """Entry point that chooses between CLI and GUI.

    ``--settings-file`` may be supplied when launching the GUI to override the
    location of the persistent JSON configuration file. When additional
    arguments are present the CLI executes normally and the option is ignored.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--settings-file", type=str)
    pre_args, remaining = pre_parser.parse_known_args(sys.argv[1:])

    if remaining:
        run_cli()
    else:
        try:
            MelodyGeneratorGUI = import_module("melody_generator.gui").MelodyGeneratorGUI
        except ImportError:
            logging.error(
                "Tkinter is required for the GUI. Run with CLI arguments or install Tkinter."
            )
            logging.error("Tkinter is not available. Please run with CLI options or install it.")
            sys.exit(1)

        from pathlib import Path

        from . import (
            generate_melody,
            create_midi_file,
            SCALE,
            CHORDS,
            load_settings,
            save_settings,
            generate_random_chord_progression,
            generate_random_rhythm_pattern,
            generate_harmony_line,
            generate_counterpoint_melody,
        )

        settings_path = Path(pre_args.settings_file).expanduser() if pre_args.settings_file else None

        def _load() -> dict:
            return load_settings(settings_path) if settings_path else load_settings()

        def _save(data: dict) -> None:
            save_settings(data, settings_path) if settings_path else save_settings(data)

        gui = MelodyGeneratorGUI(
            generate_melody,
            create_midi_file,
            SCALE,
            CHORDS,
            _load,
            _save,
            generate_random_chord_progression,
            generate_random_rhythm_pattern,
            generate_harmony_line,
            generate_counterpoint_melody,
        )
        gui.run()


