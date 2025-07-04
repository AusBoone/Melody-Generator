"""Tests ensuring lru_cache decoration of helpers."""

import importlib
import sys
import types
from pathlib import Path

# Stub dependencies so ``melody_generator`` imports without optional packages
mido_stub = types.ModuleType("mido")
mido_stub.Message = object
mido_stub.MidiFile = object
mido_stub.MidiTrack = list
mido_stub.MetaMessage = lambda *a, **kw: object()
mido_stub.bpm2tempo = lambda bpm: bpm
sys.modules.setdefault("mido", mido_stub)

# Stub minimal tkinter
tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

mod = importlib.import_module("melody_generator")


def test_canonical_key_cache_hits():
    """Repeated canonical_key calls should register cache hits."""
    info_before = mod.canonical_key.cache_info()
    mod.canonical_key("C")
    mod.canonical_key("C")
    info_after = mod.canonical_key.cache_info()
    assert info_after.hits >= info_before.hits + 1


def test_canonical_chord_cache_hits():
    """Repeated canonical_chord calls should register cache hits."""
    info_before = mod.canonical_chord.cache_info()
    mod.canonical_chord("Dm")
    mod.canonical_chord("Dm")
    info_after = mod.canonical_chord.cache_info()
    assert info_after.hits >= info_before.hits + 1
