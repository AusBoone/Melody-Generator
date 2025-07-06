"""Integration tests for the CLI and desktop GUI.

These tests exercise the package end to end while avoiding heavy optional
dependencies. ``mido`` and ``tkinter`` are replaced with lightweight stubs so
the CLI and GUI entry points can be imported without installing those
libraries. The tests then ensure that both user interfaces drive the core
melody generation code correctly and that any produced MIDI files have the
expected structure."""

import importlib
import os
import subprocess
import sys
from pathlib import Path
import types
import threading
import time
import pytest

def load_module():
    """Import ``melody_generator`` with dummy stand-ins for external modules.

    The package optionally depends on ``mido`` for MIDI writing and ``tkinter``
    for the desktop GUI. These tests supply lightweight replacements for those
    modules so that importing the package does not require the real
    dependencies, allowing the integration logic to be tested in isolation.
    """
    # Create minimal replacements for optional packages so the tests can run
    # without installing them.
    stub_mido = types.ModuleType("mido")
    class DummyMidiFile:
        last_instance = None
        def __init__(self, *a, **k):
            self.tracks = []
            DummyMidiFile.last_instance = self
        def save(self, path):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("midi")
    stub_mido.Message = lambda *a, **k: None
    stub_mido.MidiFile = DummyMidiFile
    stub_mido.MidiTrack = lambda *a, **k: []
    stub_mido.MetaMessage = lambda *a, **k: None
    stub_mido.bpm2tempo = lambda bpm: bpm

    tk_stub = types.ModuleType("tkinter")
    tk_stub.filedialog = types.ModuleType("filedialog")
    tk_stub.messagebox = types.ModuleType("messagebox")
    tk_stub.ttk = types.ModuleType("ttk")

    sys.modules["mido"] = stub_mido
    sys.modules.setdefault("tkinter", tk_stub)
    sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
    sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
    sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    if "melody_generator" in sys.modules:
        del sys.modules["melody_generator"]
    module = importlib.import_module("melody_generator")
    gui_module = importlib.import_module("melody_generator.gui")
    module.gui = gui_module
    return module, gui_module, DummyMidiFile


def test_random_helpers(monkeypatch):
    """Validate the random helper utilities used by the interfaces.

    ``generate_random_chord_progression`` should return only chords known to the
    library, while ``generate_random_rhythm_pattern`` must produce durations from
    the allowed set. The patched ``random.choice`` forces a repeated motif so we
    can also assert that some repetition logic is exercised."""
    mod, _, _ = load_module()
    chords = mod.generate_random_chord_progression("C", 4)
    assert len(chords) == 4
    for chord in chords:
        assert chord in mod.CHORDS

    orig_choice = mod.random.choice

    def choice(seq):
        if seq and isinstance(seq[0], list):
            return [0.25, 0, 0.25]
        return orig_choice(seq)

    monkeypatch.setattr(mod.random, "choice", choice)
    pattern = mod.generate_random_rhythm_pattern(6)
    allowed = {0.25, 0.5, 0.75, 0.125, 0.0625, 0}
    assert len(pattern) == 6 and all(p in allowed for p in pattern)
    assert 0 in pattern
    # Ensure a motif is repeated at least once in the returned pattern.
    repeated = any(
        pattern[:i] == pattern[i : 2 * i]
        for i in range(1, 4)
        if 2 * i <= len(pattern)
    )
    assert repeated


