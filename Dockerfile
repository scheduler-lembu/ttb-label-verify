# Container image for the TTB label verification prototype.
#
# The container is the PORTABILITY UNIT: the same image runs on Fly.io for the
# public prototype and drops into TTB's Azure tenant (Container Apps / App
# Service for Linux) for production — prototype -> production is a config change
# (provider/model + endpoint), not a rebuild. See ARCHITECTURE.md §1 / §11.
#
# Scaffold pass: a straightforward, buildable-shape Dockerfile. Not built or run
# in this pass.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application.
COPY . .

# Prototype listens on 8080 (matches fly.toml internal_port).
EXPOSE 8080

# Run the FastAPI app with uvicorn. (app.main:create_app is a stub this pass.)
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
