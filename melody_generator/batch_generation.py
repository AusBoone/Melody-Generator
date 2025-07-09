"""Parallel melody generation helpers.

This module provides a small convenience function for producing many
melodies concurrently. It offloads each generation call to a worker
process via :class:`concurrent.futures.ProcessPoolExecutor` so CPU bound
work scales with the number of available cores.

Example
-------
>>> configs = [
...     {"key": "C", "notes": 8, "chords": ["C", "G"], "motif_length": 4},
...     {"key": "Dm", "notes": 8, "chords": ["Dm", "A"], "motif_length": 4},
... ]
>>> generate_batch(configs, workers=2)
[["C4", "E4", ...], ["D4", "F4", ...]]
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Iterable, List, Dict, Any

from . import generate_melody


def _generate_single(kwargs: Dict[str, Any]) -> List[str]:
    """Wrapper used by worker processes to generate one melody."""

    return generate_melody(**kwargs)


def generate_batch(
    configs: Iterable[Dict[str, Any]], *, workers: int | None = None
) -> List[List[str]]:
    """Generate multiple melodies in parallel.

    Parameters
    ----------
    configs:
        Iterable of argument dictionaries accepted by :func:`generate_melody`.
    workers:
        Optional number of worker processes. When ``None`` the CPU count is
        used. ``1`` disables multiprocessing and runs serially. ``ValueError``
        is raised when ``workers`` is ``0`` or a negative value so callers
        receive immediate feedback about invalid input.

    Returns
    -------
    List[List[str]]
        Each generated melody as a list of note strings.
    """

    cfg_list = list(configs)
    if workers is not None and workers <= 0:
        # ``0`` and negative counts are nonsensical. Reject them early so
        # callers do not mistakenly spawn an empty process pool or expect
        # automatic CPU detection.
        raise ValueError("workers must be positive")
    if workers is None:
        workers = os.cpu_count() or 1
    if workers <= 1:
        # Fall back to a simple list comprehension so unit tests run without
        # spawning subprocesses.
        return [_generate_single(cfg) for cfg in cfg_list]

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_generate_single, cfg) for cfg in cfg_list]
        return [f.result() for f in futs]