def test_harmony_and_counterpoint_intervals_and_tracks(tmp_path):
    """Verify harmony/counterpoint generation and MIDI track creation.

    The harmony line should maintain a fixed interval relative to the original
    melody. Counterpoint notes are checked against a whitelist of consonant
    intervals. Finally ``create_midi_file`` should place each extra line on its
    own track so the resulting ``MidiFile`` ends up with the expected number of
    tracks."""
    mod, _, DummyMidiFile = load_module()
    melody = ["C4", "D4", "E4", "F4"]
    harmony = mod.generate_harmony_line(melody, interval=4)
    for m, h in zip(melody, harmony):
        assert mod.note_to_midi(h) - mod.note_to_midi(m) == 4
    counter = mod.generate_counterpoint_melody(melody, "C")
    valid = {3, 4, 7, 8, 9, 12}
    for m, c in zip(melody, counter):
        assert abs(mod.note_to_midi(c) - mod.note_to_midi(m)) in valid
    out = tmp_path / "t.mid"
    mod.create_midi_file(
        melody,
        120,
        (4, 4),
        str(out),
        harmony=True,
        pattern=[0.25],
        extra_tracks=[harmony, counter],
    )
    mid = DummyMidiFile.last_instance
    assert mid is not None and len(mid.tracks) == 1 + 1 + 2


def test_negative_interval_harmony():
    """Harmony lines with negative intervals drop below the melody."""
    mod, _, _ = load_module()
    melody = ["G4", "A4", "B4"]
    harmony = mod.generate_harmony_line(melody, interval=-3)
    for m, h in zip(melody, harmony):
        assert mod.note_to_midi(h) - mod.note_to_midi(m) == -3


