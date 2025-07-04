"""Humanization helpers for MIDI events."""

from __future__ import annotations

import random
from typing import Iterable


def humanize_events(messages: Iterable) -> None:
    """Apply micro timing offsets and velocity variation in place."""

    for msg in messages:
        if hasattr(msg, "time") and msg.time > 0:
            jitter = random.randint(-15, 15)
            msg.time = max(0, msg.time + jitter)
