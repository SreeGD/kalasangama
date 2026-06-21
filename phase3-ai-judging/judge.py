#!/usr/bin/env python3
"""
Kala Sangama 2026 — AI judging pipeline (admin-run, advisory pre-screen)
========================================================================
Reads shortlisted artwork submissions, scores each painting against the rubric
using Claude vision, and writes a ranked report (CSV + HTML) for human judges.

Input modes (set INPUT_MODE in .env):
  local-folder — a folder of images named with all the metadata. No CSV, no
                 Google setup. (recommended; the default)
  local        — a CSV + a folder of images.
  drive        — read the Google Form responses Sheet and download images from Drive.
  drive-folder — read images straight from a Google Drive folder (coming soon).

Filename convention for local-folder / drive-folder:
  School__Category__Student__YYYY-MM-DD__HHMM[__RegID].ext
  e.g.  Sri-Vidya-School__Coloring__Diya-Sharma__2026-07-20__1015.jpg
  - fields split on "__"; "-" inside a field becomes a space on display
  - Category is Coloring or Painting (C / P also accepted)
  - Time and RegID are optional (time falls back to the file's modified time)

Usage:
  python judge.py                         # judge everything
  python judge.py --category painting     # only one category
  python judge.py --school "ABC School"   # only one school
  python judge.py --limit 5               # quick test on first 5
  python judge.py --dry-run               # list submissions, no API calls

Outputs (in OUTPUT_DIR): results.html, results.csv, shortlist.csv (top-3 per
school & category). The AI score is ADVISORY — human judges decide final winners.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import re
import sys
import time
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

# ---- third-party (see requirements.txt) ----
try:
    import yaml
    from dotenv import load_dotenv
    from anthropic import Anthropic
except ImportError as e:  # pragma: no cover
    sys.exit(f"Missing dependency: {e}. Run:  pip install -r requirements.txt")

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", HERE / "output"))
CACHE_PATH = OUTPUT_DIR / "_cache.json"
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".gif": "image/gif"}

# Canonical category labels (must match the keys in rubric.yaml -> category_notes)
CAT_COLORING = "Coloring (Std 2–5)"
CAT_PAINTING = "Painting (Std 6–10)"

# Filenames that didn't match the convention (surfaced in the report)
UNMATCHED: list[str] = []


# ===========================================================================
# Data model
# ===========================================================================
@dataclass
class Submission:
    sub_id: str            # stable unique id (used for caching)
    school: str
    student: str
    category: str
    standard: str = ""
    title: str = ""
    date: str = ""         # YYYY-MM-DD
    time: str = ""         # HHMM
    reg_id: str = ""       # optional Phase-2 card id, e.g. KS2026-0042
    image_path: Path | None = None   # local mode
    image_bytes: bytes | None = None # drive mode (downloaded in memory)
    image_media_type: str = "image/jpeg"

    def load_b64(self) -> tuple[str, str]:
        if self.image_bytes is not None:
            data = self.image_bytes
            media = self.image_media_type
        else:
            data = self.image_path.read_bytes()
            media = MEDIA_TYPES.get(self.image_path.suffix.lower(), "image/jpeg")
        return base64.standard_b64encode(data).decode("ascii"), media


@dataclass
class Result:
    submission: Submission
    scores: dict = field(default_factory=dict)   # criterion key -> 0..scale_max
    weighted_total: float = 0.0                   # 0..100
    notes: str = ""
    error: str = ""


# ===========================================================================
# Rubric
# ===========================================================================
def load_rubric() -> dict:
    with open(HERE / "rubric.yaml", "r", encoding="utf-8") as f:
        r = yaml.safe_load(f)
    total = sum(c["weight"] for c in r["criteria"])
    if abs(total - 100) > 0.01:
        print(f"⚠  Rubric weights sum to {total}, not 100. Scores will be normalised.")
    return r


def build_prompt(rubric: dict, sub: Submission) -> str:
    scale = rubric.get("scale_max", 10)
    lines = [
        f'You are an art-competition judge for "Kala Sangama 2026", a children\'s '
        f'art contest on the theme "{rubric["theme"]}".',
        "",
        f"Entry — Category: {sub.category}; Standard/Class: {sub.standard or 'n/a'}; "
        f"Student: {sub.student}; School: {sub.school}.",
        "",
        f"Score the artwork on each criterion from 0 to {scale} (decimals allowed):",
    ]
    for c in rubric["criteria"]:
        lines.append(f'  - "{c["key"]}" ({c["name"]}, weight {c["weight"]}%): '
                     f'{c["description"].strip()}')
    note = (rubric.get("category_notes") or {}).get(sub.category)
    if note:
        lines += ["", f"Age-group guidance: {note.strip()}"]
    if rubric.get("guidance"):
        lines += ["", rubric["guidance"].strip()]
    keys = ", ".join(f'"{c["key"]}"' for c in rubric["criteria"])
    lines += [
        "",
        "Respond with ONLY a JSON object, no markdown, in exactly this shape:",
        '{',
        f'  "scores": {{ {keys} : <number> }},',
        '  "notes": "<2-3 sentence justification, encouraging and specific>",',
        '  "concerns": "<empty string, or note if image unclear / off-theme / not original>"',
        '}',
    ]
    return "\n".join(lines)


def weighted_total(rubric: dict, scores: dict) -> float:
    scale = rubric.get("scale_max", 10)
    wsum = sum(c["weight"] for c in rubric["criteria"]) or 100
    total = 0.0
    for c in rubric["criteria"]:
        s = float(scores.get(c["key"], 0) or 0)
        total += (s / scale) * (c["weight"] / wsum) * 100
    return round(total, 1)


# ===========================================================================
# Judging
# ===========================================================================
def judge_one(client: Anthropic, model: str, rubric: dict, sub: Submission,
              retries: int = 3) -> Result:
    b64, media = sub.load_b64()
    prompt = build_prompt(rubric, sub)
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {
                            "type": "base64", "media_type": media, "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            text = "".join(b.text for b in msg.content if b.type == "text").strip()
            data = _parse_json(text)
            scores = {k: float(v) for k, v in (data.get("scores") or {}).items()}
            res = Result(submission=sub, scores=scores,
                         weighted_total=weighted_total(rubric, scores),
                         notes=data.get("notes", ""))
            if data.get("concerns"):
                res.notes = (res.notes + f"  [Concern: {data['concerns']}]").strip()
            return res
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            if attempt < retries:
                time.sleep(2 * attempt)
    return Result(submission=sub, error=last_err)


def _parse_json(text: str) -> dict:
    if "```" in text:  # strip code fences if the model added them
        text = text.split("```")[1].lstrip("json").strip() if "```" in text else text
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON in model response: {text[:200]}")
    return json.loads(text[start:end + 1])


# ===========================================================================
# Input loaders
# ===========================================================================
def load_local() -> list[Submission]:
    """CSV columns (header, case-insensitive): school, student, category,
    standard, title, image. `image` is a filename in IMAGES_DIR (or a path)."""
    csv_path = Path(os.getenv("INPUT_CSV", HERE / "input" / "submissions.csv"))
    images_dir = Path(os.getenv("IMAGES_DIR", HERE / "input" / "images"))
    if not csv_path.exists():
        sys.exit(f"INPUT_CSV not found: {csv_path}\nSee README for the local-mode format.")
    subs: list[Submission] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f), start=1):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            img = row.get("image", "")
            if not img:
                continue
            p = Path(img)
            if not p.is_absolute():
                p = images_dir / img
            if not p.exists():
                print(f"⚠  row {i}: image not found, skipping: {p}")
                continue
            subs.append(Submission(
                sub_id=row.get("id") or f"{row.get('school','')}|{row.get('student','')}|{img}",
                school=row.get("school", ""), student=row.get("student", ""),
                category=row.get("category", ""), standard=row.get("standard", ""),
                title=row.get("title", ""), image_path=p))
    return subs


def canon_category(raw: str) -> str:
    """Map a free-form category token to the canonical rubric label, or '' if unknown."""
    t = (raw or "").strip().lower()
    if t in ("c", "color", "colour", "coloring", "colouring") or t.startswith("color") or t.startswith("colour"):
        return CAT_COLORING
    if t in ("p", "paint", "painting") or t.startswith("paint"):
        return CAT_PAINTING
    return ""


def parse_filename(name: str) -> dict | None:
    """Parse 'School__Category__Student__YYYY-MM-DD__HHMM[__RegID].ext'.
    Returns a metadata dict, or None if it doesn't match the convention."""
    stem = name.rsplit(".", 1)[0]
    parts = [p.strip() for p in stem.split("__") if p.strip() != ""]
    if len(parts) < 4:
        return None
    category = canon_category(parts[1])
    if not category:
        return None
    date = parts[3].strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return None  # 4th field must be an ISO date
    dehyphen = lambda s: s.replace("-", " ").strip()
    # Remaining tokens after the date are time and/or RegID, in any order:
    # a 3-4 digit token is the time; anything else is the RegID.
    time, reg_id = "", ""
    for tok in (p.strip() for p in parts[4:]):
        if not tok:
            continue
        if not time and re.match(r"^\d{3,4}$", tok):
            time = tok
        elif not reg_id:
            reg_id = tok
    return {
        "school": dehyphen(parts[0]),
        "category": category,
        "student": dehyphen(parts[2]),
        "date": date,
        "time": time,
        "reg_id": reg_id,
    }


