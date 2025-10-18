"""Tests for :func:`melody_generator.midi_to_degrees` conversion helper.

The scenarios in this module ensure that the MIDI-to-scale-degree conversion
utility honours the musical expectations used by dataset builders. Each test
deliberately targets a core requirement to guard against regressions:

* **Basic mapping** – verifies that C-major melodies map directly to ascending
  scale degrees without unexpected offsets or gaps.
* **Cross-track ordering** – confirms that the helper sorts merged tracks by
  absolute tick time so melodic order remains intact regardless of track
  structure.
* **Chromatic handling** – demonstrates the difference between the default
  chromatic snapping behaviour and the ``drop_out_of_key`` strict filtering
  option.
* **Validation errors** – ensures that empty files produce an immediate,
  descriptive ``ValueError`` so data pipelines fail fast and clearly.
"""

# Modification summary: restructure imports and runtime preparation so Ruff's
# E402 lint check passes while still exercising the real ``mido`` module. The
# new fixture swaps out any stubbed dependencies, reloads ``melody_generator``
# with the genuine library, and restores the environment once the assertions
# finish executing.

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

# Module-level globals are set during test initialisation so the helper
# functions below can access the genuine ``mido`` classes and freshly reloaded
# ``melody_generator`` module. They default to ``None`` until the autouse
# fixture populates them.
Message: type[Any] | None = None
MidiFile: type[Any] | None = None
MidiTrack: type[Any] | None = None
melody_generator: ModuleType | None = None


def _load_real_mido() -> tuple[ModuleType | None, ModuleType]:
    """Swap any stubbed :mod:`mido` module for the real implementation.

    Returns a two-tuple containing the previous module (``None`` when absent)
    and the freshly imported real module so callers can both use the genuine
    API and later restore the stub for other tests.
    """

    original = sys.modules.pop("mido", None)
    try:
        module = importlib.import_module("mido")
    except ModuleNotFoundError as exc:  # pragma: no cover - guards against CI envs
        raise ModuleNotFoundError("mido must be installed for MIDI conversion tests") from exc
    sys.modules["mido"] = module
    return original, module


def _reload_melody_generator() -> ModuleType:
    """Reload :mod:`melody_generator` so it binds to the real ``mido`` module."""

    module = importlib.import_module("melody_generator")
    return importlib.reload(module)


def _ensure_dependencies() -> tuple[type[Any], type[Any], type[Any], ModuleType]:
    """Return the runtime classes/modules required by the tests.

    Defensive checks raise informative ``RuntimeError`` exceptions when the
    autouse fixture fails to initialise correctly. Although this situation is
    unlikely, the explicit error message simplifies diagnosis if it ever occurs
    (for example, when the file is executed in isolation outside pytest).
    """

    if not all((Message, MidiFile, MidiTrack, melody_generator)):
        raise RuntimeError("midi_to_degrees tests require the real mido and melody_generator modules")
    return (
        cast(type[Any], Message),
        cast(type[Any], MidiFile),
        cast(type[Any], MidiTrack),
        cast(ModuleType, melody_generator),
    )


def _restore_mido(original: ModuleType | None) -> None:
    """Return ``sys.modules['mido']`` to its prior stubbed state."""

    if original is not None:
        sys.modules["mido"] = original
    else:
        sys.modules.pop("mido", None)


@pytest.fixture(scope="module", autouse=True)
def _prepare_real_mido_environment() -> Iterator[None]:
    """Ensure tests exercise the true :mod:`mido` API and then restore stubs."""

    original_mido, real_mido = _load_real_mido()
    globals()["Message"] = real_mido.Message
    globals()["MidiFile"] = real_mido.MidiFile
    globals()["MidiTrack"] = real_mido.MidiTrack
    globals()["melody_generator"] = _reload_melody_generator()

    try:
        yield
    finally:
        _restore_mido(original_mido)
        if "melody_generator" in sys.modules:
            importlib.reload(sys.modules["melody_generator"])
        globals()["Message"] = None
        globals()["MidiFile"] = None
        globals()["MidiTrack"] = None
        globals()["melody_generator"] = None


