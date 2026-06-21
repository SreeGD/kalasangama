# Photo naming guide (for coordinators)

Name each artwork photo like this, then drop it in the folder:

```
School__Category__Student__YYYY-MM-DD__HHMM.jpg
```

- Separate the parts with **two underscores** `__`
- Use a hyphen `-` for spaces in names (or just leave spaces — both work)
- **Category** = `Coloring` or `Painting`
- **Date** = year-month-day, e.g. `2026-07-20`
- **Time** = 24-hour `HHMM`, e.g. `1015` *(optional — leave it out and the file's
  own timestamp is used)*
- You can add the registration card id at the end *(optional)*: `…__KS2026-0042.jpg`

### Good examples
```
Sri-Vidya-School__Coloring__Diya-Sharma__2026-07-20__1015.jpg
National Public School__Painting__Ishan Rao__2026-07-21__0930.png
Mount-Carmel__Painting__Aisha-Khan__2026-07-21__1145__KS2026-0107.jpg
```

### Tips
- Allowed image types: `.jpg .jpeg .png .webp`
- Coloring = Std 2–5, Painting = Std 6–10
- If two photos are sent for the same student & category, the **newest** one is used.
- A file that doesn't follow this pattern is skipped and listed in the report so you
  can rename and re-add it.

### Don't want to type names by hand?
Ask the admin for the pre-made name list — `tools/build_filenames.py` turns the
registration sheet into a ready filename for every student, or can auto-rename a folder
of photos for you (match by registration-card id).
