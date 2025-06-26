"""MIDI playback utilities using FluidSynth.

This module provides helper functions for previewing generated MIDI files
without relying on the user's default operating system player.  Playback
is performed with the ``fluidsynth`` library which requires a SoundFont
(SF2) file to synthesize audio.

Example usage
-------------
>>> from melody_generator.playback import play_midi
>>> play_midi("song.mid")

The SoundFont path can be supplied via the ``soundfont`` parameter or the
``SOUND_FONT`` environment variable.  When neither is given a sensible
default is attempted.
"""

from __future__ import annotations

import os
import subprocess
from typing import Optional

__all__ = ["MidiPlaybackError", "play_midi", "render_midi_to_wav"]


class MidiPlaybackError(RuntimeError):
    """Raised when MIDI playback or rendering fails."""


def _resolve_soundfont(sf: Optional[str]) -> str:
    """Return the path to the soundfont to use for synthesis."""

    candidate = sf or os.environ.get("SOUND_FONT") or "/usr/share/sounds/sf2/TimGM6mb.sf2"
    if not os.path.isfile(candidate):
        raise MidiPlaybackError(
            "SoundFont not found. Provide path via argument or SOUND_FONT env var."
        )
    return candidate


def play_midi(path: str, soundfont: Optional[str] = None) -> None:
    """Play ``path`` using FluidSynth in real time.

    Parameters
    ----------
    path:
        MIDI file to play.
    soundfont:
        Optional path to the SoundFont ``.sf2`` file. When omitted the
        ``SOUND_FONT`` environment variable or a system default is used.

    Raises
    ------
    MidiPlaybackError
        If FluidSynth is unavailable or playback fails.
    """

    try:
        import fluidsynth  # type: ignore
    except Exception as exc:  # type: ignore
        raise MidiPlaybackError("PyFluidSynth is required for playback") from exc

    sf_path = _resolve_soundfont(soundfont)

    synth = fluidsynth.Synth()
    try:
        synth.start()
    except Exception as exc:
        raise MidiPlaybackError(f"Could not start audio driver: {exc}") from exc

    try:
        sfid = synth.sfload(sf_path)
        synth.program_select(0, sfid, 0, 0)
        synth.play_midi_file(path)
    except Exception as exc:
        raise MidiPlaybackError(f"Playback failed: {exc}") from exc
    finally:
        synth.delete()


def render_midi_to_wav(midi_path: str, wav_path: str, soundfont: Optional[str] = None) -> None:
    """Render ``midi_path`` to ``wav_path`` using the ``fluidsynth`` CLI.

    ``fluidsynth`` must be installed on the system for this to work.  The
    function is primarily used by the web interface to embed audio in the
    browser when native MIDI playback is not available.
    """

    sf_path = _resolve_soundfont(soundfont)
    cmd = [
        "fluidsynth",
        "-ni",
        "-F",
        wav_path,
        sf_path,
        midi_path,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        raise MidiPlaybackError(f"Failed to render MIDI: {exc}") from exc
