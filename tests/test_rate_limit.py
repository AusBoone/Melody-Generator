"""Rate limiter tests for the Flask web interface.

Alongside the baseline behaviour, these tests ensure configuration errors do
not inadvertently throttle legitimate requests. When the limit is missing or
malformed, the helper should disable throttling and emit a warning instead of
returning HTTP 429 responses. This matches the project's emphasis on clear
operator feedback without sacrificing usability.
"""

import threading
import logging

import test_web_gui as web_gui_tests

# Reuse the already configured Flask app and imported ``web_gui`` module from
# ``test_web_gui``. That module stubs external dependencies and sets required
# environment variables, so importing it here provides a fully initialized
# application instance suitable for exercising the rate limiter.
web_gui = web_gui_tests.web_gui
app = web_gui_tests.app


def setup_function() -> None:
    """Ensure each test runs with a fresh request log."""
    web_gui.REQUEST_LOG.clear()


def test_rate_limit_enforces_limit() -> None:
    """Requests beyond the configured threshold should return HTTP 429."""
    app.config["RATE_LIMIT_PER_MINUTE"] = 1
    client = app.test_client()
    first = client.get("/")
    assert first.status_code == 200
    # Successful requests should not include throttling headers.
    assert "Retry-After" not in first.headers

    second = client.get("/")
    assert second.status_code == 429
    # The rejection must advise the client when to retry.
    assert "Retry-After" in second.headers
    assert int(second.headers["Retry-After"]) > 0


def test_rate_limit_purges_expired_entries() -> None:
    """Entries older than the current window are removed before counting."""
    app.config["RATE_LIMIT_PER_MINUTE"] = 5
    old_time = web_gui.monotonic() - (web_gui.RATE_LIMIT_WINDOW * 2)
    web_gui.REQUEST_LOG["stale"] = (old_time, 1)
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert "stale" not in web_gui.REQUEST_LOG


def test_rate_limit_thread_safety() -> None:
    """Concurrent requests increment counters without race conditions."""
    app.config["RATE_LIMIT_PER_MINUTE"] = 100
    ip_addr = "9.9.9.9"

    def hit() -> None:
        # Each thread creates its own request context so ``rate_limit`` can
        # access ``flask.request`` safely.
        with app.test_request_context("/", environ_overrides={"REMOTE_ADDR": ip_addr}):
            assert web_gui.rate_limit() is None

    threads = [threading.Thread(target=hit) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert web_gui.REQUEST_LOG[ip_addr][1] == 10


def test_rate_limit_negative_config_disables(caplog) -> None:
    """Negative configuration values disable the limiter with a warning."""

    caplog.set_level(logging.WARNING)
    app.config["RATE_LIMIT_PER_MINUTE"] = -5
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert "disabling rate limiting" in caplog.text


def test_rate_limit_non_numeric_config_disables(caplog) -> None:
    """Non-numeric configuration values should not trigger throttling."""

    caplog.set_level(logging.WARNING)
    app.config["RATE_LIMIT_PER_MINUTE"] = "fast"
    client = app.test_client()
    assert client.get("/").status_code == 200
    assert "Invalid RATE_LIMIT_PER_MINUTE" in caplog.text
