# COWORK HANDOFF #4b-1-push — Commit & Push the Image Quality Gate

## OBJECTIVE
Commit and push the reviewed Handoff #4b-1 work (image quality gate) to the public
repo. It has passed Testing-Manager review. This is a git operation only: gate on the
offline tests first, and never stage, commit, or print .env or the API key.

## FILES TO CREATE / EDIT
None. Create, edit, and delete nothing. This round only runs tests and git commands.

## TASKS
1. From `C:\Users\finan\Documents\ttb-label-verify\` run:  `pytest -q`
   If the output does NOT end in "40 passed" (or shows ANY failure/error), STOP —
   do not stage, commit, or push — and paste the full output. Otherwise continue.

2. Run:  `git add -A`
   Then run:  `git status`
   Paste the git status output. In your reply, explicitly confirm that `.env` is NOT
   in the list of staged/changed files (it is git-ignored and must never be staged).
   If `.env` — or anything that could contain a secret — appears staged, STOP and report.

3. Run:  `git commit -m "Image quality gate (Handoff #4b-1)"`
   Paste the commit summary line.

4. Run:  `git push origin main`
   Paste the push output. If the push fails for any reason (auth, credentials,
   network), do NOT retry blindly and do NOT change anything — paste the exact error
   message and stop.

5. Run:  `git log --oneline -3`   and   `git status`
   Paste both. The new Handoff #4b-1 commit should be the top line, it should now be
   on origin/main, and the working tree should report "nothing to commit, working
   tree clean".

## DO NOT TOUCH
- Do not edit, create, or delete any source or documentation file — commit/push only.
- Never stage, commit, or print the contents of `.env` or the API key. `.env` stays
  git-ignored and untracked.
- Do not rewrite or amend any earlier commit; only add the one new commit.

## ACCEPTANCE TEST
Your reply shows, in order: pytest ending in "40 passed"; a git status after
`git add -A` with `.env` absent from the staged files; the new commit created;
`git push origin main` succeeding; and a final `git log --oneline -3` with the
Handoff #4b-1 commit on top plus a clean working tree. If any step failed, you
stopped at that step and pasted the exact error instead of proceeding.
