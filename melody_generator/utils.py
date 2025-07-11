"""Utility helpers shared across Melody Generator components.

This module collects lightweight functions that do not fit in more
specific modules.  Each helper is carefully documented so both the CLI
and GUI can reuse the same validation logic without duplicating code.

Usage Example
-------------
>>> from melody_generator.utils import validate_time_signature
>>> validate_time_signature("3/4")
(3, 4)
"""

from __future__ import annotations

__all__ = ["validate_time_signature"]


def validate_time_signature(ts: str) -> tuple[int, int]:
    """Parse and validate a time signature string.

    Parameters
    ----------
    ts:
        Time signature in ``"NUM/DEN"`` form. Whitespace around the
        separator is ignored.

    Returns
    -------
    tuple[int, int]
        ``(numerator, denominator)`` when ``ts`` is valid.

    Raises
    ------
    ValueError
        If ``ts`` is malformed or uses an unsupported denominator.
    """

    # Accept input such as "4/4" or " 3 / 8 " by trimming whitespace
    parts = ts.strip().split("/")
    if len(parts) != 2:
        raise ValueError(
            "Time signature must be in the form 'numerator/denominator'."
        )

    try:
        numerator = int(parts[0])
        denominator = int(parts[1])
    except ValueError as exc:  # non-integer values
        raise ValueError(
            "Time signature must contain integer numerator and denominator."
        ) from exc

    # Restrict denominator to common simple meter values
    valid_denominators = {1, 2, 4, 8, 16}
    if numerator <= 0 or denominator not in valid_denominators:
        raise ValueError(
            "Time signature numerator must be > 0 and denominator one of 1, 2, 4, 8 or 16."
        )

    return numerator, denominator