def test_cli_subprocess_creates_file(tmp_path):
    """Run the CLI entry point in a real subprocess.

    The command is executed with stubbed modules on the ``PYTHONPATH`` so that
    the ``melody_generator`` package can be imported without additional
    dependencies. Successful completion should create a MIDI file at the
    requested output path."""
    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    (stub_dir / "mido.py").write_text(
        """class MidiFile:\n    def __init__(self, *a, **k):\n        self.tracks=[]\n    def save(self, p):\n        open(p,'w').write('midi')\nclass MidiTrack(list):\n    pass\nclass Message:\n    def __init__(self,*a,**k):\n        pass\nclass MetaMessage:\n    def __init__(self,*a,**k):\n        pass\ndef bpm2tempo(bpm):\n    return bpm\n""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    # Point PYTHONPATH at our stub directory so the subprocess imports them
    env["PYTHONPATH"] = f"{stub_dir}:{env.get('PYTHONPATH','')}"
    output = tmp_path / "out.mid"
    # Execute the CLI in a subprocess to ensure the console script works end-to-end
    subprocess.run(
        [
            sys.executable,
            "-m",
            "melody_generator",
            "--key",
            "C",
            "--chords",
            "C,G,Am,F",
            "--bpm",
            "120",
            "--timesig",
            "4/4",
            "--notes",
            "8",
            "--base-octave",
            "4",
            "--include-chords",
            "--output",
            str(output),
        ],
        check=True,
        env=env,
    )
    assert output.exists()


def test_cli_accepts_lowercase(tmp_path):
    """Lowercase key and chord names should be accepted by the CLI."""

    stub_dir = tmp_path / "stubs"
    stub_dir.mkdir()
    (stub_dir / "mido.py").write_text(
        """class MidiFile:\n    def __init__(self,*a,**k):\n        self.tracks=[]\n    def save(self,p):\n        open(p,'w').write('midi')\nclass MidiTrack(list):\n    pass\nclass Message:\n    def __init__(self,*a,**k):\n        pass\nclass MetaMessage:\n    def __init__(self,*a,**k):\n        pass\ndef bpm2tempo(bpm):\n    return bpm\n""",
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{stub_dir}:{env.get('PYTHONPATH','')}"

    output = tmp_path / "lower.mid"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "melody_generator",
            "--key",
            "c",
            "--chords",
            "c,g,am,f",
            "--bpm",
            "120",
            "--timesig",
            "4/4",
            "--notes",
            "8",
            "--base-octave",
            "4",
            "--output",
            str(output),
        ],
        check=True,
        env=env,
    )
    assert output.exists()


def test_cli_lists_keys_and_exits(capsys):
    """``--list-keys`` should print the available keys and exit without errors."""
    mod, _, _ = load_module()
    argv = ["prog", "--list-keys"]
    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    captured = capsys.readouterr()
    sys.argv = old
    keys = "\n".join(sorted(mod.SCALE.keys())) + "\n"
    assert captured.out == keys


def test_cli_lists_chords_and_exits(capsys):
    """``--list-chords`` should print the available chords and exit."""
    mod, _, _ = load_module()
    argv = ["prog", "--list-chords"]
    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    captured = capsys.readouterr()
    sys.argv = old
    chords = "\n".join(sorted(mod.CHORDS.keys())) + "\n"
    assert captured.out == chords


def test_cli_enable_ml_and_style(tmp_path, monkeypatch):
    """``--enable-ml`` should load the sequence model and pass the style."""

    mod, _, _ = load_module()
    output = tmp_path / "out.mid"
    called = {}

    def fake_load(path, vocab):
        called["loaded"] = True
        return object()

    def gen_mel(*args, **kwargs):
        called["seq"] = kwargs.get("sequence_model")
        called["style"] = kwargs.get("style")
        return ["C4"]

    monkeypatch.setattr(mod, "load_sequence_model", fake_load)
    monkeypatch.setattr(mod, "generate_melody", gen_mel)
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "1",
        "--motif_length",
        "1",
        "--base-octave",
        "4",
        "--output",
        str(output),
        "--enable-ml",
        "--style",
        "jazz",
    ]
    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert called.get("loaded")
    assert called.get("seq") is not None
    assert called.get("style") == "jazz"


def test_generate_button_click(tmp_path, monkeypatch):
    """Simulate a user clicking the "Generate" button in the GUI.

    The test wires up a ``MelodyGeneratorGUI`` instance with stubbed callbacks
    and uses ``filedialog``/``messagebox`` replacements to avoid real user
    interaction. After invoking ``_generate_button_click`` a MIDI file should be
    written and confirmation dialogs shown."""
    mod, gui_mod, _ = load_module()
    out = tmp_path / "gui.mid"
    calls = {}

    def gen_mel(key, notes, chords, motif_length=4, base_octave=4, **kwargs):
        calls["oct"] = base_octave
        return ["C4"] * notes

    def create(mel, bpm, ts, path, harmony=False, pattern=None, extra_tracks=None, **kw):
        calls["args"] = (mel, bpm, ts, path, harmony, pattern, extra_tracks)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("midi")

    def harm(mel):
        return ["E4"] * len(mel)

    def cp(mel, key):
        return ["G4"] * len(mel)

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = gen_mel
    gui.create_midi_file = create
    gui.harmony_line_fn = harm
    gui.counterpoint_fn = cp
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 5)
    gui.instrument_var = types.SimpleNamespace(get=lambda: "Piano")
    gui.harmony_var = types.SimpleNamespace(get=lambda: True)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: True)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "1")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: True)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    lb = types.SimpleNamespace(
        curselection=lambda: (0, 1),
        get=lambda idx: ["C", "G"][idx],
    )
    gui.chord_listbox = lb
    gui.display_map = {"C": "C", "G": "G"}
    gui.sorted_chords = ["C", "G"]

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(out),
        raising=False,
    )
    # Capture any messagebox calls so we can assert on them later
    errs = []
    infos = []
    monkeypatch.setattr(
        mod.gui.messagebox,
        "showerror",
        lambda *a, **k: errs.append(a),
        raising=False,
    )
    monkeypatch.setattr(
        mod.gui.messagebox,
        "showinfo",
        lambda *a, **k: infos.append(a),
        raising=False,
    )
    monkeypatch.setattr(
        mod.gui.messagebox,
        "askyesno",
        lambda *a, **k: False,
        raising=False,
    )

    gui._generate_button_click()

    assert out.exists()
    assert not errs
    assert infos
    assert calls["args"][3] == str(out)
    assert len(calls["args"][6]) == 2
    assert calls["oct"] == 5


def test_generate_button_click_non_positive(tmp_path, monkeypatch):
    """Reject negative or zero values entered in the GUI.

    ``MelodyGeneratorGUI`` should validate that BPM, note count, motif length
    and harmony line counts are all positive integers. When invalid values are
    supplied the ``showerror`` dialog should be triggered instead of attempting
    to generate a melody."""
    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: []
    gui.create_midi_file = lambda *a, **k: None
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 0)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: -1)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "0")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: False)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    lb = types.SimpleNamespace(curselection=lambda: (0,), get=lambda idx: "C")
    gui.chord_listbox = lb
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]

    monkeypatch.setattr(gui_mod.filedialog, "asksaveasfilename", lambda **k: str(tmp_path / "x.mid"), raising=False)
    errs = []
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False)

    gui._generate_button_click()

    assert errs


def test_generate_button_click_invalid_denominator(tmp_path, monkeypatch):
    """Validate denominator checks for time signatures entered in the GUI.

    ``_generate_button_click`` should refuse to proceed when the denominator of
    the time signature is anything other than 1, 2, 4, 8 or 16. The test
    simulates user input of ``4/0`` and asserts that an error dialog appears."""
    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: []
    gui.create_midi_file = lambda *a, **k: None
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/0")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    lb = types.SimpleNamespace(curselection=lambda: (0,), get=lambda idx: "C")
    gui.chord_listbox = lb
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        mod.gui.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
    )

    gui._generate_button_click()

    assert errs


def test_generate_button_click_invalid_numerator(tmp_path, monkeypatch):
    """Reject numerator values outside the valid range in the GUI.

    The numerator must be a positive integer. By submitting ``0/4`` the test
    ensures ``_generate_button_click`` presents an error dialog instead of
    producing a MIDI file."""
    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: []
    gui.create_midi_file = lambda *a, **k: None
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "0/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    lb = types.SimpleNamespace(curselection=lambda: (0,), get=lambda idx: "C")
    gui.chord_listbox = lb
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        mod.gui.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
    )

    gui._generate_button_click()

    assert errs


def test_generate_button_click_motif_exceeds_notes(tmp_path, monkeypatch):
    """Handle motif lengths longer than the overall note count.

    ``_generate_button_click`` should reject user input when the motif length
    exceeds the total notes requested. The error dialog indicates to the user
    that the motif cannot be longer than the melody itself."""
    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: []
    gui.create_midi_file = lambda *a, **k: None
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 2)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "4")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    lb = types.SimpleNamespace(curselection=lambda: (0,), get=lambda idx: "C")
    gui.chord_listbox = lb
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        mod.gui.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
    )

    gui._generate_button_click()

    assert errs


def test_generate_button_click_invalid_base_octave(tmp_path, monkeypatch):
    """Out-of-range base octave values trigger an error dialog."""

    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: []
    gui.create_midi_file = lambda *a, **k: None
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 9)
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    lb = types.SimpleNamespace(curselection=lambda: (0,), get=lambda idx: "C")
    gui.chord_listbox = lb
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]

    monkeypatch.setattr(
        gui_mod.filedialog, "asksaveasfilename", lambda **k: str(tmp_path / "x.mid"), raising=False
    )
    errs = []
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False)

    gui._generate_button_click()

    assert errs


def test_cli_invalid_timesig_exits(tmp_path):
    """CLI should exit when the time signature is malformed.

    The argument ``--timesig`` expects ``NUM/DEN``. Supplying ``4`` triggers the
    parser's validation logic which exits with ``SystemExit``."""
    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4",  # missing denominator
        "--notes",
        "8",
        "--base-octave",
        "4",
        "--output",
        str(out),
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_cli_invalid_numerator_exits(tmp_path):
    """CLI exits when given an invalid time signature numerator.

    A numerator of ``0`` is not allowed, so ``run_cli`` should raise
    ``SystemExit`` during argument parsing."""
    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "0/4",
        "--notes",
        "8",
        "--base-octave",
        "4",
        "--output",
        str(out),
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_cli_non_positive_values_exit(tmp_path):
    """``run_cli`` rejects negative or zero numeric options.

    Both ``--bpm`` and ``--notes`` must be positive integers. Providing ``0``
    BPM and ``-1`` notes should cause the CLI to terminate with
    ``SystemExit``."""
    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "0",
        "--timesig",
        "4/4",
        "--notes",
        "-1",
        "--motif_length",
        "0",
        "--base-octave",
        "4",
        "--output",
        str(out),
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_cli_motif_exceeds_notes_exit(tmp_path):
    """Motif lengths longer than ``--notes`` should abort execution.

    Specifying a motif length of ``4`` when only ``2`` notes are requested
    should cause ``run_cli`` to raise ``SystemExit`` after argument validation."""
    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "2",
        "--motif_length",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_cli_invalid_instrument_number_exit(tmp_path):
    """Out-of-range instrument values should cause ``run_cli`` to exit."""

    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--instrument",
        "128",
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_cli_invalid_base_octave_exit(tmp_path):
    """``run_cli`` should exit when ``--base-octave`` is outside 0-8."""

    mod, _, _ = load_module()
    out = tmp_path / "bad.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--base-octave",
        "9",
        "--output",
        str(out),
    ]
    old = sys.argv
    sys.argv = argv
    with pytest.raises(SystemExit):
        mod.run_cli()
    sys.argv = old


