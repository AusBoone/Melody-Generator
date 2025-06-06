import importlib
import sys
import types
import pytest

pytest.importorskip("flask")

# Stub mido and tkinter so the imports succeed
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *a, **k: None
stub_mido.MidiFile = lambda *a, **k: types.SimpleNamespace(tracks=[])
stub_mido.MidiTrack = lambda *a, **k: []
stub_mido.MetaMessage = lambda *a, **k: None
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

web_gui = importlib.import_module("melody_generator.web_gui")

app = web_gui.app


def test_index_route():
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Generate Melody" in resp.data

