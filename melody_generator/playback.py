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
default is attempted.  Setting ``SOUND_FONT`` globally allows both the GUI and
CLI helpers to locate the same instrument bank without additional
configuration.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

__all__ = [
    "MidiPlaybackError",
    "play_midi",
    "render_midi_to_wav",
    "open_default_player",
]


class MidiPlaybackError(RuntimeError):
    """Raised when MIDI playback or rendering fails."""


def _resolve_soundfont(sf: Optional[str]) -> str:
    """Return the path to the soundfont to use for synthesis."""

    candidate = sf or os.environ.get("SOUND_FONT") or "/usr/share/sounds/sf2/TimGM6mb.sf2"
    # Expand ``~`` and environment variables so user-supplied paths work
    # regardless of how they are specified.
    candidate = os.path.expanduser(os.path.expandvars(candidate))
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
        If PyFluidSynth is unavailable, ``fluidsynth`` is missing, or playback
        fails.  When the underlying executable is absent a
        ``MidiPlaybackError`` with the message ``"fluidsynth not installed"``
        is raised.
    """

    try:
        import fluidsynth  # type: ignore
    except FileNotFoundError as exc:  # type: ignore[attr-defined]
        # ``fluidsynth`` C library not found; provide a clear error message
        raise MidiPlaybackError("fluidsynth not installed") from exc
    except Exception as exc:  # type: ignore
        # Any other import failure indicates PyFluidSynth itself is missing
        raise MidiPlaybackError("PyFluidSynth is required for playback") from exc

    sf_path = _resolve_soundfont(soundfont)

    try:
        synth = fluidsynth.Synth()
    except FileNotFoundError as exc:
        # Raised when the underlying ``fluidsynth`` binary or library is
        # missing entirely. This provides a clearer message than the raw
        # exception text from the dependency.
        raise MidiPlaybackError("fluidsynth not installed") from exc
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


def render_midi_to_wav(
    midi_path: str, wav_path: str, soundfont: Optional[str] = None
) -> None:
    """Render ``midi_path`` to ``wav_path`` using the ``fluidsynth`` CLI.

    ``fluidsynth`` must be installed on the system for this to work. The
    function is primarily used by the web interface to embed audio in the
    browser when native MIDI playback is not available.

    Raises
    ------
    MidiPlaybackError
        If ``fluidsynth`` is missing, the MIDI file does not exist or the
        subprocess fails for any other reason. When the executable is absent
        the error message will be ``"fluidsynth not installed"``.
    """

    sf_path = _resolve_soundfont(soundfont)

    # Fail fast when the input file does not exist to avoid spawning
    # ``fluidsynth`` with an invalid path which would result in a cryptic
    # error message from the subprocess.
    if not os.path.isfile(midi_path):
        raise MidiPlaybackError("MIDI file not found")
    cmd = [
        "fluidsynth",
        "-ni",
        "-F",
        wav_path,
        sf_path,
        midi_path,
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        # ``fluidsynth`` executable not present in ``PATH``
        raise MidiPlaybackError("fluidsynth not installed") from exc
    except Exception as exc:
        raise MidiPlaybackError(f"Failed to render MIDI: {exc}") from exc


def open_default_player(path: str, *, delete_after: bool = False) -> None:
    """Launch ``path`` with the operating system's default MIDI player.

    This function contains the platform-specific logic used by both the
    command line and GUI helpers. It blocks until the player command
    completes, removing ``path`` afterwards when ``delete_after`` is ``True``.

    Parameters
    ----------
    path:
        File to open in the default player.
    delete_after:
        Delete ``path`` once playback finishes.

    Raises
    ------
    Exception
        Propagates any errors raised by ``subprocess.run`` or ``os.remove``.
    """

    player = os.environ.get("MELODY_PLAYER")
    if sys.platform.startswith("win"):
        if player:
            subprocess.run([player, path], check=False)
        else:
            subprocess.run(["cmd", "/c", "start", "/wait", "", path], check=False)
    elif sys.platform == "darwin":
        if player:
            subprocess.run(["open", "-W", "-a", player, path], check=False)
        else:
            subprocess.run(["open", "-W", path], check=False)
    else:
        if player:
            subprocess.run([player, path], check=False)
        else:
            proc = subprocess.run(["xdg-open", "--wait", path], check=False)
            if proc.returncode != 0:
                subprocess.run(["xdg-open", path], check=False)

    if delete_after:
        os.remove(path)
