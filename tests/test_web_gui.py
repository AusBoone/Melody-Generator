"""Tests for the Flask based web GUI.

The web interface exposes the same melody generation functionality as the
desktop application. These tests post various form values to the Flask app and
verify that invalid input is rejected and valid input renders correctly."""

import importlib
import sys
import types
from pathlib import Path
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
    """Verify that the index page renders successfully."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Generate Melody" in resp.data


def test_invalid_timesig_flash():
    """Submitting an invalid time signature triggers a flash message."""
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
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_numerator_flash():
    """Numerator outside the valid range triggers an error flash."""
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
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_negative_numerator_flash():
    """Negative numerators result in an error flash."""
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
            "base_octave": "4",
        },
    )
    assert b"Time signature must be" in resp.data


def test_invalid_key_flash():
    """Posting an unknown musical key returns an error message."""
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
            "base_octave": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Invalid key selected" in resp.data


def test_motif_exceeds_notes_flash():
    """Motif lengths longer than the note count flash an error."""
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
            "base_octave": "4",
        },
    )
    assert b"Motif length cannot exceed" in resp.data


def test_invalid_base_octave_flash():
    """Out-of-range ``base_octave`` values return an error flash."""

    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "9",
        },
    )
    assert b"Base octave must be" in resp.data


def test_invalid_chord_flash():
    """Unknown chords in the form post return an error flash."""
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
            "base_octave": "4",
        },
    )
    assert resp.status_code == 200
    assert b"Unknown chord" in resp.data


def test_include_chords_flag():
    """Setting the ``include_chords`` checkbox should be accepted."""
    client = app.test_client()
    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "8",
            "motif_length": "4",
            "base_octave": "4",
            "include_chords": "1",
            "chords_same": "1",
        },
    )
    assert resp.status_code == 200


def test_successful_post_returns_audio(monkeypatch):
    """Valid form submissions embed a WAV audio preview."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)
    monkeypatch.setattr(
        web_gui.playback,
        "render_midi_to_wav",
        lambda mid, wav, soundfont=None: Path(wav).write_bytes(b"wav"),
    )

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
        },
    )
    assert b"audio/wav" in resp.data


def test_playback_failure_flash(monkeypatch):
    """Failed audio rendering notifies the user via flash message."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    def raise_error(_mid, _wav, soundfont=None):
        raise web_gui.MidiPlaybackError("no synth")

    monkeypatch.setattr(web_gui.playback, "render_midi_to_wav", raise_error)

    resp = client.post(
        "/",
        data={
            "key": "C",
            "chords": "C",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
        },
    )

    assert resp.status_code == 200
    assert b"Preview audio could not be generated" in resp.data

