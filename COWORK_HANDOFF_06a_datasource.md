# COWORK HANDOFF #6a — Application Data-Source Layer (demo application DB)

## OBJECTIVE
Create the application data-source layer: a single interface that supplies
"applications" (the expected values a label is checked against), backed by a bundled
demo dataset (a stand-in for COLA). This is the seam the batch-import path and the
future Azure/COLA connection both plug into, and it is what lets expected values come
from a dataset instead of being hand-typed. It is driven by the existing field registry
so extra/unknown application columns flow through without touching the matcher. Also
record the batch-triage product direction as a DOCUMENTED TARGET (north star), without
changing any existing doc's phase order. Offline only — no AI, no network, no UI, no
batch, no deploy. Proven by pytest. Do not git commit or push.

## FILES TO CREATE
- C:\Users\finan\Documents\ttb-label-verify\app\data_source.py
- C:\Users\finan\Documents\ttb-label-verify\sample_data\demo_applications.csv
- C:\Users\finan\Documents\ttb-label-verify\tests\test_data_source.py
- C:\Users\finan\Documents\ttb-label-verify\BATCH_TRIAGE_DESIGN.md

## FILES TO EDIT
- C:\Users\finan\Documents\ttb-label-verify\app\config.py   (additive only)

## CHANGES

### 1) sample_data\demo_applications.csv  (the demo application DB)
- DERIVE this file from the existing `sample_data\test_labels.csv` so the expected
  values stay identical to the catalog (do NOT modify test_labels.csv itself).
- Columns, in this order:
  `application_id,display_name,image_filename,brand,alcohol_content,class_type,net_contents,producer,country_of_origin,beverage_type`
- One row per existing test label (10 rows). For each row:
  - `application_id` = "APP-0001" .. "APP-0010" in the same order the rows appear in
    test_labels.csv (stable, zero-padded).
  - `image_filename` = copied from test_labels.csv (the linked demo label image).
  - `brand, alcohol_content, class_type, net_contents, producer, country_of_origin` =
    copied verbatim from the matching test_labels.csv row (blank stays blank).
  - `display_name` = the brand, plus " — " plus class_type if class_type is non-blank
    (e.g. "OLD TOM DISTILLERY — Kentucky Straight Bourbon Whiskey"); if class_type is
    blank, just the brand; if brand is blank, use application_id.
  - `beverage_type` = best-effort category inferred from class_type: contains
    "beer"/"malt"/"ale"/"lager" -> "malt beverage"; contains "wine"/"champagne"/"port"
    -> "wine"; otherwise -> "distilled spirits".
- The `warning` column is intentionally omitted (the warning is checked against the
  stored canonical constant, not the application — MA-8).
- `beverage_type` is deliberately an EXTRA field beyond the seven registry fields; it
  exists to prove the data layer carries unknown columns without affecting matching.

### 2) app\data_source.py  (interface + demo implementation + production seam)
Imports: `csv`, `abc`, `pathlib`, `pydantic BaseModel`; import `FIELD_REGISTRY` from
`app.fields` to get the set of known field keys — do NOT hardcode the seven field names;
read them from the registry so adding a registry field automatically makes the loader
pull it from applications.

- `class Application(BaseModel)`:
  - `application_id: str`
  - `display_name: str`
  - `image_filename: str | None = None`
  - `expected: dict[str, str | None]`   # ONLY keys that exist in the field registry
  - `extra: dict[str, str]`             # any other columns (e.g. beverage_type)

- `class ApplicationSource(abc.ABC)`:
  - `@abstractmethod list_applications(self) -> list[Application]`
  - `@abstractmethod get_application(self, application_id: str) -> Application | None`

- `class DemoCsvSource(ApplicationSource)`:
  - `__init__(self, csv_path: str | Path)`: store path; load rows lazily or on init.
  - Loading rule per row: read all columns. Pull `application_id`, `display_name`,
    `image_filename` out by name. Of the REMAINING columns, any whose key is a registry
    field key go into `expected` (empty string -> None); every other column goes into
    `extra` (as strings). Build an `Application`.
  - `list_applications()` -> all rows in file order.
  - `get_application(id)` -> the matching Application or None.
  - Be defensive: a missing file or missing header column raises a clear `ValueError`
    with a helpful message; a blank cell becomes None in `expected`.

- `class AzureApplicationSource(ApplicationSource)`:
  - A DOCUMENTED STUB — do not implement real Azure calls. Docstring must state:
    "Production seam. In production this pulls application records from TTB's COLA/Azure
    tenant and returns the SAME Application shape, so nothing downstream changes. Out of
    scope for the prototype (CON-01); the demo runs on DemoCsvSource or an uploaded CSV."
    Both methods raise `NotImplementedError` with that message.

- `def get_application_source(settings) -> ApplicationSource`:
  - if `getattr(settings, "DATA_SOURCE", "demo") == "azure"`: return `AzureApplicationSource()`
  - else: return `DemoCsvSource(getattr(settings, "DEMO_DB_PATH", "sample_data/demo_applications.csv"))`

