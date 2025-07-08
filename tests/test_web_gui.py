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


def test_invalid_instrument_flash():
    """Posting an instrument not in ``INSTRUMENTS`` shows an error."""

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
            "instrument": "Banjo",
        },
    )

    assert b"Unknown instrument" in resp.data


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


def test_lowercase_inputs(monkeypatch):
    """Form values in lowercase should still be processed correctly."""

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
            "key": "c",
            "chords": "c,am",
            "bpm": "120",
            "timesig": "4/4",
            "notes": "1",
            "motif_length": "1",
            "base_octave": "4",
        },
    )

    assert resp.status_code == 200 and b"audio/wav" in resp.data


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


def test_enable_ml_missing_dependency(monkeypatch):
    """Enabling ML without PyTorch should flash an error message."""

    client = app.test_client()

    monkeypatch.setattr(web_gui, "create_midi_file", lambda *a, **k: None)

    def raise_dep(*_a, **_k):
        raise RuntimeError("PyTorch is required")

    monkeypatch.setattr(web_gui, "load_sequence_model", raise_dep)

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
            "enable_ml": "1",
        },
    )

    assert resp.status_code == 200
    assert b"PyTorch is required" in resp.data



def test_generation_dispatched_to_celery(monkeypatch):
    """When Celery is available ``index`` should send work to a task."""
    celery_mod = types.ModuleType("celery")
    called = {}

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, **kwargs):
            """Capture keyword arguments supplied to ``delay`` for assertion."""
            called["kwargs"] = kwargs

            class Res:
                def get(self, timeout=None):
                    return ("", "")

            return Res()

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            called["task"] = True
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    client = gui.app.test_client()

    monkeypatch.setattr(gui, "_generate_preview", lambda **kw: ("", ""))

    client.post(
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

    assert called.get("task")
    assert called["kwargs"]["key"] == "C"
    assert called["kwargs"]["bpm"] == 120
    assert called["kwargs"]["notes"] == 1


def test_delay_arguments_match_preview_parameters(monkeypatch):
    """Ensure ``delay`` receives only keyword arguments matching preview params."""

    # Capture all arguments passed to ``delay`` for later inspection.
    called = {}

    celery_mod = types.ModuleType("celery")

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, *args, **kwargs):
            """Record positional and keyword arguments supplied by ``index``."""
            called["args"] = args
            called["kwargs"] = kwargs

            class Res:
                def get(self, timeout=None):
                    return ("", "")

            return Res()

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            called["task"] = True
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    client = gui.app.test_client()

    # Avoid heavy processing during the test by stubbing the actual generator.
    monkeypatch.setattr(gui, "_generate_preview", lambda **kw: ("", ""))

    client.post(
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

    expected_params = {
        "key": "C",
        "bpm": 120,
        "timesig": (4, 4),
        "notes": 1,
        "motif_length": 1,
        "base_octave": 4,
        "instrument": "Piano",
        "harmony": False,
        "random_rhythm": False,
        "counterpoint": False,
        "harmony_lines": 0,
        "include_chords": False,
        "chords_same": False,
        # The web GUI forwards the humanize option to ``create_midi_file``.
        # When the checkbox is unchecked the default ``False`` should be sent.
        "humanize": False,
        "enable_ml": False,
        "style": None,
        "chords": ["C"],
    }

    assert called.get("task")
    assert called.get("args") == ()
    assert called.get("kwargs") == expected_params


def test_celery_failure_falls_back_to_sync(monkeypatch):
    """Preview generation should continue if the Celery broker is unreachable."""

    celery_mod = types.ModuleType("celery")
    called = {}

    class DummyTask:
        def __init__(self, fn):
            self.fn = fn

        def delay(self, **_kw):
            """Simulate a broker connection error when dispatching."""
            called["delay"] = True
            raise RuntimeError("broker unreachable")

    class DummyCelery:
        def __init__(self, *a, **k):
            pass

        def task(self, fn):
            return DummyTask(fn)

    celery_mod.Celery = DummyCelery
    monkeypatch.setitem(sys.modules, "celery", celery_mod)

    gui = importlib.reload(importlib.import_module("melody_generator.web_gui"))
    client = gui.app.test_client()

    called_sync = {}

    def fake_preview(**_kw):
        called_sync["called"] = True
        return "", ""

    monkeypatch.setattr(gui, "_generate_preview", fake_preview)

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
    assert called.get("delay")
    assert called_sync.get("called")


def test_random_rhythm_length_matches_notes(monkeypatch):
    """Random rhythm option should produce a pattern equal to the note count."""

    captured = {}

    # Stub heavy generation functions to keep the test fast and predictable.
    monkeypatch.setattr(web_gui, "generate_melody", lambda *a, **k: ["C4"] * 4)

    def fake_pattern(n):
        captured["length"] = n
        return [0.25] * n

    monkeypatch.setattr(web_gui, "generate_random_rhythm_pattern", fake_pattern)

    def fake_create(mel, bpm, ts, path, *, pattern=None, **_kw):
        captured["pattern"] = pattern
        Path(path).write_text("midi")

    monkeypatch.setattr(web_gui, "create_midi_file", fake_create)
    monkeypatch.setattr(web_gui.playback, "render_midi_to_wav", lambda *a, **k: None)

    web_gui._generate_preview(
        key="C",
        bpm=120,
        timesig=(4, 4),
        notes=4,
        motif_length=2,
        base_octave=4,
        instrument="Piano",
        harmony=False,
        random_rhythm=True,
        counterpoint=False,
        harmony_lines=0,
        include_chords=False,
        chords_same=False,
        enable_ml=False,
        style=None,
        chords=["C"],
        humanize=False,
    )

    assert captured.get("length") == 4
    assert captured.get("pattern") == [0.25] * 4
