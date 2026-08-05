"""FastAPI application entry point.

Single responsibility: define the HTTP surface and serve the UI. Routes:
    GET  /         -> serve the single-page UI (templates/index.html)
    POST /verify   -> single-label verification (delegates to app.verify)
    POST /batch    -> batch verification; streams per-item results via SSE
                      (delegates to app.batch)

Cross-cutting concerns handled here (later): upload validation (MAX_UPLOAD_MB),
clear error messages for malformed input (NFR-06, never a crash), and the
optional shared-password gate (DEMO_PASSWORD, OFF by default).

Scaffold pass: declare the app object and route stubs. No request handling,
no extraction, no matching this pass.
"""

from __future__ import annotations

# NOTE: imports intentionally omitted in the scaffold to avoid importing
# unresolved runtime deps. The real app constructs:
#     app = FastAPI()
#     app.mount("/static", StaticFiles(directory="app/static"), name="static")
#     templates = Jinja2Templates(directory="app/templates")


def create_app():
    """Build and return the configured FastAPI application.

    Stub: real implementation instantiates FastAPI, mounts static files and
    templates, and registers the routes below. No behavior this pass.
    """
    raise NotImplementedError


async def index():
    """GET / — serve the single-page UI. Stub."""
    raise NotImplementedError


async def verify_route():
    """POST /verify — single-label verification (fail-fast ~5s). Stub."""
    raise NotImplementedError


async def batch_route():
    """POST /batch — batch verification; streams results via SSE. Stub."""
    raise NotImplementedError
