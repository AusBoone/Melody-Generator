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

# Revision note
# -------------
# ``_resolve_soundfont`` was extended to check standard SoundFont locations on
# Windows and macOS before falling back to the previous Linux path. This ensures
# playback works out-of-the-box on those systems when the default files are
# present.
#
# Error reporting for missing dependencies was updated to include installation
# hints so users can more easily resolve playback issues.
#
# Current revision introduces ``shlex.split`` to parse the ``MELODY_PLAYER``
# environment variable. This ensures custom player commands containing spaces
# (e.g. paths under ``Program Files``) are executed correctly. ``open_default_player``
# now validates the target MIDI file before launching the subprocess so
# erroneous paths raise ``FileNotFoundError`` immediately.

from __future__ import annotations

import os
import subprocess
import sys
import shlex
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
    """Return the path to the soundfont to use for synthesis.

    Parameters
    ----------
    sf:
        Optional path supplied directly by the caller. When ``None`` the
        ``SOUND_FONT`` environment variable is consulted followed by
        platform-specific defaults.

    Returns
    -------
    str
        Absolute path to an existing SoundFont or DLS file.

    Raises
    ------
    MidiPlaybackError
        If no valid file can be located.
    """

    # Prefer the explicit argument first then the environment variable. If
    # neither are provided choose a sensible default based on the current
    # operating system.
    if sf:
        candidate = sf
    else:
        candidate = os.environ.get("SOUND_FONT")
        if not candidate:
            if sys.platform.startswith("win"):
                candidate = r"C:\\Windows\\System32\\drivers\\gm.dls"
            elif sys.platform == "darwin":
                candidate = "/Library/Audio/Sounds/Banks/FluidR3_GM.sf2"
            else:
                candidate = "/usr/share/sounds/sf2/TimGM6mb.sf2"

    # Expand user home and environment variables to support ``~`` and
    # variables inside the provided path.
    candidate = os.path.expanduser(os.path.expandvars(candidate))

    # Bail out early with a clear error if the file is absent so callers know
    # precisely why playback failed.
    if not os.path.isfile(candidate):
        raise MidiPlaybackError(
            "SoundFont not found. Provide a valid path via the argument or "
            "SOUND_FONT environment variable, or install a General MIDI soundfont."
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
        fails. When the underlying executable is absent a
        ``MidiPlaybackError`` with the message
        ``"fluidsynth not installed. Install the FluidSynth library and
        pyFluidSynth package."`` is raised.
    """

    try:
        import fluidsynth  # type: ignore
    except FileNotFoundError as exc:  # type: ignore[attr-defined]
        # ``fluidsynth`` C library not found; provide a clear error message with
        # guidance on how to install the dependency.
        raise MidiPlaybackError(
            "fluidsynth not installed. Install the FluidSynth library and "
            "pyFluidSynth package."
        ) from exc
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
        raise MidiPlaybackError(
            "fluidsynth not installed. Install the FluidSynth library and "
            "pyFluidSynth package."
        ) from exc
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
        subprocess fails for any other reason. When the executable is absent the
        error message will be ``"fluidsynth not installed. Install the FluidSynth
        library and pyFluidSynth package."``.
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
        raise MidiPlaybackError(
            "fluidsynth not installed. Install the FluidSynth library and "
            "pyFluidSynth package."
        ) from exc
    except Exception as exc:
        raise MidiPlaybackError(f"Failed to render MIDI: {exc}") from exc


def open_default_player(path: str, *, delete_after: bool = False) -> None:
    """Launch ``path`` with the operating system's default MIDI player.

    This function contains the platform-specific logic used by both the
    command line and GUI helpers. It blocks until the player command
    completes, removing ``path`` afterwards when ``delete_after`` is ``True``.
    The ``MELODY_PLAYER`` environment variable may specify a custom player
    executable. When provided it is parsed with ``shlex.split`` so quoted
    commands containing spaces are handled correctly.

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
        ``FileNotFoundError`` is raised when ``path`` does not exist.
    """

    # Fail fast when the target MIDI file is missing so callers immediately know
    # the provided path is incorrect.
    if not os.path.isfile(path):
        raise FileNotFoundError(f"MIDI file not found: {path}")

    player = os.environ.get("MELODY_PLAYER")
    # ``shlex.split`` correctly handles quoted paths so custom player commands
    # containing spaces are parsed into individual arguments.
    player_args = shlex.split(player) if player else None

    if sys.platform.startswith("win"):
        if player_args:
            cmd = player_args + [path]
            subprocess.run(cmd, check=False)
        else:
            subprocess.run(["cmd", "/c", "start", "/wait", "", path], check=False)
    elif sys.platform == "darwin":
        if player_args:
            cmd = ["open", "-W", "-a"] + player_args + [path]
            subprocess.run(cmd, check=False)
        else:
            subprocess.run(["open", "-W", path], check=False)
    else:
        if player_args:
            cmd = player_args + [path]
            subprocess.run(cmd, check=False)
        else:
            proc = subprocess.run(["xdg-open", "--wait", path], check=False)
            if proc.returncode != 0:
                subprocess.run(["xdg-open", path], check=False)

    if delete_after:
        os.remove(path)
