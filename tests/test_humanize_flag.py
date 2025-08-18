"""Unit tests validating the new humanization toggle.

The module stubs out the ``mido`` dependency so tests can run without
writing actual MIDI files. It reloads ``melody_generator`` with these
stubs and verifies that events are unchanged when ``humanize=False``.
"""

import importlib
import sys
import types
from pathlib import Path


def _setup_module():
    """Reload melody_generator with stubbed dependencies."""
    stub_mido = types.ModuleType("mido")

    class Msg:
        def __init__(self, type: str, **kw) -> None:
            self.type = type
            self.time = kw.get("time", 0)
            self.velocity = kw.get("velocity")
            self.note = kw.get("note")
            self.program = kw.get("program")

    class DummyFile:
        last_instance = None

        def __init__(self, *a, **k) -> None:
            self.tracks = []
            DummyFile.last_instance = self

        def save(self, _p: str) -> None:
            pass

    stub_mido.Message = Msg
    stub_mido.MidiFile = DummyFile
    stub_mido.MidiTrack = list
    stub_mido.MetaMessage = lambda *a, **k: Msg("meta", **k)
    stub_mido.bpm2tempo = lambda bpm: bpm
    sys.modules["mido"] = stub_mido

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")
    sys.modules.setdefault("tkinter", tk_stub)
    sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
    sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
    sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    if "melody_generator.midi_io" in sys.modules:
        del sys.modules["melody_generator.midi_io"]
    if "melody_generator" in sys.modules:
        del sys.modules["melody_generator"]
    return importlib.import_module("melody_generator"), DummyFile


def test_no_humanize_preserves_events(tmp_path, monkeypatch):
    """Events remain unaltered when ``humanize`` is ``False``."""
    # The DummyFile tracks list will hold the messages written by
    # ``create_midi_file``. By calling the function twice—once with
    # ``humanize`` disabled and once enabled—we can compare the resulting
    # timings to confirm jitter only applies when requested.
    mod, DummyFile = _setup_module()

    def fake_humanize(msgs):
        for m in msgs:
            m.time += 99

    monkeypatch.setattr(mod, "humanize_events", fake_humanize)
    monkeypatch.setattr(mod.midi_io, "humanize_events", fake_humanize)

    melody = ["C4", "D4"]
    out = tmp_path / "a.mid"
    mod.create_midi_file(melody, 120, (4, 4), str(out), pattern=[0.25], humanize=False)
    base_times = [m.time for m in DummyFile.last_instance.tracks[0]]

    out2 = tmp_path / "b.mid"
    mod.create_midi_file(melody, 120, (4, 4), str(out2), pattern=[0.25], humanize=True)
    jitter_times = [m.time for m in DummyFile.last_instance.tracks[0]]

    assert base_times != jitter_times
    diffs = [j - b for j, b in zip(jitter_times, base_times)]
    assert any(d == 99 for d in diffs)
    assert all(b <= j for b, j in zip(base_times, jitter_times))


def test_humanize_all_tracks(tmp_path, monkeypatch):
    """Humanization is applied to every track when multiple tracks exist."""
    # By requesting harmony and providing an additional track, ``create_midi_file``
    # produces three tracks: the melody, a harmony line, and the extra part.
    # ``humanize_events`` is monkeypatched to record each invocation and to add
    # a constant offset to event times so the test can verify that every track
    # was processed.
    mod, DummyFile = _setup_module()

    calls = []

    def fake_humanize(msgs):
        calls.append(id(msgs))
        for m in msgs:
            m.time += 99

    monkeypatch.setattr(mod, "humanize_events", fake_humanize)
    monkeypatch.setattr(mod.midi_io, "humanize_events", fake_humanize)

    melody = ["C4"]
    extra = [["E4"]]
    out = tmp_path / "multi.mid"
    mod.create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        pattern=[0.25],
        harmony=True,
        extra_tracks=extra,
        humanize=True,
    )

    # ``humanize_events`` should have been called once per track.
    assert len(calls) == len(DummyFile.last_instance.tracks)
    # The first message in every track should reflect the jitter added by the
    # stubbed ``humanize_events`` implementation.
    for track in DummyFile.last_instance.tracks:
        assert track[0].time == 99
