# Phase 3 — AI Judging Pipeline

An **admin-run** script that scores shortlisted artwork against the rubric using Claude
vision and produces a ranked report for human judges. The AI score is an **advisory
pre-screen** — humans decide the final winners.

```
input ──▶ judge.py ──▶ output/results.csv
(CSV+images               output/results.html  ◀── review here
 or Google Sheet+Drive)
```

## Quick start (local mode — no Google setup)

```bash
cd phase3-ai-judging
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then add your ANTHROPIC_API_KEY
# put artwork photos in input/images/ and list them in input/submissions.csv

python judge.py --dry-run     # sanity-check what will be judged
python judge.py               # judge everything → output/results.html
```

Open `output/results.html` in a browser to review scores, per-criterion breakdowns,
and the AI-recommended top 3 per school & category.

### `submissions.csv` columns
`id, school, student, standard, category, title, image` — `image` is a filename in
`IMAGES_DIR`. A sample is included.

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
