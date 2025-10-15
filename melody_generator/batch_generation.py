"""Parallel melody generation helpers.

Modification summary
--------------------
* Expanded module documentation with design notes describing worker model and
  assumptions.
* Added ``generate_batch_async`` and supporting helpers so large exports can be
  dispatched to Celery workers when the optional dependency is installed. The
  asynchronous path validates configuration eagerly and reuses a lazily
  registered task to avoid repeatedly decorating the same function.

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

Design Notes
------------
``generate_batch`` is intentionally lightweight. It avoids custom process
management and simply proxies arguments to :func:`generate_melody` in worker
processes. The function assumes each configuration dictionary contains valid
keys for ``generate_melody`` and raises ``ValueError`` if ``workers`` is
non-positive.
"""

from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, Iterable, List, Optional

from . import generate_melody

# Celery is optional; when it is unavailable the synchronous ``generate_batch``
# helper remains the only entry point and callers attempting to use the
# asynchronous API receive a descriptive ``RuntimeError``.
try:  # pragma: no cover - Celery is not required for unit tests
    from celery import Celery
except Exception:  # pragma: no cover - optional dependency missing
    Celery = None  # type: ignore

# ``celery_app`` stores the application configured via ``configure_celery`` so
# subsequent calls to :func:`generate_batch_async` can reuse the same task
# registration without requiring each caller to supply the app explicitly.
celery_app: Optional["Celery"] = None

# Name used when registering the Celery task. Exposing it as a constant keeps the
# test double in sync with the production code and prevents subtle typos when
# checking ``app.tasks``.
_CELERY_TASK_NAME = "melody_generator.batch_generation.generate_batch"

# Cache of the lazily registered Celery task so repeated asynchronous dispatches
# avoid re-decorating the same function. The ``None`` sentinel indicates the task
# has not yet been created for the configured app.
_celery_task = None


def _generate_single(kwargs: Dict[str, Any]) -> List[str]:
    """Wrapper used by worker processes to generate one melody."""

    return generate_melody(**kwargs)


def generate_batch(
    configs: Iterable[Dict[str, Any]], *, workers: Optional[int] = None
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


def configure_celery(app: "Celery") -> None:
    """Register the Celery application used for asynchronous batch exports.

    Parameters
    ----------
    app:
        Configured Celery application. The caller is responsible for providing
        a broker and (optionally) a result backend. The function stores the app
        globally so :func:`generate_batch_async` can reuse the same instance.

    Notes
    -----
    Passing a new application replaces the previously stored one and clears the
    cached task so the next asynchronous call re-registers itself with the
    updated app. This makes it safe to call ``configure_celery`` during tests or
    when reloading configuration at runtime.
    """

    global celery_app, _celery_task
    celery_app = app
    _celery_task = None  # Force lazy re-registration for the new application.


def _ensure_celery_task(app: "Celery"):
    """Return the Celery task object used for asynchronous generation.

    The task is registered lazily so importing this module does not attempt to
    create Celery applications during unit tests or environments where the
    dependency is absent. When the task already exists it is returned directly;
    otherwise a new task wrapping :func:`_generate_batch_serial` is registered.
    """

    global _celery_task
    if _celery_task is not None:
        return _celery_task

    # If the application already has a task registered under the expected name
    # reuse it. This allows callers to pre-register their own implementation
    # while still using the helper to dispatch work.
    if hasattr(app, "tasks") and _CELERY_TASK_NAME in getattr(app, "tasks"):
        _celery_task = app.tasks[_CELERY_TASK_NAME]
        return _celery_task

    @_wrap_celery_task(app)
    def task(configs: List[Dict[str, Any]]) -> List[List[str]]:
        return _generate_batch_serial(configs)

    _celery_task = task
    return _celery_task


def _wrap_celery_task(app: "Celery"):
    """Return a decorator that registers ``func`` as a Celery task.

    A small indirection keeps :func:`_ensure_celery_task` readable and allows
    the decorator to be defined even when Celery is replaced with a stub object
    during tests. The returned wrapper mirrors :meth:`Celery.task` without
    depending on Celery internals, making the behaviour easy to simulate.
    """

    def decorator(func):
        return app.task(name=_CELERY_TASK_NAME)(func)

    return decorator


def _generate_batch_serial(configs: Iterable[Dict[str, Any]]) -> List[List[str]]:
    """Serial helper used by Celery workers to generate melodies.

    Celery workers typically process requests one at a time. Spawning additional
    process pools within those workers would waste resources, so the task simply
    iterates over the configuration list and calls :func:`_generate_single` for
    each entry.
    """

    return [_generate_single(cfg) for cfg in configs]


def generate_batch_async(
    configs: Iterable[Dict[str, Any]],
    *,
    countdown: Optional[int] = None,
    celery_app: Optional["Celery"] = None,
):
    """Dispatch ``configs`` to a Celery worker for asynchronous generation.

    Parameters
    ----------
    configs:
        Iterable of configuration dictionaries accepted by
        :func:`melody_generator.generate_melody`.
    countdown:
        Optional delay in seconds before Celery executes the task. ``None``
        submits the job immediately. Values must be non-negative.
    celery_app:
        Specific Celery application to use. When omitted the application
        previously supplied via :func:`configure_celery` is used.

    Returns
    -------
    celery.result.AsyncResult
        Handle allowing callers to wait for completion or inspect progress. The
        return type depends on the Celery version but always implements
        ``get()``.

    Raises
    ------
    RuntimeError
        If Celery is unavailable or no application has been configured.
    ValueError
        If ``countdown`` is negative.
    """

    if Celery is None:
        raise RuntimeError(
            "Celery is required for generate_batch_async; install the dependency to use this feature."
        )

    if countdown is not None and countdown < 0:
        raise ValueError("countdown must be None or non-negative")

    app = celery_app or globals().get("celery_app")
    if app is None:
        raise RuntimeError(
            "No Celery app configured. Call configure_celery() or pass the app explicitly."
        )

    task = _ensure_celery_task(app)
    config_list = [dict(cfg) for cfg in configs]
    apply_kwargs = {"args": [config_list], "kwargs": {}}
    if countdown is not None:
        apply_kwargs["countdown"] = countdown
    return task.apply_async(**apply_kwargs)
