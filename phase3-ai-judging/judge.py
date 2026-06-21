#!/usr/bin/env python3
"""
Kala Sangama 2026 — AI judging pipeline (admin-run, advisory pre-screen)
========================================================================
Reads shortlisted artwork submissions, scores each painting against the rubric
using Claude vision, and writes a ranked report (CSV + HTML) for human judges.

Two input modes (set INPUT_MODE in .env):
  local  — point at a CSV + a folder of images. Zero Google setup. (default)
  drive  — read the Google Form responses Sheet and download images from Drive
           via a Google service account.

Usage:
  python judge.py                         # judge everything
  python judge.py --category painting     # only one category
  python judge.py --school "ABC School"   # only one school
  python judge.py --limit 5               # quick test on first 5
  python judge.py --dry-run               # list submissions, no API calls

The AI score is ADVISORY. Final winners are chosen by human judges.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
import time
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

    # Rank within (category, school): mark recommended top-3 per school/category.
    ok = [r for r in results if not r.error]
    ok.sort(key=lambda r: (r.submission.category, r.submission.school, -r.weighted_total))
    rank_in_school: dict[int, int] = {}
    seen: dict[tuple, int] = {}
    for r in ok:
        key = (r.submission.category, r.submission.school)
        seen[key] = seen.get(key, 0) + 1
        rank_in_school[id(r)] = seen[key]

    # CSV
    csv_path = OUTPUT_DIR / "results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "school", "student", "standard", "weighted_total",
                    "rank_in_school", *crit_keys, "notes", "error"])
        for r in sorted(results, key=lambda r: (r.submission.category,
                        r.submission.school, -r.weighted_total)):
            w.writerow([r.submission.category, r.submission.school, r.submission.student,
                        r.submission.standard, r.weighted_total,
                        rank_in_school.get(id(r), ""),
                        *[r.scores.get(k, "") for k in crit_keys],
                        r.notes, r.error])

    _write_html(rubric, results, rank_in_school, crit_keys)
    return csv_path


def _write_html(rubric, results, rank_in_school, crit_keys):
    import html
    rows = []
    for r in sorted([x for x in results if not x.error],
                    key=lambda r: (r.submission.category, r.submission.school, -r.weighted_total)):
        s = r.submission
        rk = rank_in_school.get(id(r), "")
        top = "top3" if isinstance(rk, int) and rk <= 3 else ""
        img = ""
        if s.image_path:
            img = f'<img src="{html.escape(os.path.relpath(s.image_path, OUTPUT_DIR))}" loading="lazy">'
        crit_cells = "".join(f"<td>{r.scores.get(k,'')}</td>" for k in crit_keys)
        rows.append(
            f'<tr class="{top}"><td>{img}</td><td>{html.escape(s.category)}</td>'
            f'<td>{html.escape(s.school)}</td><td>{html.escape(s.student)} '
            f'<small>{html.escape(s.standard)}</small></td>'
            f'<td class="score">{r.weighted_total}</td><td>{rk}</td>{crit_cells}'
            f'<td class="notes">{html.escape(r.notes)}</td></tr>')
    errs = "".join(f"<li>{html.escape(r.submission.student)} "
                   f"({html.escape(r.submission.school)}): {html.escape(r.error)}</li>"
                   for r in results if r.error)
    head = "".join(f"<th>{html.escape(c['name'])}</th>" for c in rubric["criteria"])
    doc = f"""<!doctype html><meta charset=utf-8>
<title>Kala Sangama 2026 — AI Judging Report</title>
<style>
 body{{font-family:system-ui,sans-serif;margin:24px;color:#3a2414;background:#fbf8e9}}
 h1{{color:#4a1d0a}} .sub{{color:#7a5c44}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 4px 14px rgba(74,29,10,.08)}}
 th,td{{border-bottom:1px solid #eee;padding:8px 10px;text-align:left;vertical-align:top;font-size:14px}}
 th{{background:#4a1d0a;color:#f8d9b8;position:sticky;top:0}}
 img{{width:84px;height:84px;object-fit:cover;border-radius:8px}}
 .score{{font-weight:700;font-size:16px;color:#c4630b}}
 tr.top3{{background:#fff6e8}} tr.top3 .score{{color:#a8500a}}
 .notes{{max-width:320px;color:#555}} .legend{{margin:10px 0;color:#7a5c44}}
 .err{{background:#fff0f0;border:1px solid #f3c0c0;padding:10px;border-radius:8px;margin-top:18px}}
</style>
<h1>Kala Sangama 2026 — AI Judging Report</h1>
<p class=sub>Theme: <b>{html.escape(rubric['theme'])}</b> · Advisory pre-screen — human judges decide final winners.</p>
<p class=legend>Highlighted rows = AI-recommended top 3 within that school &amp; category.</p>
<table><thead><tr><th>Art</th><th>Category</th><th>School</th><th>Student</th>
<th>Score /100</th><th>Rank</th>{head}<th>Notes</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{f'<div class=err><b>Could not judge ({errs.count("<li>")}):</b><ul>{errs}</ul></div>' if errs else ''}
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

    mode = os.getenv("INPUT_MODE", "local").lower()
    print(f"Input mode: {mode} · model: {args.model}")
    subs = load_drive() if mode == "drive" else load_local()

    if args.category:
        subs = [s for s in subs if args.category.lower() in s.category.lower()]
    if args.school:
        subs = [s for s in subs if args.school.lower() in s.school.lower()]
    if args.limit:
        subs = subs[: args.limit]
    print(f"Loaded {len(subs)} submission(s).")

    if args.dry_run:
        for s in subs:
            print(f"  - [{s.category}] {s.school} / {s.student} ({s.standard})")
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
    print(f"\n✅ Judged {judged}/{len(results)}.")
    print(f"   CSV : {csv_path}")
    print(f"   HTML: {OUTPUT_DIR / 'results.html'}")


if __name__ == "__main__":
    main()
