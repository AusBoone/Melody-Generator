import importlib
import sys
import types
import pytest

pytest.importorskip("flask")

# Stub mido and tkinter so the imports succeed
stub_mido = types.ModuleType("mido")
stub_mido.Message = lambda *a, **k: None
class DummyMidiFile:
    """Minimal MidiFile stub with a save method."""

    def __init__(self, *a, **k):
        self.tracks = []

    def save(self, _path):
        pass

stub_mido.MidiFile = DummyMidiFile
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


def test_invalid_timesig_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4",  # invalid
            "notes": "8",
            "motif_length": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_numerator_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "0/4",
            "notes": "8",
            "motif_length": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_negative_numerator_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "-3/4",
            "notes": "8",
            "motif_length": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_key_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "InvalidKey",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Invalid key selected" in resp.data


def test_motif_exceeds_notes_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "2",
            "motif_length": "4",
        },
    )
    assert b"Motif length cannot exceed" in resp.data


def test_invalid_chord_flash():
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C,Unknown",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Unknown chord" in resp.data

