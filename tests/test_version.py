"""Simple version check for the package.

Verifies that the ``__version__`` attribute matches the expected release
string."""

import sys
import types
import importlib
from pathlib import Path

# Provide a minimal dummy 'mido' module so the script can be imported without the dependency
mido_stub = types.ModuleType('mido')
mido_stub.Message = object
mido_stub.MidiFile = object
mido_stub.MidiTrack = object
mido_stub.bpm2tempo = lambda bpm: bpm
mido_stub.MetaMessage = object
sys.modules['mido'] = mido_stub

# Provide a minimal stub for the 'tkinter' module so the import succeeds
tk_stub = types.ModuleType("tkinter")
tk_stub.filedialog = types.ModuleType("filedialog")
tk_stub.messagebox = types.ModuleType("messagebox")
tk_stub.ttk = types.ModuleType("ttk")
sys.modules.setdefault("tkinter", tk_stub)
sys.modules.setdefault("tkinter.filedialog", tk_stub.filedialog)
sys.modules.setdefault("tkinter.messagebox", tk_stub.messagebox)
sys.modules.setdefault("tkinter.ttk", tk_stub.ttk)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

melody_generator = importlib.import_module("melody_generator")


def test_version_matches():
    """Ensure ``melody_generator.__version__`` exposes the release version."""
    assert melody_generator.__version__ == "0.1.0"