def test_preview_button_uses_playback(monkeypatch, tmp_path):
    """``_preview_button_click`` should invoke the playback module."""

    mod, gui_mod, _ = load_module()

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: ["C4"] * 4
    gui.create_midi_file = lambda *a, **k: Path(a[3]).write_text("midi")
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.instrument_var = types.SimpleNamespace(get=lambda: "Piano")
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: False)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    gui.chord_listbox = types.SimpleNamespace(
        curselection=lambda: (0,), get=lambda idx: "C"
    )
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]
    gui.soundfont_var = types.SimpleNamespace(get=lambda: "")

    calls = {}

    stub_play = types.SimpleNamespace(play_midi=lambda path, soundfont=None: calls.setdefault("path", path))
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui, "messagebox", types.SimpleNamespace(showerror=lambda *a, **k: None), raising=False)

    gui._preview_button_click()

    assert "path" in calls


def test_preview_button_falls_back(monkeypatch, tmp_path):
    """Playback errors should trigger the fallback player."""

    mod, gui_mod, _ = load_module()

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: ["C4"] * 4
    gui.create_midi_file = lambda *a, **k: Path(a[3]).write_text("midi")
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.instrument_var = types.SimpleNamespace(get=lambda: "Piano")
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: False)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    gui.chord_listbox = types.SimpleNamespace(
        curselection=lambda: (0,), get=lambda idx: "C"
    )
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]
    gui.soundfont_var = types.SimpleNamespace(get=lambda: "")

    def raise_err(_p, soundfont=None):
        raise gui_mod.MidiPlaybackError("boom")

    stub_play = types.SimpleNamespace(play_midi=raise_err)
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    calls = {}
    monkeypatch.setattr(gui, "_open_default_player", lambda p, delete_after=False: calls.setdefault("fallback", p))

    gui._preview_button_click()

    assert "fallback" in calls


