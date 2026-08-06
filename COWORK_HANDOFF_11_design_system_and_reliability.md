OBJECTIVE
Establish a shared, professional design system and apply it to the surfaces that are NOT
changing structurally (the single-label page and the batch LANDING area), add a favicon (to
end the /favicon.ico 404), and fix batch reliability so transient read failures (the "extractor
unavailable — needs human review" items) are retried instead of fast-failed. This is the
FOUNDATION pass: the next handoff (#12) rebuilds the triage results into per-field buckets +
a focused review screen using THIS design system, so everything ends up consistent. No flow
changes; the ONLY behavior change is the batch retry (backend). Offline build + unit tests;
no deploy.

TARGET REPO (CONFIRMED): C:\Users\finan\Documents\ttb-label-verify\   (NOT "shaphal".)

BEFORE YOU START — READ THESE
- app\templates\index.html         (single-label page markup)
- app\static\app.js                (single-label results rendering, if results are built in JS)
- app\templates\batch.html         (batch page: the LANDING cards + the results/triage container)
- app\static\batch.js              (triage results rendering — DO NOT change its behavior this pass)
- app\static\style.css             (current styles — you will grow this into the design system)
- app\main.py                      (how templates/static are served; where to add a favicon route/link)
- app\extraction\vision_llm.py     (the request timeout; model param from #10)
- app\extraction\router.py         (extract_batch from #10 — where the retry goes)
- app\config.py + .env.example     (add the batch timeout + retry knobs)

FILES TO EDIT / CREATE
EDIT:   app\static\style.css              (THE DESIGN SYSTEM: tokens + components + restyle rules)
EDIT:   app\templates\index.html          (apply component classes/markup — single-label page)
EDIT:   app\static\app.js                 (apply the new classes to JS-rendered single-label results; styling only)
EDIT:   app\templates\batch.html          (restyle the LANDING area only: header, "Try the demo" + "Use your own" cards)
CREATE: app\static\favicon.svg            (a simple, professional favicon — inline-drawable SVG)
EDIT:   app\templates\*.html + app\main.py (wire the favicon: <link rel="icon"> in templates and/or a /favicon.ico route)
EDIT:   app\config.py                      (add BATCH_LABEL_TIMEOUT_S + BATCH_MAX_RETRIES)
EDIT:   app\.env.example                   (document the two new batch knobs; keep values as defaults)
EDIT:   app\extraction\vision_llm.py       (let the batch extractor use a longer timeout than single-label)
EDIT:   app\extraction\router.py           (extract_batch: bounded retry on transient failure)
EDIT:   tests\test_batch.py or tests\test_cache.py (add the retry unit test — offline, fake extractor)

CHANGES

PART 1 — THE DESIGN SYSTEM (app\static\style.css)
Aesthetic: clean, professional, trustworthy — appropriate for a U.S. Treasury / federal compliance
tool. Restrained and serious, not flashy. DEPENDENCY-FREE: no external fonts, no icon CDN, no
framework — everything self-contained so it works inside a locked-down network and offline.
  - TOKENS as CSS custom properties in :root (use these everywhere; no hard-coded colors elsewhere):
      * Palette: a deep navy/slate primary (headers, primary buttons); a near-white app background;
        white cards with a subtle border + soft shadow; near-black body text; a muted gray for
        secondary text; ONE restrained blue accent for links.
      * Semantic status (MUTED and accessible, NOT neon): pass=professional green, fail=serious red,
        needs-review/attention=amber/gold. Provide a bg+text pair for each so contrast is AA.
      * Spacing scale, border-radius, shadow, and a type scale (h1/h2/h3/body/small) as tokens.
  - TYPOGRAPHY: a clean system font stack, e.g.
      font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    Comfortable line-height, sensible max line length for reading. Large, legible sizes (NFR-03).
  - ICONS: a small set of INLINE SVG icons defined once and reused (e.g. an SVG <symbol> sprite in a
    shared partial, or documented inline snippets): check, x, warning-triangle, bucket/folder, image,
    upload, search, chevron. No icon library, no network.
  - COMPONENTS (shared classes, used across ALL pages so the look is uniform):
      * Buttons: .btn with variants --primary (navy), --success (approve/green), --danger (reject/red),
        --secondary/ghost. Large targets, clear hover/active, VISIBLE focus ring (keyboard-accessible).
      * Cards / panels: consistent radius, border, shadow, padding.
      * Status pill/badge: pass/fail/review variants using the semantic tokens.
      * Tables: style the extracted-vs-expected readout (header, row rhythm, status coloring).
      * Page header + section banners.
  - ACCESSIBILITY: WCAG AA contrast, visible focus states, large tap targets (the 73-year-old bar),
    readable sizes. Keep it high-contrast and calm.
  - This design system lives in style.css and is loaded by every page, so single-label, batch, and
    (in #12) the review screen all inherit the same tokens/components.

PART 2 — RESTYLE THE STABLE SURFACES (markup: apply the classes; NO behavior change)
  - Single-label page (index.html + app.js result rendering): apply the header, card, button, table,
    and status-pill components. The upload zone, the primary button, and the extracted-vs-expected
    results table should all look like the new system. Behavior/flow UNCHANGED.
  - Batch LANDING (batch.html): restyle the page header, the "Try the demo" card (primary button),
    and the "Use your own" card (template link, file inputs, "Check my batch" button) to the system.
  - DO NOT restructure or change the behavior of the triage RESULTS area (the summary bar, the
    buckets/folders, the detail panel) — that is rebuilt in #12. It will inherit the global tokens
    (font/colors) automatically, which is fine for this interim pass. Do NOT edit batch.js behavior.

PART 3 — FAVICON (end the 404)
  - Add app\static\favicon.svg: a simple, professional mark (e.g. a small navy shield or a check-in-a-
    square — plain, no external asset). Reference it with <link rel="icon" href="/static/favicon.svg">
    in the page templates, and/or add a lightweight GET /favicon.ico route that returns it. Confirm the
    browser stops logging a 404 for /favicon.ico.

PART 4 — BATCH RELIABILITY: RETRY (fixes the "extractor unavailable" items)
Rationale: single-label reads fail fast to hold the ~5s bar (NFR-01), but BATCH is not on the
interactive clock, so a transient timeout/API hiccup should be RETRIED, not surfaced as a failed read.
  - app\config.py + .env.example: add
      BATCH_LABEL_TIMEOUT_S  (default e.g. 15 — longer than SINGLE_LABEL_TIMEOUT_S)
      BATCH_MAX_RETRIES      (default e.g. 2 — attempts AFTER the first try)
  - app\extraction\vision_llm.py: the batch extractor (BATCH_MODEL) should use BATCH_LABEL_TIMEOUT_S
    for its request timeout; the single-label extractor keeps SINGLE_LABEL_TIMEOUT_S. (Single-label
    fail-fast behavior is UNCHANGED.)
  - app\extraction\router.py, extract_batch: on a failed read (ok=False / exception), retry up to
    BATCH_MAX_RETRIES times (a tiny backoff between attempts is fine) before giving up and returning
    the not-ok result (which verify then turns into NEEDS_REVIEW, as today). A CACHE HIT still short-
    circuits with no call and no retry. Only cache successful reads (unchanged from #10).
  - Keep it simple and synchronous within the existing off-thread batch worker; do NOT add new deps.

DO NOT TOUCH
- The matching/verdict core: app\matching\*, app\models.py, app\fields.py, app\matching\canonical.py — UNCHANGED.
- app\triage.py — UNCHANGED this pass (its per-field rework is #12).
- app\static\batch.js BEHAVIOR — UNCHANGED (triage results logic is rebuilt in #12; only global CSS may affect it).
- The single-label FLOW and app\verify.py single-label behavior — UNCHANGED (styling only on the single-label page).
- app\extraction\prompt.py — UNCHANGED.
- The graded catalog (test_labels\, sample_data\test_labels.csv, TEST_PLAN.md, tools\generate_test_labels.py) — UNCHANGED.
- The #7 demo corpus (demo_labels\, sample_data\demo_applications.csv, tools\generate_demo_labels.py) — UNCHANGED.
- REQUIREMENTS.md, ARCHITECTURE.md, BATCH_TRIAGE_DESIGN.md, PROJECT_HANDOFF.md — UNCHANGED this pass.
- No git add/commit/push. No .env / API-key access. No Docker/deploy. Do NOT run the 300-item live batch —
  the retry is proven by the offline unit test below.

ACCEPTANCE TEST
1. pip install -r requirements.txt
2. pytest -q — all prior tests (96) still pass, PLUS a new batch RETRY test (offline, fake extractor):
     - a fake batch extractor that FAILS ONCE then SUCCEEDS -> extract_batch returns ok=True and the
       underlying extractor was called TWICE (one retry);
     - a fake extractor that ALWAYS FAILS -> extract_batch returns ok=False after 1 + BATCH_MAX_RETRIES
       attempts (no infinite loop);
     - a CACHE HIT still returns immediately with ZERO extractor calls (no retry on a hit).
   Report the pytest summary and the new test count.
3. Boot check: TestClient GET /batch -> 200 and GET / (single-label page) -> 200.
4. Favicon: confirm GET /favicon.ico (or /static/favicon.svg) returns 200, not 404.
5. Visual check (start the server locally, no model call needed for styling): open / and /batch and confirm
   the single-label page and the batch LANDING now use the new design system — navy header, styled cards,
   the new button styles, consistent typography and status colors. Report briefly how they look (a DOM/CSS
   read or a screenshot description is fine). The triage results area may still look plain — that's expected
   (rebuilt in #12).
6. Scope check: git status shows only the intended files; the matcher core, triage.py, batch.js behavior,
   the graded catalog, the #7 corpus, and the untouched docs are unchanged.
7. Report back to the Testing Manager: pytest summary + new test count, the retry test result (2 calls on
   fail-then-succeed; capped attempts on always-fail; 0 on cache hit), the favicon confirmation, a short note
   on how the restyled pages look, confirmation of scope, and that nothing was committed/pushed and no live
   300-run occurred.
