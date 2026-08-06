# COWORK HANDOFF #6-prep — Surface the files the batch build needs

## OBJECTIVE
Read-and-report only. Print the current verbatim contents of the files the batch pass
(#6) builds against, so the Testing Manager writes the batch routes, page, and pairing
logic against exactly what exists — especially the CURRENT main.py (its TemplateResponse
call signature) and the data_source public API. Change no files. Do NOT git add, commit,
or push.

## FILES TO CREATE / EDIT
None. Create, edit, and delete nothing. This round only reads files.

## TASKS
Print the FULL, VERBATIM current contents of each of these files, each under a clear
heading with its path:
1. C:\Users\finan\Documents\ttb-label-verify\app\main.py
2. C:\Users\finan\Documents\ttb-label-verify\app\batch.py
3. C:\Users\finan\Documents\ttb-label-verify\app\cache.py
4. C:\Users\finan\Documents\ttb-label-verify\app\data_source.py
5. C:\Users\finan\Documents\ttb-label-verify\app\config.py
6. C:\Users\finan\Documents\ttb-label-verify\app\templates\index.html
7. C:\Users\finan\Documents\ttb-label-verify\app\static\app.js
8. C:\Users\finan\Documents\ttb-label-verify\sample_data\batch_template.csv

If any file does not exist, say so explicitly rather than guessing.

## DO NOT TOUCH
- Do not modify, create, or delete ANY file.
- No git add, commit, or push. No network calls. Do not touch .env or print the key.

## ACCEPTANCE TEST
Your reply contains the full current contents of all eight files above (or a clear note
for any that do not exist), and confirms nothing on disk was changed and nothing was
committed or pushed.
