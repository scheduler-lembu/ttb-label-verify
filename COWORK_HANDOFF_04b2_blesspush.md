# COWORK HANDOFF #4b-2-blesspush — Accept imperfect-image outcomes, then push

## OBJECTIVE
Record that the two deliberately-imperfect catalog labels (09 tiny, 10 rotated+noise)
have TWO acceptable outcomes — PASS (read cleanly) or NEEDS_REVIEW (flagged for a
human, NFR-05) — so the catalog reports cleanly with the literal-OCR cross-check
active. Then commit and push all outstanding work: the FB-1 future-build note, the
#4b-2 warning cross-check, and this expectation update. The push is GATED on a clean
test + harness run — if anything still DIFFERS, stop before committing.

## FILES TO CREATE / EDIT
Edit:
- C:\Users\finan\Documents\ttb-label-verify\tools\run_catalog.py
- C:\Users\finan\Documents\ttb-label-verify\TEST_PLAN.md

(No new files. All other outstanding changes are already on disk from earlier passes
and will be committed as-is.)

## CHANGES

### 1) tools/run_catalog.py — accept a set of verdicts for the two imperfect labels
In the `EXPECTED_OVERALL` map, replace the two single-value entries:
```python
    "label_09_warning_tiny.png": ResultState.PASS,
    "label_10_degraded.png": ResultState.PASS,
```
with set-valued entries (both PASS and NEEDS_REVIEW count as a match — imperfect
image, NFR-05: reading it or flagging it are both correct; only a wrong verdict fails):
```python
    # Imperfect-image labels: PASS (read cleanly) OR NEEDS_REVIEW (cross-check flags
    # the tiny/rotated warning for a human) are BOTH acceptable outcomes (NFR-05).
    "label_09_warning_tiny.png": frozenset({ResultState.PASS, ResultState.NEEDS_REVIEW}),
    "label_10_degraded.png": frozenset({ResultState.PASS, ResultState.NEEDS_REVIEW}),
```
Then update the match/print block. Replace:
```python
        exp_overall = EXPECTED_OVERALL.get(filename)
        verdict_matches = exp_overall is None or result.overall == exp_overall
        matched += int(verdict_matches)
        flag = "MATCH " if verdict_matches else "DIFFERS"

        print(f"-- {filename}")
        print(f"   overall: {result.overall.value:12s} "
              f"expected: {exp_overall.value if exp_overall else '-':12s} "
              f"[{flag}]   {elapsed:5.2f}s")
```
with:
```python
        exp_overall = EXPECTED_OVERALL.get(filename)
        if isinstance(exp_overall, frozenset):
            verdict_matches = result.overall in exp_overall
            exp_label = " or ".join(sorted(s.value for s in exp_overall))
        else:
            verdict_matches = exp_overall is None or result.overall == exp_overall
            exp_label = exp_overall.value if exp_overall else "-"
        matched += int(verdict_matches)
        flag = "MATCH " if verdict_matches else "DIFFERS"

        print(f"-- {filename}")
        print(f"   overall: {result.overall.value:12s} "
              f"expected: {exp_label:24s} "
              f"[{flag}]   {elapsed:5.2f}s")
```
Change nothing else in the file.

### 2) TEST_PLAN.md
- In the §3 catalog table (the main per-label table), for the `label_09` and
  `label_10` rows only, change the expected-verdict cell to read:
  `PASS or NEEDS_REVIEW (imperfect image — both acceptable, NFR-05)`
  and, in each of those two rows' notes/"proves" text, append: for label_09 —
  "the literal-OCR cross-check may flag the tiny/buried warning for review (a soft
  touch on the deferred MR-06 concern)"; for label_10 — "the cross-check may flag the
  rotated/noisy image for review (NFR-05 graceful degradation)". Do not change any
  other row.
- In the "## Handoff #4b-2 — literal-OCR warning cross-check: real end-to-end results"
  section appended last pass, add one closing line:
  "Resolution: for the two deliberately-imperfect labels (09 tiny, 10 rotated) both
  PASS and NEEDS_REVIEW are accepted as correct (NFR-05); the harness expectation is
  updated accordingly, so the catalog reports 10/10 with the cross-check active. The
  current run flagged both — the conservative, compliance-safe outcome."

## GATE + GIT (do these in order; STOP on any failure)
1. `pip install -r requirements.txt`  (should be a no-op)
2. `pytest -q` — must end in "50 passed". If not, STOP and paste the output.
3. Confirm API_KEY is present (report "present"/"absent", never the key). If present,
   run `python tools/run_catalog.py`. It MUST now report **10/10 MATCH** (labels 09/10
   match because their verdict is in the accepted set). If ANY label shows DIFFERS,
   STOP — do NOT commit or push — and paste the full table.
4. `git add -A`, then `git status`. Paste it. Confirm `.env` is NOT staged (only
   `.env.example` may appear). If `.env` or any secret-bearing file is staged, STOP.
5. `git commit -m "Literal-OCR warning cross-check + imperfect-image expectations; incl. FB-1 future-build note (Handoff #4b-2)"`
   Paste the commit summary line. (This single commit intentionally includes the FB-1
   note, the #4b-2 cross-check code + doc syncs, and this expectation update — they are
   interleaved in the working tree.)
6. `git push origin main` — paste the output. If it fails (auth/network), do NOT retry
   blindly; paste the exact error and stop.
7. `git log --oneline -3` and `git status` — paste both. The new commit should be on
   top, on origin/main, working tree clean.

## DO NOT TOUCH
- app/matching/*, app/models.py, app/fields.py, tests/* (except none change this pass),
  app/quality_gate.py, app/extraction/* — no code changes this pass.
- app/main.py, templates/*, static/*, app/batch.py, cache.py, Dockerfile, fly.toml,
  ARCHITECTURE.md — unchanged.
- Only `tools/run_catalog.py` and `TEST_PLAN.md` are edited; everything else already on
  disk is committed as-is. Never stage/commit/print `.env` or the API key.

## ACCEPTANCE TEST
Your reply shows, in order: `pytest` ending "50 passed"; the harness reporting 10/10
MATCH with the cross-check active; a `git status` after add with `.env` absent; the
commit created; `git push origin main` succeeding; and a final `git log --oneline -3`
with the new Handoff #4b-2 commit on top plus a clean working tree. If any gate failed,
you stopped there and pasted the exact output instead of committing or pushing.
