# COWORK HANDOFF #2c — Warning Prefix Whitespace Fix

## START HERE
Read these first, then this handoff:
- `C:\Users\finan\Documents\ttb-label-verify\app\matching\rules.py`  (the file being fixed)
- `C:\Users\finan\Documents\ttb-label-verify\tests\test_matching.py`  (the test being extended)
- `C:\Users\finan\Documents\ttb-label-verify\REQUIREMENTS.md`  (§5 MR-05)
- `C:\Users\finan\Documents\ttb-label-verify\ASSUMPTIONS_AND_TRADEOFFS.md`

---

## OBJECTIVE
Fix one real bug: the all-caps prefix check in `match_warning` compares the matched
prefix to a single-spaced literal, so a **correctly all-caps** warning whose prefix
wraps across a line break or uses extra spaces (`GOVERNMENT\nWARNING`,
`GOVERNMENT␣␣WARNING`) is **wrongly FAILed as "prefix not all caps."** Make the
all-caps check whitespace-tolerant (case remains strict), add tests that guard it,
and add-only doc notes. Still **offline** — no AI, no network, no UI, no deploy.

**This is a targeted fix. Do not change any other matcher, threshold, or the exact
(character-for-character) body comparison. Warning strictness on WORDING and CASE
stays exactly as-is — only the prefix whitespace handling changes.**

---

## PART A — CODE FIX

### `app/matching/rules.py` — inside `match_warning`, the prefix all-caps check
Replace this block:
```python
    if m.group(0) != "GOVERNMENT WARNING":
        return FieldResult(
            field="warning",
            expected=CANONICAL_GOVERNMENT_WARNING,
            extracted=extracted,
            rule=WARNING_RULE,
            verdict=ResultState.FAIL,
            reason=ResultReason.WARNING_PREFIX_NOT_ALLCAPS,
            note="prefix not all caps",
        )
```
with this (collapse the matched prefix's whitespace to a single space **before** the
case comparison, so a line-broken/multi-space but correctly-capitalized prefix passes,
while a genuine case difference like `Government Warning` still fails):
```python
    prefix_norm = re.sub(r"\s+", " ", m.group(0))
    if prefix_norm != "GOVERNMENT WARNING":
        return FieldResult(
            field="warning",
            expected=CANONICAL_GOVERNMENT_WARNING,
            extracted=extracted,
            rule=WARNING_RULE,
            verdict=ResultState.FAIL,
            reason=ResultReason.WARNING_PREFIX_NOT_ALLCAPS,
            note="prefix not all caps",
        )
```
(`re` is already imported at the top of the file. Change nothing else in this function
— the downstream exact-match already whitespace-normalizes the full text, so a
line-broken compliant warning will now pass end-to-end.)

---

## PART B — TESTS (`tests/test_matching.py`)
Add these tests (keep all existing tests unchanged):

```python
def test_warning_linebroken_prefix_passes():
    """A correctly all-caps prefix wrapped across a line break -> PASS (not a caps failure)."""
    line_broken = CANONICAL_GOVERNMENT_WARNING.replace(
        "GOVERNMENT WARNING", "GOVERNMENT\nWARNING", 1
    )
    r = match_warning(None, line_broken)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.MATCH


def test_warning_double_space_prefix_passes():
    """A correctly all-caps prefix with an extra space -> PASS."""
    double_space = CANONICAL_GOVERNMENT_WARNING.replace(
        "GOVERNMENT WARNING", "GOVERNMENT  WARNING", 1
    )
    r = match_warning(None, double_space)
    assert r.verdict == ResultState.PASS
    assert r.reason == ResultReason.MATCH
```
The existing `test_warning_title_case_prefix_fails` must **still pass** (genuine case
difference still FAILs) — confirm it does. That's the regression guard proving we
loosened whitespace only, not case.

---

## PART C — DOC SYNC (ADD-ONLY — do not reword or remove anything existing)

### `REQUIREMENTS.md`
- **§5, MR-04/05 "Acceptance detail" paragraph — append one sentence** (do not alter
  the existing text): "Whitespace variation *within the prefix* (a line break or
  extra spaces between GOVERNMENT and WARNING) does not by itself fail the all-caps
  check — only a genuine letter-case difference fails."

### `ASSUMPTIONS_AND_TRADEOFFS.md`
- **§E (Known Limitations) — append one item** (next number in sequence): "The
  all-caps prefix check is whitespace-tolerant: the matched `GOVERNMENT WARNING`
  prefix is whitespace-normalized before the case comparison, so a correctly-capitalized
  prefix that wraps across lines is not false-failed. Case remains strict (title case
  fails)."

**Do NOT** change any existing FR/MR/NFR wording or ID, any decision row, or any
other assumption. Additions only.

---

## DO NOT TOUCH
- Any matcher other than `match_warning`'s prefix check. No threshold changes.
- The canonical warning wording, the exact body comparison, or warning strictness on
  wording/case.
- `app/extraction/*`, `app/main.py`, `app/verify.py`, `app/batch.py`, `app/cache.py`,
  `app/config.py`, `app/templates/*`, `app/static/*`, `app/models.py`, `app/fields.py`,
  `app/matching/normalize.py`, `app/matching/canonical.py` — unchanged this pass.
- No AI/network/Docker/deploy/push. No prices.

---

## ACCEPTANCE TEST
1. `pip install -r requirements.txt`
2. `pytest -q` — **all pass**, now including:
   - `test_warning_linebroken_prefix_passes` (was the bug) → PASS / `match`.
   - `test_warning_double_space_prefix_passes` → PASS / `match`.
   - `test_warning_title_case_prefix_fails` still FAILs / `warning_prefix_not_allcaps` (regression guard).
   - Every previously-passing case still passes (expect the total to rise by 2).
3. Confirm the one-sentence additions are present in `REQUIREMENTS.md` (§5) and
   `ASSUMPTIONS_AND_TRADEOFFS.md` (§E), and that nothing existing was changed.
4. Paste the `pytest` summary + the two doc lines you added back to the Testing Manager.
   **Do not push** — the Testing Manager will review, then direct the push.
