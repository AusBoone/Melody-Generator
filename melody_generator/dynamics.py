"""Humanization helpers for MIDI events.

``humanize_events`` lightly randomises the ``time`` and ``velocity`` fields of
incoming MIDI messages so that playback does not sound overly mechanical. The
function mutates the provided messages in place and gracefully skips attributes
that are missing.
"""

from __future__ import annotations

import random
from typing import Iterable


def humanize_events(messages: Iterable) -> None:
    """Jitter ``time`` and ``velocity`` fields of ``messages``.

    Each MIDI message is modified individually so that subsequent playback has a
    more natural feel. ``time`` values are shifted by ±15 ticks while ``velocity``
    is adjusted by ±10 units, staying within the 1–127 MIDI range.
    """

    for msg in messages:
        # Each MIDI message is adjusted individually so playback feels less
        # mechanical. Only events with a positive delta time are modified.
        if hasattr(msg, "time") and msg.time > 0:
            jitter = random.randint(-15, 15)
            msg.time = max(0, msg.time + jitter)
        if hasattr(msg, "velocity") and msg.velocity is not None:
            vel_jitter = random.randint(-10, 10)
            msg.velocity = max(1, min(127, msg.velocity + vel_jitter))