def test_preview_file_removed(monkeypatch, tmp_path):
    """Temporary preview MIDI files should be deleted after playback."""

    mod, gui_mod, _ = load_module()

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: ["C4"] * 4
    gui.create_midi_file = lambda *a, **k: Path(a[3]).write_text("midi")
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.instrument_var = types.SimpleNamespace(get=lambda: "Piano")
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: False)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    gui.chord_listbox = types.SimpleNamespace(
        curselection=lambda: (0,), get=lambda idx: "C"
    )
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]
    gui.soundfont_var = types.SimpleNamespace(get=lambda: "")

    calls = {}
    stub_play = types.SimpleNamespace(
        play_midi=lambda path, soundfont=None: calls.setdefault("path", path)
    )
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(gui, "_open_default_player", lambda p, delete_after=False: Path(p).unlink())

    gui._preview_button_click()

    path = calls["path"]
    assert not os.path.exists(path)


def test_preview_file_waits_for_player(monkeypatch):
    """Preview file should remain until the player thread cleans up."""

    mod, gui_mod, _ = load_module()

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.generate_melody = lambda *a, **k: ["C4"] * 4
    gui.create_midi_file = lambda *a, **k: Path(a[3]).write_text("midi")
    gui.harmony_line_fn = None
    gui.counterpoint_fn = None
    gui.save_settings = None
    gui.rhythm_pattern = None
    gui.ml_var = types.SimpleNamespace(get=lambda: False)
    gui.style_var = types.SimpleNamespace(get=lambda: "")
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 4)
    gui.instrument_var = types.SimpleNamespace(get=lambda: "Piano")
    gui.harmony_var = types.SimpleNamespace(get=lambda: False)
    gui.counterpoint_var = types.SimpleNamespace(get=lambda: False)
    gui.harmony_lines = types.SimpleNamespace(get=lambda: "0")
    gui.include_chords_var = types.SimpleNamespace(get=lambda: False)
    gui.chords_same_var = types.SimpleNamespace(get=lambda: False)
    gui.chord_listbox = types.SimpleNamespace(
        curselection=lambda: (0,), get=lambda idx: "C"
    )
    gui.display_map = {"C": "C"}
    gui.sorted_chords = ["C"]
    gui.soundfont_var = types.SimpleNamespace(get=lambda: "")

    def raise_err(_p, soundfont=None):
        raise gui_mod.MidiPlaybackError("boom")

    stub_play = types.SimpleNamespace(play_midi=raise_err)
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)

    calls = {}

    def fake_player(path, delete_after=False):
        calls["path"] = path
        def worker():
            time.sleep(0.05)
            if delete_after:
                Path(path).unlink()
        threading.Thread(target=worker, daemon=True).start()

    monkeypatch.setattr(gui, "_open_default_player", fake_player)

    gui._preview_button_click()

    tmp = Path(calls["path"])
    assert tmp.exists()
    time.sleep(0.06)
    assert not tmp.exists()


