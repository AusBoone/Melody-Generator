import importlib
import sys
import types


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

    if "melody_generator" in sys.modules:
        del sys.modules["melody_generator"]
    return importlib.import_module("melody_generator"), DummyFile


def test_no_humanize_preserves_events(tmp_path, monkeypatch):
    """Events remain unaltered when ``humanize`` is ``False``."""
    mod, DummyFile = _setup_module()

    def fake_humanize(msgs):
        for m in msgs:
            m.time += 99

    monkeypatch.setattr(mod, "humanize_events", fake_humanize)

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
