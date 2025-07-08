"""Command line helpers for Melody Generator.

The functions here parse command line arguments and dispatch to the core
library. Keeping the CLI isolated simplifies testing and allows other
applications to reuse the generation logic without importing Tkinter.
"""

from __future__ import annotations

import argparse
import logging
import sys
from importlib import import_module
from typing import List

from . import (
    CHORDS,
    canonical_chord,
    canonical_key,
    MAX_OCTAVE,
    MIN_OCTAVE,
    SCALE,
)


__all__ = ["run_cli", "main"]


def run_cli() -> None:
    """Parse CLI arguments and generate a MIDI file."""

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
    parser.add_argument("--no-humanize", dest="humanize", action="store_false", help="Disable timing and velocity randomization")
    parser.add_argument("--enable-ml", action="store_true", help="Activate ML-based weighting using a small sequence model")
    parser.add_argument("--style", type=str, help="Optional style name to bias note selection")
    parser.add_argument("--soundfont", type=str, help="Path to a SoundFont (.sf2) file used when previewing with --play")
    parser.add_argument("--play", action="store_true", help="Play the MIDI file after it is created")
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

    if not MIN_OCTAVE <= args.base_octave <= MAX_OCTAVE:
        logging.error(f"Base octave must be between {MIN_OCTAVE} and {MAX_OCTAVE}.")
        sys.exit(1)

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
        chord_progression = generate_random_chord_progression(args.key, args.random_chords)
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
        parts = args.timesig.split("/")
        if len(parts) != 2:
            raise ValueError
        numerator, denominator = map(int, parts)
        if numerator <= 0 or denominator not in {1, 2, 4, 8, 16}:
            raise ValueError
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
    if args.play:
        try:
            from . import playback

            playback.play_midi(args.output, soundfont=args.soundfont)
        except Exception:
            _open_default_player(args.output)
    logging.info("Melody generation complete.")


def main() -> None:
    """Entry point that chooses between CLI and GUI."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) > 1:
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

        gui = MelodyGeneratorGUI(
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
        gui.run()


