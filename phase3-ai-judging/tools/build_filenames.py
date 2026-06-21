#!/usr/bin/env python3
"""
build_filenames.py — generate Kala Sangama photo filenames from the student roster
==================================================================================
Turns a Student Registration CSV (exported from the Phase-2 Google Sheet) into the
naming convention the judging pipeline expects, so coordinators never hand-type:

    School__Category__Student__YYYY-MM-DD__HHMM[__RegID].jpg

Two modes:

  list (default) — write a checklist CSV of suggested filenames, one per student:
      python tools/build_filenames.py --csv students.csv --date 2026-07-20
      # -> filenames.csv  (reg_id, school, student, category, suggested_name)

  rename — rename a folder of loosely-named photos into the convention by matching
           each file against a key column (RegID by default). Preview first, then --apply:
      python tools/build_filenames.py --csv students.csv --date 2026-07-20 \
             --rename ./photos                 # dry-run preview
      python tools/build_filenames.py --csv students.csv --date 2026-07-20 \
             --rename ./photos --apply         # do it (or --copy ./renamed)

CSV headers are matched loosely (case-insensitive, partial). Category is taken from a
'category' column, or inferred from the standard/class (2-5 = Coloring, 6-10 = Painting).
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
CAT_COLORING, CAT_PAINTING = "Coloring", "Painting"


# ---------------------------------------------------------------- helpers
def colget(row: dict, *needles: str) -> str:
    for n in needles:
        for k, v in row.items():
            if k and n.lower() in k.lower():
                return str(v or "").strip()
    return ""


def col_time(row: dict) -> str:
    """A dedicated time-column lookup that won't grab a 'Timestamp' column."""
    for k, v in row.items():
        if not k:
            continue
        kl = k.lower()
        if "timestamp" in kl or "stamp" in kl:
            continue
        if kl == "time" or kl.endswith(" time") or kl.startswith("time "):
            return str(v or "").strip()
    return ""


def canon_category(raw: str, standard: str) -> str:
    t = (raw or "").strip().lower()
    if t.startswith("color") or t.startswith("colour") or t == "c":
        return CAT_COLORING
    if t.startswith("paint") or t == "p":
        return CAT_PAINTING
    m = re.search(r"\d+", standard or "")          # infer from grade
    if m:
        n = int(m.group())
        if 2 <= n <= 5:
            return CAT_COLORING
        if 6 <= n <= 10:
            return CAT_PAINTING
    return ""


def slug(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "", s or "")        # illegal filename chars
    s = s.replace("__", "_").replace("·", "-")       # protect the field delimiter
    s = re.sub(r"\s+", "-", s.strip())               # spaces -> hyphen
    return s.strip("-") or "NA"


def build_stem(school, category, student, date, time, reg_id) -> str:
    parts = [slug(school), category, slug(student), date]
    if time:
        parts.append(re.sub(r"\D", "", time)[:4])
    if reg_id:
        parts.append(slug(reg_id))
    return "__".join(parts)


def load_roster(csv_path: Path, default_date: str, default_time: str) -> list[dict]:
    if not csv_path.exists():
        sys.exit(f"CSV not found: {csv_path}")
    out = []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for i, row in enumerate(csv.DictReader(f), start=2):  # row 2 = first data row
            student = colget(row, "student full name", "student name", "student", "name")
            if not student:
                continue
            standard = colget(row, "standard", "class", "grade")
            category = canon_category(colget(row, "category"), standard)
            date = colget(row, "competition date", "event date") or default_date \
                or colget(row, "date")
            time = col_time(row) or default_time
            reg_id = colget(row, "registration id", "reg id", "card", "id")
            if not category:
                print(f"⚠  row {i}: can't tell category for {student} "
                      f"(standard='{standard}'), skipping")
                continue
            if not date:
                sys.exit("No date: pass --date YYYY-MM-DD (or add a 'date' column).")
            out.append({
                "school": colget(row, "school name", "school"),
                "student": student, "category": category,
                "standard": standard, "date": date, "time": time, "reg_id": reg_id,
                "stem": build_stem(colget(row, "school name", "school"), category,
                                   student, date, time, reg_id),
            })
    return out


# ---------------------------------------------------------------- modes
def mode_list(roster: list[dict], out_path: Path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["reg_id", "school", "student", "category", "suggested_name"])
        for r in roster:
            w.writerow([r["reg_id"], r["school"], r["student"], r["category"],
                        r["stem"] + ".jpg"])
    print(f"✅ Wrote {len(roster)} suggested filenames → {out_path}")
    print("   Rename each student's photo to its 'suggested_name' (any image extension).")


def mode_rename(roster, src: Path, key_field: str, apply: bool, copy_to: Path | None):
    if not src.is_dir():
        sys.exit(f"--rename folder not found: {src}")
    # index roster by the chosen key (lowercased) for matching against filenames
    index = {}
    for r in roster:
        kv = r.get(key_field, "")
        if kv:
            index[kv.lower()] = r
    if not index:
        sys.exit(f"No usable '{key_field}' values in the roster to match filenames against.")

    planned, unmatched = [], []
    for p in sorted(src.iterdir()):
        if p.suffix.lower() not in IMG_EXTS or p.name.startswith("."):
            continue
        stem_lc = p.stem.lower()
        hit = next((r for kv, r in index.items() if kv in stem_lc), None)
        if not hit:
            unmatched.append(p.name)
            continue
        planned.append((p, hit["stem"] + p.suffix.lower()))

    if copy_to:
        copy_to.mkdir(parents=True, exist_ok=True)
    print(f"{'APPLYING' if apply else 'PREVIEW (dry-run)'} — {len(planned)} file(s):\n")
    for src_p, new_name in planned:
        dest = (copy_to or src_p.parent) / new_name
        print(f"  {src_p.name}\n    → {dest.name}")
        if apply:
            data = src_p.read_bytes()
            dest.write_bytes(data)
            if not copy_to and dest != src_p:
                src_p.unlink()
    if unmatched:
        print(f"\n⚠  {len(unmatched)} file(s) had no matching {key_field}: "
              + ", ".join(unmatched))
    if not apply:
        print("\nNothing changed. Re-run with --apply (add --copy DIR to keep originals).")


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="Generate Kala Sangama photo filenames")
    ap.add_argument("--csv", required=True, help="Student Registration CSV export")
    ap.add_argument("--date", default="", help="Competition date YYYY-MM-DD (or a 'date' column)")
    ap.add_argument("--time", default="", help="Default time HHMM (optional)")
    ap.add_argument("--out", default="filenames.csv", help="list mode output CSV")
    ap.add_argument("--rename", metavar="DIR", help="rename photos in DIR into the convention")
    ap.add_argument("--key", default="reg_id",
                    choices=["reg_id", "student"], help="field to match filenames on (rename mode)")
    ap.add_argument("--apply", action="store_true", help="actually rename (rename mode)")
    ap.add_argument("--copy", metavar="DIR", help="copy renamed files here instead of in-place")
    args = ap.parse_args()

    roster = load_roster(Path(args.csv), args.date.strip(), args.time.strip())
    if not roster:
        sys.exit("No usable student rows found in the CSV.")

    if args.rename:
        mode_rename(roster, Path(args.rename), args.key, args.apply,
                    Path(args.copy) if args.copy else None)
    else:
        mode_list(roster, Path(args.out))


if __name__ == "__main__":
    main()