- At the bottom, a `__main__` block that prints each application's `application_id` and
  `display_name` (used by the acceptance test), e.g.:
  ```python
  if __name__ == "__main__":
      for a in DemoCsvSource("sample_data/demo_applications.csv").list_applications():
          print(a.application_id, "|", a.display_name)
  ```

### 3) app\config.py  (ADDITIVE ONLY)
- Add two settings to the Settings dataclass with defaults, and read them in
  get_settings() with the existing `_get` string helper:
  - `DATA_SOURCE: str = "demo"`     # "demo" or "azure"
  - `DEMO_DB_PATH: str = "sample_data/demo_applications.csv"`
- Do not remove, rename, or change any existing setting or the settings object shape.

### 4) tests\test_data_source.py  (offline; point the source at
`sample_data/demo_applications.csv`, relative to repo root, as pytest runs from there)
- `test_lists_ten_applications`: `DemoCsvSource(...).list_applications()` has length 10.
- `test_get_known_application`: `get_application("APP-0001")` is not None and its
  `expected["brand"]` and `expected["alcohol_content"]` match the first test_labels.csv
  row's values.
- `test_expected_keys_are_registry_only`: for every application, every key in `.expected`
  is a registry field key (import FIELD_REGISTRY), and "beverage_type" is NOT in
  `.expected`.
- `test_extra_field_preserved`: at least one application has "beverage_type" in `.extra`
  with a non-empty value (proves unknown columns flow through, don't hit the matcher).
- `test_unknown_id_returns_none`: `get_application("APP-9999")` is None.

### 5) BATCH_TRIAGE_DESIGN.md  (NEW — the documented target, north star)
Create this file with a STATUS BANNER at the very top (verbatim), then the design body:
```
# Batch Triage & Data-Source — Design Direction (Documented Target)
## TTB AI Label Verification Prototype — Working Document

> **STATUS: DOCUMENTED TARGET — not yet the built product.** This records the north-star
> product direction (batch-in / exceptions-out triage queue) agreed as where the tool is
> headed. The team is deliberately finishing the required core first — single-label UI
> (done), this data-source layer, batch (#6), and deploy (#7) — and will build the
> exception-folder triage queue on top of the deployed core afterward. This document does
> NOT supersede the phase order in PROJECT_HANDOFF; when the pivot begins, this graduates
> from target to in-build. Treated like the FB-1 note: on the record, showing the
> thinking, marked "next, not now."
```
Then include the design body describing: the batch triage queue (batch in, clean items
auto-clear, exceptions grouped into folders by reason code, agent reviews one field's
flaw across many labels, approve/reject/note click-through, multi-flaw labels tagged into
multiple folders); that the single-label view is RETAINED as the detail panel that opens
on a flagged row (not retired); the data-source seam (this handoff) as the foundation; the
registry-driven extensibility; the Azure/COLA on-ramp as a VISIBLE but STUBBED production
path (never a live integration — CON-01); on-screen-only resolution of decisions (no
persistence — D-8/CON-02); and the alternatives rejected (automatch, single-label as the
workflow, real Azure integration). Keep it consistent with existing decisions and do NOT
restate it as superseding the current phase order — the banner already fixes its status.

## DO NOT TOUCH
- `app\models.py`, `app\fields.py`, `app\matching\*`, `app\extraction\*`, `app\verify.py`,
  `app\main.py`, `app\quality_gate.py`, `app\batch.py`, `app\cache.py`,
  `app\templates\*`, `app\static\*` — unchanged.
- `sample_data\test_labels.csv`, `TEST_PLAN.md`, `tools\*`, `test_labels\*`,
  `README.md`, `REQUIREMENTS.md`, `ASSUMPTIONS_AND_TRADEOFFS.md`, `ARCHITECTURE.md`,
  `PROJECT_HANDOFF.md` — unchanged. (Do NOT apply any phase-reorder or single-label
  "demotion" to these; the target doc's status banner is the only place that direction
  is recorded.)
- Do not reopen or modify the matcher, the canonical warning, or any existing test.
- No AI, no network, no Docker, no deploy, no git push.

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`
2. `pytest -q` — report the summary. Expected: the 57 existing tests still pass PLUS the
   5 new data-source tests = **62 passed**. If any existing test fails, STOP and paste it.
3. `python -m app.data_source` — must print 10 lines, each an application_id and a
   readable display_name (e.g. "APP-0001 | OLD TOM DISTILLERY — Kentucky Straight Bourbon
   Whiskey"). Paste the 10 lines.
4. Confirm `BATCH_TRIAGE_DESIGN.md` exists and opens with the STATUS: DOCUMENTED TARGET
   banner at the top.
5. Report back: the pytest summary (62 passed), the 10 printed application names,
   confirmation that only the listed files were created/edited (git status --short) and
   that no phase-order/demotion edit was made to any existing doc, and that nothing was
   committed or pushed.
