OBJECTIVE
Prepare the app for deployment to Fly.io and PROVE the container works locally before we touch Fly:
create a Dockerfile, .dockerignore, fly.toml, and a /health check; tune memory so a public 300-label
run can't exhaust RAM; then BUILD and RUN the Docker image locally and confirm the app serves. NO Fly
account, NO deploy, NO API key, NO cost this pass — this pass only makes the container and verifies it
boots and serves. The public demo is FULLY OPEN (no password).

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\main.py                 (routes; add /health if absent; confirm the app object is app.main:app)
- app\config.py               (env settings incl. API_KEY, MAX_RETAINED_JOBS; how the key is read)
- requirements.txt            (all runtime deps — the image installs these)
- Dockerfile, fly.toml        (current placeholders/stubs — replace with real ones)
- .gitignore                  (confirm .env is ignored — it must NOT enter the image)
- the app tree                (confirm demo_labels\, sample_data\, app\ are needed at runtime and will be in the image)

CHANGES

PART 1 — Dockerfile (real, minimal, correct)
  - Base: python:3.11-slim (if a needed system library is missing at boot — see PART 5 — either add the apt
    packages, e.g. `libglib2.0-0 libgl1`, or fall back to `python:3.11`; the local smoke test decides).
  - Steps: set a workdir; copy requirements.txt and `pip install --no-cache-dir -r requirements.txt` first (layer
    cache); then copy the app; EXPOSE 8000; CMD runs uvicorn:
        uvicorn app.main:app --host 0.0.0.0 --port 8000
  - The image MUST include what the app reads at runtime: app\, demo_labels\, sample_data\ (the demo reads these
    from disk). Do NOT bake .env or any secret into the image (see PART 2).

PART 2 — .dockerignore
  - Exclude non-runtime + secret files so they never enter the image: .env, .git, .gitignore, __pycache__, *.pyc,
    .pytest_cache, any venv/.venv, .claude, and the COWORK_HANDOFF_*.md files. Keep app\, demo_labels\,
    sample_data\, requirements.txt. (tests\ and test_labels\ may be excluded — not needed at runtime.)
  - CRITICAL: .env must be excluded — the key is provided on Fly as a secret, never in the image.

PART 3 — /health endpoint
  - Ensure `GET /health` exists in app\main.py and returns HTTP 200 with a tiny JSON body ({"status":"ok"}).
    If it already exists, leave it. This is Fly's health check target.

PART 4 — fly.toml + memory tuning
  - fly.toml: app name suggestion "ttb-label-verify" (note: Fly may require a different globally-unique name at
    launch — that's fine, the user will pick one). Configure:
      * a primary region;
      * [http_service] internal_port = 8000, force_https = true, auto_stop_machines = true,
        auto_start_machines = true, min_machines_running = 0 (scale to zero when idle -> near-zero cost);
      * a health check on path "/health";
      * [[vm]] memory = "1024mb", cpus = 1 (shared) — headroom for the retained in-memory jobs.
  - MEMORY TUNING: in app\config.py, reduce MAX_RETAINED_JOBS to 6 (from 12) so at most ~6 jobs' worth of image
    bytes sit in memory at once. (Each demo job holds ~300 images in memory; 6 * that fits comfortably in 1 GB.)
    Keep the oldest-eviction behavior.

PART 5 — LOCAL DOCKER SMOKE TEST (the point of this pass — prove it serves)
  - Build:  docker build -t ttb-label-verify .
  - Run:    docker run --rm -p 8000:8000 -e API_KEY= ttb-label-verify   (blank key on purpose — we only test that
            it BOOTS and SERVES pages; no live model call, no cost)
  - Confirm from the host: GET http://localhost:8000/health -> 200; GET http://localhost:8000/ -> 200 (the app);
    GET http://localhost:8000/batch -> 200; GET http://localhost:8000/single -> 200.
  - If the container FAILS to boot due to a missing system library (e.g. an OpenCV import needing libGL/glib),
    fix the Dockerfile (add the apt packages or switch base image) and rebuild until it boots and serves. This is
    exactly what we want to catch NOW, locally, not on Fly.
  - Stop the container when done.

DO NOT TOUCH
- The matching/verdict core, triage.py, verify.py, extraction, the batch/UI behavior, the graded catalog, the demo
  data/generators — UNCHANGED (this pass only adds deploy files + /health + the MAX_RETAINED_JOBS value).
- Do NOT deploy to Fly, do NOT install flyctl, do NOT create a Fly account — that's the USER's next step.
- Do NOT put a real API key anywhere. Do NOT commit .env. No git add/commit/push.
- REQUIREMENTS.md, ARCHITECTURE.md, README.md, PROJECT_HANDOFF.md — UNCHANGED this pass.

ACCEPTANCE TEST
1. pip install -r requirements.txt ; pytest -q — existing suite still passes (report the summary).
2. docker build -t ttb-label-verify .  — succeeds. Report the final image size.
3. docker run --rm -p 8000:8000 -e API_KEY= ttb-label-verify  — the container boots without error.
4. From the host: /health -> 200, / -> 200, /batch -> 200, /single -> 200. (No live model call needed; blank key is fine.)
5. Confirm .env is NOT in the image (it's in .dockerignore) and no secret is baked in.
6. Report back to the Testing Manager: pytest summary, whether the image BUILT and the four routes SERVED 200
   locally, the image size, the base image used (and any apt packages you had to add), the fly.toml contents, and
   confirmation that MAX_RETAINED_JOBS is now 6. Note anything that needed fixing to make the container boot.
   Nothing committed or pushed; no Fly, no key, no cost.
