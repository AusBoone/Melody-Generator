FROM python:3.11-slim

# ---------------------------------------------------------------------------
# Melody Generator container image
# ---------------------------------------------------------------------------
#
# The application previews generated melodies using the ``fluidsynth`` CLI.
# Install the system packages here so the web interface can render audio in
# the container.  ``fluid-soundfont-gm`` provides a basic SoundFont so users
# do not have to supply their own.
# ---------------------------------------------------------------------------

WORKDIR /app

COPY requirements.txt ./

# Install the Python dependencies and the system packages required for audio
# rendering.  ``fluid-soundfont-gm`` is optional but ensures preview works
# without additional configuration.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        fluidsynth \
        fluid-soundfont-gm \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENTRYPOINT ["python", "-m", "melody_generator.web_gui"]
