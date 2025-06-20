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


def test_generate_button_click(tmp_path, monkeypatch):
    """Simulate a user clicking the "Generate" button in the GUI.

    The test wires up a ``MelodyGeneratorGUI`` instance with stubbed callbacks
    and uses ``filedialog``/``messagebox`` replacements to avoid real user
    interaction. After invoking ``_generate_button_click`` a MIDI file should be
    written and confirmation dialogs shown."""
    mod, gui_mod, _ = load_module()
    out = tmp_path / "gui.mid"
    calls = {}

    def gen_mel(key, notes, chords, motif_length=4, base_octave=4):
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
    gui.key_var = types.SimpleNamespace(get=lambda: "C")
    gui.bpm_var = types.SimpleNamespace(get=lambda: 120)
    gui.timesig_var = types.SimpleNamespace(get=lambda: "4/4")
    gui.notes_var = types.SimpleNamespace(get=lambda: 4)
    gui.motif_entry = types.SimpleNamespace(get=lambda: "2")
    gui.base_octave_var = types.SimpleNamespace(get=lambda: 5)
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
        gui_mod.messagebox,
        "showerror",
        lambda *a, **k: errs.append(a),
        raising=False,
    )
    monkeypatch.setattr(
        gui_mod.messagebox,
        "showinfo",
        lambda *a, **k: infos.append(a),
        raising=False,
    )
    monkeypatch.setattr(
        gui_mod.messagebox,
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

    monkeypatch.setattr(gui_mod.filedialog, "asksaveasfilename", lambda **k: str(tmp_path / "x.mid"), raising=False)
    errs = []
    monkeypatch.setattr(gui_mod.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False)

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

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        gui_mod.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
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

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        gui_mod.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
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

    monkeypatch.setattr(
        gui_mod.filedialog,
        "asksaveasfilename",
        lambda **k: str(tmp_path / "x.mid"),
        raising=False,
    )
    errs = []
    monkeypatch.setattr(
        gui_mod.messagebox, "showerror", lambda *a, **k: errs.append(a), raising=False
    )

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
