"""General CLI error handling tests.

This module focuses on scenarios where the command-line interface must deal
with unexpected filesystem conditions.  Lightweight stubs provide the minimal
functionality required to execute ``run_cli`` without invoking heavy external
dependencies such as the real MIDI libraries or GUI toolkit.
"""

from __future__ import annotations

import logging
import sys

import pytest

from test_cli_random_chords_validation import cli_env as imported_cli_env

# Re-export the fixture so tests in this module can depend on it directly.
cli_env = imported_cli_env


def test_unwritable_output_directory(
    cli_env, tmp_path, monkeypatch, caplog
) -> None:
    """``run_cli`` exits cleanly when the destination cannot be written.

    The test creates a directory without write permissions and replaces
    ``create_midi_file`` with a helper that attempts to write inside that
    directory.  The resulting ``OSError`` should be logged and cause
    ``SystemExit`` with a non-zero return code so calling scripts can react
    appropriately.
    """

    run_cli, pkg = cli_env

    # Prepare an output directory and simulate a failure when saving to it.  We
    # explicitly raise ``OSError`` rather than relying on filesystem
    # permissions because the test runs as the ``root`` user inside the test
    # environment.
    out_dir = tmp_path / "readonly"
    out_dir.mkdir()

    def _write_file(_melody, _bpm, _ts, path, **_kw) -> None:
        """Simulate a permission failure when attempting to write ``path``."""

        raise OSError("permission denied")

    # Replace heavy generation functions with lightweight stand-ins so the
    # focus remains on error handling rather than melody creation mechanics.
    monkeypatch.setattr(pkg, "create_midi_file", _write_file)
    monkeypatch.setattr(pkg, "generate_melody", lambda *a, **k: ["C4"])
    monkeypatch.setattr(pkg, "generate_harmony_line", lambda m: m)
    monkeypatch.setattr(pkg, "generate_counterpoint_melody", lambda m, k: m)
    monkeypatch.setattr(pkg, "generate_random_rhythm_pattern", lambda n: None)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "--key",
            "C",
            "--chords",
            "C,G",
            "--bpm",
            "120",
            "--timesig",
            "4/4",
            "--notes",
            "8",
            "--output",
            str(out_dir / "out.mid"),
        ],
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            run_cli()

    assert exc.value.code == 1
    assert "could not write midi file" in caplog.text.lower()


def test_list_keys_exits_via_argparse(cli_env, monkeypatch, capsys) -> None:
    """``--list-keys`` should print supported keys without needing other args.

    The new pre-parser handles listing flags before the main parser enforces
    required options, so invoking ``run_cli`` with only ``--list-keys`` is
    sufficient and exits cleanly after printing.
    """

    run_cli, pkg = cli_env
    monkeypatch.setattr(sys, "argv", ["prog", "--list-keys"])
    run_cli()
    captured = capsys.readouterr()
    expected = "\n".join(sorted(pkg.SCALE.keys())) + "\n"
    assert captured.out == expected


def test_list_chords_exits_via_argparse(cli_env, monkeypatch, capsys) -> None:
    """``--list-chords`` should print supported chords without extra options."""

    run_cli, pkg = cli_env
    monkeypatch.setattr(sys, "argv", ["prog", "--list-chords"])
    run_cli()
    captured = capsys.readouterr()
    expected = "\n".join(sorted(pkg.CHORDS.keys())) + "\n"
    assert captured.out == expected

