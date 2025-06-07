"""Module used when executing ``python -m melody_generator``.

This file simply delegates to :func:`melody_generator.main` so that the
package can be launched as a script.  Keeping the logic in
``melody_generator.main`` allows the same entry point to be reused by the
installed ``melody-generator`` console script and during testing.
"""

from . import main

if __name__ == "__main__":
    main()