def test_cli_play_flag_invokes_playback(monkeypatch, tmp_path):
    """Providing ``--play`` should call ``playback.play_midi``."""

    mod, _, _ = load_module()
    out = tmp_path / "x.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--motif_length",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--play",
    ]

    calls = {}
    stub_play = types.SimpleNamespace(
        play_midi=lambda p, **kw: calls.setdefault("play", (p, kw.get("soundfont")))
    )
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(mod, "playback", stub_play, raising=False)

    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert calls.get("play") == (str(out), None)


def test_cli_play_flag_falls_back(monkeypatch, tmp_path):
    """Errors during playback should use the system default player."""

    mod, _, _ = load_module()
    out = tmp_path / "y.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--motif_length",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--play",
    ]

    def raise_err(_p):
        raise RuntimeError("boom")

    stub_play = types.SimpleNamespace(play_midi=raise_err)
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(mod, "playback", stub_play, raising=False)
    calls = {}
    monkeypatch.setattr(mod, "_open_default_player", lambda p, delete_after=False: calls.setdefault("fallback", p))

    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert calls.get("fallback") == str(out)


def test_cli_soundfont_forwarded(monkeypatch, tmp_path):
    """``--soundfont`` should be passed to ``playback.play_midi``."""

    mod, _, _ = load_module()
    out = tmp_path / "sf.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--play",
        "--soundfont",
        "custom.sf2",
    ]

    calls = {}
    stub_play = types.SimpleNamespace(
        play_midi=lambda p, soundfont=None: calls.setdefault("args", (p, soundfont))
    )
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(mod, "playback", stub_play, raising=False)

    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert calls.get("args") == (str(out), "custom.sf2")


