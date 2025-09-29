# Docker Guide

This guide explains how the Melody-Generator Docker image is constructed, how to
run it in different environments, and how to customise the container for
production deployments. The examples assume familiarity with Docker but call out
common pitfalls and troubleshooting steps for new users.

## Image overview
- **Base image**: `python:3.11-slim`.
- **Audio dependencies**: Installs `fluidsynth` and the `fluid-soundfont-gm`
  package so the web interface can render WAV previews without additional
  configuration.
- **Working directory**: `/app`.
- **Entry point**: `python -m melody_generator.web_gui`, which starts the Flask
  web interface defined in `melody_generator/web_gui.py`.
- **Exposed port**: 5000 for HTTP traffic.

The Dockerfile copies `requirements.txt`, installs Python dependencies, and then
copies the remainder of the source tree into the image. No application build
artefacts are produced at runtime, which keeps container start-up fast.

## Building the image
Run the following command from the repository root:

```bash
docker build -t melody-generator .
```

The resulting image contains the CLI, GUI, and web server entry points. Because
all dependencies are vendored during the build step, you can run the container
on machines that only have Docker installed.

### Rebuilding after local changes
If you modify the source code or dependency list, rebuild the image to include
those changes:

```bash
docker build --no-cache -t melody-generator .
```

The `--no-cache` flag ensures Docker does not reuse stale layers when
`requirements.txt` or the application code changes.

## Running the web interface
Launch the container and publish port 5000 so your browser can connect to the
Flask development server:

```bash
docker run --rm -p 5000:5000 melody-generator
```

### Persisting generated files
By default, any files saved by the container remain inside the ephemeral
filesystem. Mount a host directory into `/app/exports` (or another location of
your choosing) to keep generated MIDI/WAV assets:

```bash
docker run --rm -p 5000:5000 \
    -v "$(pwd)/exports:/app/exports" \
    melody-generator
```

You can then reference `/app/exports` from the CLI or web interface when saving
melodies.

### Enabling live reload for development
To enable Flask's debug features and automatic reload, pass the `FLASK_DEBUG`
flag and map your working tree into the container so code changes are reflected
immediately:

```bash
docker run --rm -p 5000:5000 \
    -e FLASK_DEBUG=1 \
    -v "$(pwd):/app" \
    melody-generator
```

This approach is convenient for iterating on the web interface without
rebuilding the image.

## Environment variables
`melody_generator.web_gui` reads several environment variables. Set them via
`-e` flags or a `.env` file when using Docker Compose.

- `FLASK_SECRET` (**required in production**) – Session signing key. A random
  value is generated for development runs, but production mode requires an
  explicit secret so sessions remain valid across restarts.
- `CELERY_BROKER_URL` (**required in production**) – Connection string for the
  Celery broker that renders previews asynchronously. Use `memory://` or omit
  the variable entirely for local, single-process usage.
- `MAX_UPLOAD_MB` (optional) – Caps request size in megabytes. Defaults to 5.
- `RATE_LIMIT_PER_MINUTE` (optional) – Enables a per-IP rate limiter when set to
  an integer value.
- `FLASK_DEBUG` / `FLASK_ENV` (optional) – Enables Flask debug mode and live
  reload when set.

Example production run using Redis for Celery and a persistent secret:

```bash
docker run --rm -p 5000:5000 \
    -e FLASK_SECRET="change-me" \
    -e CELERY_BROKER_URL="redis://redis:6379/0" \
    -e RATE_LIMIT_PER_MINUTE=120 \
    melody-generator
```

## Accessing the CLI inside the container
Use the bundled Python interpreter to execute the CLI without running the web
server:

```bash
docker run --rm -it --entrypoint python melody-generator -m melody_generator.cli --help
```

To generate a melody directly to a mounted volume:

```bash
docker run --rm -it \
    --entrypoint python \
    -v "$(pwd)/exports:/app/exports" \
    melody-generator \
    -m melody_generator.cli --output /app/exports/test.mid
```

## Using Docker Compose
The following minimal `docker-compose.yml` file runs the web interface alongside
a Redis broker for Celery background tasks:

```yaml
version: "3.9"
services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      FLASK_SECRET: "change-me"
      CELERY_BROKER_URL: "redis://redis:6379/0"
      RATE_LIMIT_PER_MINUTE: 120
    depends_on:
      - redis
  redis:
    image: redis:7-alpine
```

Start the stack with:

```bash
docker compose up --build
```

## Troubleshooting
- **`command not found: docker`** – Install Docker Desktop (macOS/Windows) or
  the Docker Engine packages for your Linux distribution.
- **Port conflicts** – If port 5000 is already in use, change the host mapping
  (e.g., `-p 8080:5000`) and navigate to `http://localhost:8080`.
- **`Missing FLASK_SECRET` error** – Set the variable via `-e FLASK_SECRET=...`
  when running in production mode or ensure `FLASK_DEBUG=1` during development.
- **FluidSynth audio issues** – The container bundles a General MIDI soundfont,
  but audio playback on the host still depends on the browser. If previews are
  silent, download the generated MIDI and play it locally to confirm the data is
  correct.

For more operational details refer to `melody_generator/web_gui.py`, which
contains in-depth comments on configuration and security checks performed at
startup.
