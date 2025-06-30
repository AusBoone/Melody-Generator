"""Entry point wrapper for ``python -m melody_generator``.

When the package is executed as a module the code here simply forwards
execution to :func:`melody_generator.main`.  Keeping the logic in a single
function means the behaviour is identical whether the user runs
``python -m melody_generator`` or the installed ``melody-generator``
console script.

Example
-------
The following invocation generates a short MIDI file from the command line::

    python -m melody_generator --key C --chords C,G,Am,F \
        --bpm 120 --timesig 4/4 --notes 16 --output song.mid
"""

# Reuse the package level ``main`` function so both ``python -m`` and the
# installed console script behave identically.
from . import main

if __name__ == "__main__":
    # Delegate execution to the package entry point
    main()
