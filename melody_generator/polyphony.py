"""Polyphonic counterpoint generation utilities.

This module orchestrates four independent melody lines (soprano, alto,
tenor and bass). Each part may have its own :class:`~melody_generator.sequence_model.SequenceModel`
for data-driven note prediction. After generating the voices, a simple
post-processing pass adjusts notes to avoid voice crossing and to keep
adjacent parts within a reasonable register difference.

Example
-------
>>> gen = PolyphonicGenerator()
>>> parts = gen.generate('C', 8, ['C', 'G', 'Am', 'F'])
>>> gen.to_midi(parts, 120, (4, 4), 'polyphony.mid')
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from . import MIN_OCTAVE, MAX_OCTAVE
from .sequence_model import SequenceModel


class PolyphonicGenerator:
    """Generate simple four-voice counterpoint melodies."""

    voices = ["soprano", "alto", "tenor", "bass"]

    def __init__(self, sequence_models: Optional[Dict[str, SequenceModel]] = None) -> None:
        """Create a new generator.

        Parameters
        ----------
        sequence_models:
            Optional mapping of voice names to sequence models. Voices not
            present in the mapping fall back to heuristic generation.
        """

        self.sequence_models = sequence_models or {}
        self.default_octaves = {
            "soprano": 5,
            "alto": 4,
            "tenor": 3,
            "bass": 2,
        }

    def generate(
        self,
        key: str,
        num_notes: int,
        chord_progression: List[str],
        *,
        base_octaves: Optional[Dict[str, int]] = None,
    ) -> Dict[str, List[str]]:
        """Return melody lines for each voice.

        Parameters
        ----------
        key:
            Musical key for all voices.
        num_notes:
            Number of notes per voice.
        chord_progression:
            Harmony driving note choice.
        base_octaves:
            Optional per-voice octave overrides. Each value must fall within
            ``MIN_OCTAVE`` and ``MAX_OCTAVE`` otherwise a ``ValueError`` will be
            raised.

        Returns
        -------
        Dict[str, List[str]]
            Mapping voice name to generated melody line.
        """

        if not chord_progression:
            raise ValueError("chord_progression must not be empty")
        base_octaves = base_octaves or {}
        lines: Dict[str, List[str]] = {}
        for voice in self.voices:
            model = self.sequence_models.get(voice)
            octave = base_octaves.get(voice, self.default_octaves[voice])
            # Validate provided octave range rather than silently clamping. This
            # prevents surprising register shifts when a caller accidentally
            # supplies an out-of-bounds value.
            if voice in base_octaves and not MIN_OCTAVE <= octave <= MAX_OCTAVE:
                raise ValueError(
                    f"base_octaves[{voice!r}] must be between {MIN_OCTAVE} and {MAX_OCTAVE}"
                )
            octave = max(MIN_OCTAVE, min(MAX_OCTAVE, octave))
            from . import generate_melody  # Local import avoids circular deps
            line = generate_melody(
                key,
                num_notes,
                chord_progression,
                base_octave=octave,
                sequence_model=model,
            )
            lines[voice] = line

        self._enforce_voice_leading(lines)
        return lines

    def to_midi(
        self,
        voices: Dict[str, List[str]],
        bpm: int,
        time_signature: Tuple[int, int],
        path: str,
        *,
        pattern: Optional[List[float]] = None,
        chord_progression: Optional[List[str]] = None,
    ) -> None:
        """Write ``voices`` to ``path`` using multiple MIDI tracks."""

        extra = [voices[v] for v in self.voices[1:]]
        from . import create_midi_file  # Local import avoids circular deps
        create_midi_file(
            voices[self.voices[0]],
            bpm,
            time_signature,
            path,
            pattern=pattern,
            extra_tracks=extra,
            chord_progression=chord_progression,
        )

    def _enforce_voice_leading(self, voices: Dict[str, List[str]]) -> None:
        """Adjust voices in place to avoid crossing and wide spacing."""

        length = len(next(iter(voices.values())))
        from . import note_to_midi, midi_to_note  # Local import avoids circular deps
        for i in range(length):
            for hi, lo in zip(self.voices, self.voices[1:]):
                up = note_to_midi(voices[hi][i])
                low = note_to_midi(voices[lo][i])
                # Prevent voice crossing by moving the lower voice down or the
                # upper voice up by an octave as needed.
                if up < low:
                    if up + 12 <= 127:
                        up += 12
                        voices[hi][i] = midi_to_note(up)
                    elif low - 12 >= 0:
                        low -= 12
                        voices[lo][i] = midi_to_note(low)
                # Keep adjacent voices within one octave.
                if up - low > 12 and low + 12 <= 127:
                    low += 12
                    voices[lo][i] = midi_to_note(low)