def load_local_folder() -> list[Submission]:
    """Scan a folder of images whose FILENAMES carry the metadata (no CSV)."""
    folder = Path(os.getenv("IMAGES_DIR", HERE / "input" / "images"))
    if not folder.is_dir():
        sys.exit(f"IMAGES_DIR not found: {folder}\nSee README for the filename convention.")
    by_key: dict[tuple, Submission] = {}
    subs: list[Submission] = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() not in MEDIA_TYPES or p.name.startswith("."):
            continue
        meta = parse_filename(p.name)
        if not meta:
            UNMATCHED.append(p.name)
            print(f"⚠  filename does not match convention, skipping: {p.name}")
            continue
        if not meta["time"]:
            meta["time"] = datetime.fromtimestamp(p.stat().st_mtime).strftime("%H%M")
        sub = Submission(
            sub_id=meta["reg_id"] or p.name,
            school=meta["school"], student=meta["student"], category=meta["category"],
            date=meta["date"], time=meta["time"], reg_id=meta["reg_id"], image_path=p)
        # dedupe same student+category, keeping the latest by date+time
        key = (meta["reg_id"] or f'{sub.school}|{sub.student}|{sub.category}'.lower())
        prev = by_key.get(key)
        if prev and (prev.date, prev.time) >= (sub.date, sub.time):
            print(f"⚠  duplicate, keeping newer: {p.name}")
            continue
        if prev:
            print(f"⚠  duplicate, replacing older entry for {sub.student} ({sub.category})")
            subs.remove(prev)
        by_key[key] = sub
        subs.append(sub)
    return subs


