# Phase 3 — AI Judging Pipeline

An **admin-run** script that scores shortlisted artwork against the rubric using Claude
vision and produces a ranked report for human judges. The AI score is an **advisory
pre-screen** — humans decide the final winners.

```
folder of named images ──▶ judge.py ──▶ output/results.html  ◀── review here
(or CSV+images, or Google Sheet+Drive)   output/results.csv
                                         output/shortlist.csv (top-3 per school&category)
```

## Quick start (local-folder — no Google setup, no CSV)

Name each photo with the metadata, drop them in a folder, run the script.

```bash
cd phase3-ai-judging
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then add your ANTHROPIC_API_KEY (INPUT_MODE=local-folder)
# put artwork photos in input/images/ named like the convention below

python judge.py --dry-run     # sanity-check what will be judged (no API calls)
python judge.py               # judge everything → output/results.html
```

Open `output/results.html` to review scores, per-criterion breakdowns, the AI-recommended
**top 3 per school & category**, and the **inter-school leaderboard** per category.

### Filename convention (local-folder)
```
School__Category__Student__YYYY-MM-DD__HHMM[__RegID].jpg
e.g.  Sri-Vidya-School__Coloring__Diya-Sharma__2026-07-20__1015.jpg
```
- Fields split on `__`; a `-` inside a field shows as a space (spaces also allowed).
- **Category** = `Coloring` or `Painting` (`C` / `P` accepted).
- **Time** and **RegID** are optional (time falls back to the file's modified time).
- Duplicates for the same student & category → newest kept. Bad filenames are skipped
  and listed in the report. Full guide for coordinators: **[NAMING.md](./NAMING.md)**.

### Alternative: CSV mode (`INPUT_MODE=local`)
Columns `id, school, student, standard, category, title, image` (`image` = filename in
`IMAGES_DIR`). A sample `input/submissions.csv` is included.

### Helper: generate filenames from the roster ([`tools/build_filenames.py`](./tools/build_filenames.py))
So coordinators don't hand-type names. Export the Student Registration sheet to CSV, then:

```bash
# 1) make a checklist of the correct name for every student
python tools/build_filenames.py --csv students.csv --date 2026-07-20
#    -> filenames.csv  (reg_id, school, student, category, suggested_name)

# 2) OR auto-rename a folder of loosely-named photos into the convention
python tools/build_filenames.py --csv students.csv --date 2026-07-20 --rename ./photos
python tools/build_filenames.py --csv students.csv --date 2026-07-20 --rename ./photos --apply
#    matches each file by RegID in its name; add --copy ./renamed to keep originals
```
Category comes from a `category` column or is inferred from the standard (2–5 = Coloring,
6–10 = Painting). Stdlib only — no extra installs. Preview first; `--apply` to commit.

## Drive mode (read straight from the Google Form)

Use this to pull images posted to the **Artwork Submission** form (Phase 2 setup).

1. Create a Google Cloud **service account**, download its JSON key.
2. Enable the **Google Sheets API** and **Google Drive API** for that project.
3. **Share** the responses Sheet *and* the form's upload Drive folder with the service
   account's email (viewer access).
4. In `.env` set:
   ```
   INPUT_MODE=drive
   GOOGLE_SERVICE_ACCOUNT_JSON=service-account.json
   SHEET_ID=<from the Phase 2 setup log>
   SHEET_TAB=Form Responses 1
   ```
5. `pip install gspread google-api-python-client google-auth` (already in requirements).
6. `python judge.py`

## Drive folder mode — coming soon

`INPUT_MODE=drive-folder` will read images straight from a Google Drive folder using the
same filename convention (no Sheet needed). Until it lands, **download or sync that Drive
folder locally** and use `local-folder` mode pointed at it (`IMAGES_DIR`).

## Common commands

| Command | Does |
|---------|------|
| `python judge.py --dry-run` | List submissions, no API calls |
| `python judge.py --category painting` | Judge only Painting entries |
| `python judge.py --school "Sri Vidya"` | Judge one school |
| `python judge.py --limit 5` | Test on the first 5 |
| `python judge.py --no-cache` | Re-judge from scratch (ignore cache) |
| `python judge.py --model claude-opus-4-8` | Use a stronger model for finals |

Results are **cached** in `output/_cache.json`, so re-runs only judge new entries and
don't spend tokens twice.

## Tuning the rubric

Edit [`rubric.yaml`](./rubric.yaml) — criteria, weights (should sum to 100),
descriptions, and per-age-group guidance. No code changes needed.

## Notes & guardrails

- **Advisory only.** The report is a starting point for human judges, not a verdict.
- The judge is instructed to score *relative to the child's age group*, to ignore photo
  quality, and to flag unclear / off-theme / non-original images in the notes.
- For real fairness, spot-check the AI's top picks and bottom picks before finalising.
- Cost scales with submissions × model. Use `sonnet` for large batches; `opus` for the
  final shortlist if you want a second, stronger opinion.