def test_cli_soundfont_without_play(monkeypatch, tmp_path):
    """Providing ``--soundfont`` alone should not invoke playback."""

    mod, _, _ = load_module()
    out = tmp_path / "sf.mid"
    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--soundfont",
        "custom.sf2",
    ]

    calls = {}
    stub_play = types.SimpleNamespace(play_midi=lambda *a, **k: calls.setdefault("called", True))
    monkeypatch.setitem(sys.modules, "melody_generator.playback", stub_play)
    monkeypatch.setattr(mod.gui.messagebox, "showerror", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(mod, "playback", stub_play, raising=False)

    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert "called" not in calls
    assert out.exists()


def test_open_default_player_error_threadsafe(monkeypatch):
    """Errors opening the default player should invoke ``showerror`` via ``after``."""

    mod, gui_mod, _ = load_module()
    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)

    calls = []
    gui.root = types.SimpleNamespace(after=lambda d, func, *a: calls.append((func, a)))

    monkeypatch.setattr(gui_mod.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(gui_mod.os, "environ", {})
    monkeypatch.setattr(gui_mod.sys, "platform", "linux", raising=False)
    errors = []
    monkeypatch.setattr(
        gui_mod.messagebox,
        "showerror",
        lambda *a, **k: errors.append(a),
        raising=False,
    )

    class DummyThread:
        def __init__(self, target, daemon=False):
            self.target = target
        def start(self):
            self.target()

    monkeypatch.setattr(gui_mod.threading, "Thread", DummyThread)

    gui._open_default_player("foo.mid")

    # Simulate Tkinter mainloop processing scheduled callbacks
    for func, args in calls:
        func(*args)

    assert errors


def test_open_default_player_waits_linux(monkeypatch, tmp_path):
    """File deletion should occur only after the player exits on Linux."""

    mod, _, _ = load_module()
    midi = tmp_path / "x.mid"
    midi.write_text("data")

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        time.sleep(0.05)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setattr(mod.os, "environ", {})
    monkeypatch.setattr(mod.sys, "platform", "linux", raising=False)

    mod._open_default_player(str(midi), delete_after=True)
    assert midi.exists()
    time.sleep(0.06)
    assert not midi.exists()
    assert calls and "--wait" in calls[0]


def test_gui_open_default_player_waits_linux(monkeypatch, tmp_path):
    """GUI preview should delay deletion until the player exits on Linux."""

    _, gui_mod, _ = load_module()
    midi = tmp_path / "x.mid"
    midi.write_text("data")

    calls = []

    def fake_run(cmd, check=False):
        calls.append(cmd)
        time.sleep(0.05)
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(gui_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(gui_mod.os, "environ", {})
    monkeypatch.setattr(gui_mod.sys, "platform", "linux", raising=False)

    gui = gui_mod.MelodyGeneratorGUI.__new__(gui_mod.MelodyGeneratorGUI)
    gui.root = types.SimpleNamespace()
    gui._open_default_player(str(midi), delete_after=True)
    assert midi.exists()
    time.sleep(0.06)
    assert not midi.exists()
    assert calls and "--wait" in calls[0]


def test_cli_random_rhythm_passed(monkeypatch, tmp_path):
    """``--random-rhythm`` should forward the pattern to all helpers."""

    mod, _, _ = load_module()
    out = tmp_path / "rr.mid"

    argv = [
        "prog",
        "--key",
        "C",
        "--chords",
        "C,G",
        "--bpm",
        "120",
        "--timesig",
        "4/4",
        "--notes",
        "4",
        "--motif_length",
        "2",
        "--base-octave",
        "4",
        "--output",
        str(out),
        "--random-rhythm",
    ]

    captured = {}

    def stub_pattern(n=3):
        captured["length"] = n
        return [0.25] * n

    monkeypatch.setattr(mod, "generate_random_rhythm_pattern", stub_pattern)

    def gen_mel(*a, **kw):
        captured["pattern"] = kw.get("pattern")
        return ["C4"] * 4

    def create(_mel, _bpm, _ts, path, *, pattern=None, **_kw):
        captured["create"] = pattern
        path_obj = Path(path)
        path_obj.write_text("midi")

    monkeypatch.setattr(mod, "generate_melody", gen_mel)
    monkeypatch.setattr(mod, "create_midi_file", create)

    old = sys.argv
    sys.argv = argv
    mod.run_cli()
    sys.argv = old

    assert captured["length"] == 4
    assert captured["pattern"] == [0.25] * 4
    assert captured["create"] == [0.25] * 4