def load_drive_folder() -> list[Submission]:
    """Read images straight from a Google Drive folder, using the same filename
    convention. (Coming soon — implemented in the next phase.)"""
    sys.exit("INPUT_MODE=drive-folder is coming soon. Use 'local-folder' for now "
             "(download/sync the Drive folder locally and point IMAGES_DIR at it).")


def load_drive() -> list[Submission]:
    """Read the Google Form responses Sheet and download artwork from Drive
    using a service account. Needs google-api-python-client + gspread."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit("Drive mode needs extra deps:\n"
                 "  pip install gspread google-api-python-client google-auth")
    sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    sheet_id = os.getenv("SHEET_ID")
    tab = os.getenv("SHEET_TAB", "Form Responses 1")
    if not (sa and sheet_id):
        sys.exit("Drive mode needs GOOGLE_SERVICE_ACCOUNT_JSON and SHEET_ID in .env")
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly",
              "https://www.googleapis.com/auth/drive.readonly"]
    creds = Credentials.from_service_account_file(sa, scopes=scopes)
    rows = gspread.authorize(creds).open_by_key(sheet_id).worksheet(tab).get_all_records()
    drive = build("drive", "v3", credentials=creds)

    def colget(row, *names):
        for n in names:
            for k, v in row.items():
                if n.lower() in k.lower():
                    return str(v).strip()
        return ""

    subs: list[Submission] = []
    for i, row in enumerate(rows, start=1):
        link = colget(row, "Artwork photo", "artwork", "upload", "photo")
        fid = _drive_file_id(link)
        if not fid:
            continue
        try:
            meta = drive.files().get(fileId=fid, fields="mimeType,name").execute()
            data = drive.files().get_media(fileId=fid).execute()
        except Exception as e:  # noqa: BLE001
            print(f"⚠  row {i}: could not download {link}: {e}")
            continue
        subs.append(Submission(
            sub_id=fid,
            school=colget(row, "School name", "school"),
            student=colget(row, "Student full name", "student", "name"),
            category=colget(row, "Category"),
            standard=colget(row, "Standard", "Class"),
            title=colget(row, "Artwork title", "title"),
            image_bytes=data,
            image_media_type=meta.get("mimeType", "image/jpeg")))
    return subs


def _drive_file_id(link: str) -> str:
    if not link:
        return ""
    for marker in ("id=", "/d/", "/file/d/"):
        if marker in link:
            rest = link.split(marker, 1)[1]
            return rest.split("&")[0].split("/")[0]
    return link if "/" not in link else ""


# ===========================================================================
# Reporting
# ===========================================================================
def write_reports(rubric: dict, results: list[Result]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    crit_keys = [c["key"] for c in rubric["criteria"]]
    ok = [r for r in results if not r.error]

    # rank within (category, school) -> the top-3 advancement list
    rank_in_school: dict[int, int] = {}
    seen: dict[tuple, int] = {}
    for r in sorted(ok, key=lambda r: (r.submission.category, r.submission.school, -r.weighted_total)):
        key = (r.submission.category, r.submission.school)
        seen[key] = seen.get(key, 0) + 1
        rank_in_school[id(r)] = seen[key]

    # rank within category across all schools -> inter-school leaderboard
    overall_rank: dict[int, int] = {}
    seenc: dict[str, int] = {}
    for r in sorted(ok, key=lambda r: (r.submission.category, -r.weighted_total)):
        c = r.submission.category
        seenc[c] = seenc.get(c, 0) + 1
        overall_rank[id(r)] = seenc[c]

    # full results.csv
    csv_path = OUTPUT_DIR / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "school", "student", "date", "time", "reg_id",
                    "weighted_total", "rank_in_school", "top3", "overall_rank",
                    *crit_keys, "notes", "error"])
        for r in sorted(results, key=lambda r: (r.submission.category,
                        r.submission.school, -r.weighted_total)):
            s = r.submission
            rk = rank_in_school.get(id(r), "")
            w.writerow([s.category, s.school, s.student, s.date, s.time, s.reg_id,
                        r.weighted_total, rk,
                        "yes" if isinstance(rk, int) and rk <= 3 else "",
                        overall_rank.get(id(r), ""),
                        *[r.scores.get(k, "") for k in crit_keys], r.notes, r.error])

    # shortlist.csv — only the recommended top-3 per school & category
    with open(OUTPUT_DIR / "shortlist.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "school", "rank_in_school", "student", "reg_id", "weighted_total"])
        for r in sorted(ok, key=lambda r: (r.submission.category, r.submission.school,
                        rank_in_school[id(r)])):
            if rank_in_school[id(r)] <= 3:
                s = r.submission
                w.writerow([s.category, s.school, rank_in_school[id(r)], s.student,
                            s.reg_id, r.weighted_total])

    _write_html(rubric, results, rank_in_school, overall_rank, crit_keys)
    return csv_path


def _write_html(rubric, results, rank_in_school, overall_rank, crit_keys):
    import html
    ok = [x for x in results if not x.error]

    # per-category inter-school leaderboards (top 5)
    cats: dict[str, list] = {}
    for r in ok:
        cats.setdefault(r.submission.category, []).append(r)
    boards = []
    for cat in sorted(cats):
        top = sorted(cats[cat], key=lambda r: overall_rank[id(r)])[:5]
        items = "".join(
            f'<li><b>{overall_rank[id(r)]}.</b> {html.escape(r.submission.student)} '
            f'<small>· {html.escape(r.submission.school)}</small> '
            f'<span class="score">{r.weighted_total}</span></li>' for r in top)
        boards.append(f'<div class="board"><h3>{html.escape(cat)}</h3><ol class="lb">{items}</ol></div>')

    rows = []
    for r in sorted(ok, key=lambda r: (r.submission.category, r.submission.school, -r.weighted_total)):
        s = r.submission
        rk = rank_in_school.get(id(r), "")
        top = "top3" if isinstance(rk, int) and rk <= 3 else ""
        img = ""
        if s.image_path:
            img = f'<img src="{html.escape(os.path.relpath(s.image_path, OUTPUT_DIR))}" loading="lazy">'
        when = html.escape((s.date + (" " + s.time if s.time else "")).strip())
        crit_cells = "".join(f"<td>{r.scores.get(k,'')}</td>" for k in crit_keys)
        rows.append(
            f'<tr class="{top}"><td>{img}</td><td>{html.escape(s.category)}</td>'
            f'<td>{html.escape(s.school)}</td>'
            f'<td>{html.escape(s.student)}<br><small>{when}'
            f'{(" · " + html.escape(s.reg_id)) if s.reg_id else ""}</small></td>'
            f'<td class="score">{r.weighted_total}</td><td>{rk}</td><td>{overall_rank.get(id(r),"")}</td>'
            f'{crit_cells}<td class="notes">{html.escape(r.notes)}</td></tr>')

    errs = "".join(f"<li>{html.escape(r.submission.student)} "
                   f"({html.escape(r.submission.school)}): {html.escape(r.error)}</li>"
                   for r in results if r.error)
    unmatched = "".join(f"<li>{html.escape(n)}</li>" for n in UNMATCHED)
    head = "".join(f"<th>{html.escape(c['name'])}</th>" for c in rubric["criteria"])
    doc = f"""<!doctype html><meta charset=utf-8>