def _write_midi(tmp_path: Path, notes: list[int]) -> Path:
    """Helper that writes a one-track MIDI file containing ``notes``.

    Each note is emitted as a ``note_on`` with an accompanying ``note_off`` so
    the resulting file mirrors the minimal structure produced by the generator.
    """

    Message_cls, MidiFile_cls, MidiTrack_cls, _ = _ensure_dependencies()
    midi = MidiFile_cls()
    track = MidiTrack_cls()
    midi.tracks.append(track)
    for note in notes:
        track.append(Message_cls("note_on", note=note, velocity=64, time=0))
        track.append(Message_cls("note_off", note=note, velocity=0, time=120))
    path = tmp_path / "sequence.mid"
    midi.save(path)
    return path


def test_midi_to_degrees_basic_sequence(tmp_path: Path) -> None:
    """Diatonic C-major notes should map directly to degrees 0..2."""

    midi_path = _write_midi(tmp_path, [60, 62, 64])  # C4, D4, E4
    *_, melody_module = _ensure_dependencies()
    result = melody_module.midi_to_degrees(midi_path, "C")

    # The tones lie squarely in the key so their degrees increment linearly.
    assert result == [0, 1, 2]


def test_midi_to_degrees_sorts_cross_track_events() -> None:
    """Events should be ordered by absolute time even when split across tracks."""

    Message_cls, MidiFile_cls, MidiTrack_cls, melody_module = _ensure_dependencies()
    midi = MidiFile_cls()

    # First track schedules an early E (64) followed by a later G (67).
    track_a = MidiTrack_cls()
    track_a.append(Message_cls("note_on", note=64, velocity=64, time=0))
    track_a.append(Message_cls("note_off", note=64, velocity=0, time=240))
    track_a.append(Message_cls("note_on", note=67, velocity=64, time=120))
    midi.tracks.append(track_a)

    # Second track introduces a middle event (F, 65) after 120 ticks. The
    # absolute-time accumulation should place it between the first two notes.
    track_b = MidiTrack_cls()
    track_b.append(Message_cls("note_on", note=65, velocity=64, time=120))
    midi.tracks.append(track_b)

    result = melody_module.midi_to_degrees(midi, "C")

    # C major degrees: E -> 2, F -> 3, G -> 4. Ordering must reflect absolute
    # timing rather than track append order.
    assert result == [2, 3, 4]


def test_midi_to_degrees_drop_out_of_key(tmp_path: Path) -> None:
    """Chromatic tones are skipped when ``drop_out_of_key`` is enabled."""

    midi_path = _write_midi(tmp_path, [60, 68])  # C4 (in key) and G#4 (chromatic)

    # Default behaviour snaps the G# to the nearest scale degree (G) yielding
    # indices [0, 4]. When ``drop_out_of_key`` is ``True`` only the tonic remains.
    *_, melody_module = _ensure_dependencies()
    snapped = melody_module.midi_to_degrees(midi_path, "C")
    filtered = melody_module.midi_to_degrees(
        midi_path, "C", drop_out_of_key=True
    )

    assert snapped == [0, 4]
    assert filtered == [0]


def test_midi_to_degrees_raises_on_empty(tmp_path: Path) -> None:
    """Missing ``note_on`` messages should trigger a clear validation error."""

    _, MidiFile_cls, MidiTrack_cls, melody_module = _ensure_dependencies()
    empty_midi = MidiFile_cls()
    empty_midi.tracks.append(MidiTrack_cls())
    path = tmp_path / "empty.mid"
    empty_midi.save(path)

    with pytest.raises(ValueError, match="note_on events"):
        melody_module.midi_to_degrees(path, "C")
