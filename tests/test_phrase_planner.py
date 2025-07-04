"""Unit tests for the phrase planning helpers."""

import sys
from pathlib import Path
import types
import importlib
import pytest

# Stub out the 'mido' and 'tkinter' modules so ``melody_generator`` imports
# succeed without the real dependencies.
stub_mido = types.ModuleType("mido")
stub_mido.Message = object
stub_mido.MidiFile = object
stub_mido.MidiTrack = list
stub_mido.MetaMessage = lambda *args, **kwargs: object()
stub_mido.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", stub_mido)

tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

phrase_module = importlib.import_module("melody_generator.phrase_planner")
PhrasePlan = phrase_module.PhrasePlan
generate_phrase_plan = phrase_module.generate_phrase_plan
generate_melody = importlib.import_module("melody_generator").generate_melody
PhrasePlanner = phrase_module.PhrasePlanner


def test_generate_phrase_plan_basic():
    """Generated plans contain the requested number of tension values."""
    plan = generate_phrase_plan(8, base_octave=3)
    assert isinstance(plan, PhrasePlan)
    assert plan.length == 8
    assert len(plan.tension_profile) == 8
    assert plan.pitch_range == (3, 5)


def test_generate_phrase_plan_invalid_inputs():
    """Invalid arguments should raise ``ValueError``."""
    with pytest.raises(ValueError):
        generate_phrase_plan(0, 4)
    with pytest.raises(ValueError):
        generate_phrase_plan(4, 4, pitch_span=-1)


def test_melody_respects_phrase_plan():
    """``generate_melody`` honours the ``pitch_range`` from a plan."""
    chords = ["C", "G"]
    plan = generate_phrase_plan(8, base_octave=2)
    mel = generate_melody("C", 8, chords, motif_length=4, base_octave=4, phrase_plan=plan)
    assert {int(n[-1]) for n in mel}.issubset(set(range(2, 5)))


def test_plan_skeleton_selects_peaks_and_ends():
    """``PhrasePlanner.plan_skeleton`` should mark boundaries and tension peaks."""
    planner = PhrasePlanner()
    chords = ["C", "G", "Am", "F"]
    tension = [0.1, 0.5, 1.0, 0.2]
    skeleton = planner.plan_skeleton(chords, tension)
    assert skeleton == [(0, "C"), (2, "A"), (3, "F")]


def test_infill_skeleton_repeats_motif():
    """Motif should fill the gaps between skeleton anchor notes."""
    planner = PhrasePlanner()
    skeleton = [(0, "C"), (2, "G"), (4, "C")]
    melody = planner.infill_skeleton(skeleton, ["D", "E"])
    assert melody == ["C", "D", "G", "E", "C"]