<title>Kala Sangama 2026 — AI Judging Report</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:24px;color:#3a2414;background:#fbf8e9}}
 h1{{color:#4a1d0a;margin-bottom:2px}} h3{{color:#4a1d0a;margin:0 0 8px}} .sub{{color:#7a5c44}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 4px 14px rgba(74,29,10,.08)}}
 th,td{{border-bottom:1px solid #eee;padding:8px 10px;text-align:left;vertical-align:top;font-size:14px}}
 th{{background:#4a1d0a;color:#f8d9b8;position:sticky;top:0}}
 img{{width:84px;height:84px;object-fit:cover;border-radius:8px}}
 .score{{font-weight:700;font-size:16px;color:#c4630b}}
 tr.top3{{background:#fff6e8}} tr.top3 .score{{color:#a8500a}}
 .notes{{max-width:300px;color:#555}} .legend{{margin:10px 0;color:#7a5c44}}
 .boards{{display:flex;flex-wrap:wrap;gap:18px;margin:16px 0 26px}}
 .board{{background:#fff;border-radius:12px;padding:14px 18px;box-shadow:0 4px 14px rgba(74,29,10,.08);min-width:280px}}
 .lb{{margin:0;padding-left:4px;list-style:none}} .lb li{{padding:4px 0;border-bottom:1px solid #f3ead2}}
 .lb small{{color:#7a5c44}}
 .err{{background:#fff0f0;border:1px solid #f3c0c0;padding:10px;border-radius:8px;margin-top:18px}}
 .warn{{background:#fff8e8;border:1px solid #f0d9a8;padding:10px;border-radius:8px;margin-top:18px}}
</style>
<h1>Kala Sangama 2026 — AI Judging Report</h1>
<p class=sub>Theme: <b>{html.escape(rubric['theme'])}</b> · Advisory pre-screen — human judges decide final winners.</p>

<h3>Inter-school leaderboard (overall, per category)</h3>
<div class=boards>{''.join(boards)}</div>

<p class=legend>Highlighted rows = AI-recommended top 3 within that school &amp; category (the Level-1 advancement list — see <b>shortlist.csv</b>).</p>
<table><thead><tr><th>Art</th><th>Category</th><th>School</th><th>Student</th>
<th>Score /100</th><th>In-school</th><th>Overall</th>{head}<th>Notes</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{f'<div class=err><b>Could not judge ({errs.count("<li>")}):</b><ul>{errs}</ul></div>' if errs else ''}
{f'<div class=warn><b>Skipped — filename did not match the convention ({len(UNMATCHED)}):</b><ul>{unmatched}</ul></div>' if unmatched else ''}
"""
    (OUTPUT_DIR / "results.html").write_text(doc, encoding="utf-8")


# ===========================================================================
# Cache (skip re-judging unchanged submissions)
# ===========================================================================
def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")


# ===========================================================================
# Main
# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description="Kala Sangama AI judging pipeline")
    ap.add_argument("--category")
    ap.add_argument("--school")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="list submissions, no API calls")
    args = ap.parse_args()

    mode = os.getenv("INPUT_MODE", "local-folder").lower()
    print(f"Input mode: {mode} · model: {args.model}")
    loaders = {
        "local-folder": load_local_folder,
        "local": load_local,
        "drive": load_drive,
        "drive-folder": load_drive_folder,
    }
    if mode not in loaders:
        sys.exit(f"Unknown INPUT_MODE '{mode}'. Choose: {', '.join(loaders)}")
    subs = loaders[mode]()

    if args.category:
        subs = [s for s in subs if args.category.lower() in s.category.lower()]
    if args.school:
        subs = [s for s in subs if args.school.lower() in s.school.lower()]
    if args.limit:
        subs = subs[: args.limit]
    print(f"Loaded {len(subs)} submission(s).")

    if args.dry_run:
        for s in subs:
            when = f"{s.date} {s.time}".strip()
            tag = f" · {s.reg_id}" if s.reg_id else ""
            print(f"  - [{s.category}] {s.school} / {s.student}  ({when}){tag}")
        if UNMATCHED:
            print(f"\n{len(UNMATCHED)} file(s) skipped (bad filename): " + ", ".join(UNMATCHED))
        return

    if not subs:
        sys.exit("No submissions to judge.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Set ANTHROPIC_API_KEY in phase3-ai-judging/.env")

    rubric = load_rubric()
    client = Anthropic(api_key=api_key)
    cache = {} if args.no_cache else load_cache()
    results: list[Result] = []

    for i, sub in enumerate(subs, start=1):
        tag = f"[{i}/{len(subs)}] {sub.school} / {sub.student}"
        cached = cache.get(sub.sub_id)
        if cached and not args.no_cache:
            print(f"{tag} — cached")
            r = Result(submission=sub, scores=cached["scores"],
                       weighted_total=cached["weighted_total"], notes=cached["notes"],
                       error=cached.get("error", ""))
        else:
            print(f"{tag} — judging…")
            r = judge_one(client, args.model, rubric, sub)
            if not r.error:
                cache[sub.sub_id] = {"scores": r.scores,
                                     "weighted_total": r.weighted_total, "notes": r.notes}
            else:
                print(f"     ⚠ {r.error}")
        results.append(r)

    if not args.no_cache:
        save_cache(cache)
    csv_path = write_reports(rubric, results)
    judged = sum(1 for r in results if not r.error)
    print(f"\n✅ Judged {judged}/{len(results)}." +
          (f"  ({len(UNMATCHED)} file(s) skipped — bad filename)" if UNMATCHED else ""))
    print(f"   HTML     : {OUTPUT_DIR / 'results.html'}")
    print(f"   CSV      : {csv_path}")
    print(f"   Shortlist: {OUTPUT_DIR / 'shortlist.csv'}")


if __name__ == "__main__":
    main()
