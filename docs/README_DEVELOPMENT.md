# Development Guide

This guide explains how to work effectively on Melody-Generator once you have a
local clone. It complements the top-level README by documenting code
organization, testing strategy and release workflows.

## Repository Layout

- `melody_generator/` – Python package containing the core generator, optional
  ML helpers and user interfaces.
  - `generator.py` hosts the rule-based melody engine.
  - `style/` loads style embeddings, PyTorch models and weighting helpers.
  - `gui.py` implements the Tkinter desktop application.
  - `web_gui/` exposes the Flask blueprint, Celery tasks and HTML templates.
- `docs/` – Extended documentation for setup, architecture, ML concepts and
  troubleshooting.
- `tests/` – Pytest suite covering generator logic, CLI behaviour, GUI events
  (via mocking) and Flask endpoints.
- `scripts/` – Utility scripts for dataset preparation and operational tasks.

Understanding this structure makes it easier to navigate the codebase and spot
where new functionality should live.

## Local Environment

1. Create a virtual environment with `python -m venv .venv` and activate it.
2. Install the project in editable mode using `pip install -e .[dev]` if you
   want development extras (defined in `pyproject.toml`).
3. Optionally install FluidSynth and a General MIDI soundfont so GUI/Web audio
   previews work locally.

## Coding Standards

- Python code follows PEP 8 conventions with a 100 character line length
  enforced via `ruff`. Configure your editor to apply the same formatting rules.
- Prefer descriptive identifiers and add docstrings to any new modules,
  classes or functions. Inline comments should explain non-obvious logic.
- When touching user-facing strings, ensure they remain concise and actionable
  because the GUI and Flask templates display them directly to musicians.

## Testing Strategy

The automated suite exercises most of the project surface area:

- **Unit tests** validate scale selection, rhythm creation, tension weighting
  and MIDI export functions.
- **Integration tests** simulate CLI executions, GUI button clicks (with
  dependency injection) and HTTP requests to the Flask app.
- **Regression tests** guard against bugs fixed in previous releases, such as
  race conditions in the Celery worker and edge cases around time signatures.

Before submitting changes run:

```bash
pytest
ruff check .
```

Both commands should pass. If you add new behaviour, include targeted tests with
clear docstrings that justify the scenario being covered.

## Release Workflow

1. Update `CHANGELOG.md` (or add a new entry if the file does not exist yet)
   summarizing noteworthy changes.
2. Bump the package version in `pyproject.toml` following semantic versioning.
3. Tag the release in Git with `git tag vX.Y.Z` and push the tag to GitHub.
4. Build the distribution with `python -m build` and upload it to TestPyPI or
   PyPI once smoke tests complete.

## Common Tasks

- **Run the GUI**: `python -m melody_generator`
- **Launch the web app**: `flask --app melody_generator.web_gui:create_app run`
- **Export many melodies**: Use `scripts/batch_generate.py` to fan out jobs
  using `ProcessPoolExecutor`.
- **Train a custom style**: Follow `docs/README_TRAINING.md`, then place the
  resulting weights and embeddings under `melody_generator/style/models/`.

## Troubleshooting

If you hit issues while developing (e.g., missing system packages or failing
previews), reference [README_TROUBLESHOOTING.md](README_TROUBLESHOOTING.md) for
platform-specific tips and logging guidance.
