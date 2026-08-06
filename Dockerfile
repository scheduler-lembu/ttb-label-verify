# Container image for the TTB label verification prototype.
#
# The container is the PORTABILITY UNIT: the same image runs on Fly.io for the
# public prototype and drops into TTB's Azure tenant (Container Apps / App
# Service for Linux) for production — prototype -> production is a config change
# (provider/model + endpoint), not a rebuild. See ARCHITECTURE.md §1 / §11.

FROM python:3.11-slim

# System libraries opencv-python-headless needs at import time. The headless
# build drops the GUI/libGL dependency, but cv2 still links libglib
# (libgthread-2.0) — without it `import cv2` fails at boot. libgl1 is added as
# cheap insurance for any codec path that still reaches for it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application. .dockerignore keeps .env, .git, caches, and the handoff
# notes out of the image; app/, demo_labels/, and sample_data/ (read at runtime)
# come in.
COPY . .

# App listens on 8000 (matches fly.toml internal_port).
EXPOSE 8000

# Run the FastAPI app. The ASGI app object is `app` in app/main.py.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
