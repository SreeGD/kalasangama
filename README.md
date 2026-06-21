# Kala Sangama 2026

Website & tooling for **Kala Sangama** — the Sri Krishna Janmashtami 2026 inter-school
coloring & painting competition by **ISKCON South Bengaluru | ICC Mega School Outreach**.
Theme: *“Sri Krishna at Vrindavan Village.”*

Built in three phases, each deployable independently:

| Phase | What | Tech | Folder |
|------|------|------|--------|
| **1 — Marketing** | Bilingual (English/ಕನ್ನಡ) landing page: about, categories, timeline, promotion, contact | Static HTML/CSS/JS (no build step) | this folder + `css/`, `js/`, `assets/` |
| **2 — Registration** | School + student registration via Google Forms → Google Sheet | Google Apps Script | [`phase2-registration/`](phase2-registration/) |
| **3 — AI Judging** | Admin-run pipeline scoring artwork photos against the rubric via Claude vision | Python | [`phase3-ai-judging/`](phase3-ai-judging/) |

## Phase 1 — run / deploy the site

It's a plain static site. To preview locally:

```bash
python3 -m http.server 8000   # then open http://localhost:8000
```

Deploy by uploading the folder to any static host — **GitHub Pages, Netlify, Vercel,
Cloudflare Pages**, or a temple web server. No build step.

**Before launch, edit [`js/config.js`](js/config.js):**
- `forms.school` / `forms.student` → the Phase 2 Google Form links
- `contact.whatsapp` / `contact.email` / `contact.volunteer` → committee contacts

Add posters to `assets/` (`poster-en.png`, `poster-kn.png`, `og-image.png`) — see
[`assets/README.md`](assets/README.md). The page degrades gracefully if they're absent.

### Editing content / translations
All text lives in [`js/i18n.js`](js/i18n.js) as `en` and `kn` dictionaries keyed to
`data-i18n` attributes in `index.html`. Keep both languages in sync (92 keys each).

## Phase 2 — set up registration
See [`phase2-registration/README.md`](phase2-registration/README.md). One Apps Script
run creates the School, Student, and Artwork-Submission forms wired to one Sheet.

## Phase 3 — run the AI judging
See [`phase3-ai-judging/README.md`](phase3-ai-judging/README.md). Reads submissions
(a folder of named images — see [NAMING.md](phase3-ai-judging/NAMING.md) — or a CSV, or
the Google Sheet+Drive), scores each piece against
[`rubric.yaml`](phase3-ai-judging/rubric.yaml), and writes a ranked `results.html`,
`results.csv`, and `shortlist.csv` (top-3 per school & category). **Advisory only** —
human judges decide final winners.

---

### Event at a glance
- **Categories:** Coloring (Std 2–5), Painting (Std 6–10) — top 3 per school advance.
- **Level 1:** within schools, second half of July 2026.
- **Level 2 (final):** ICC Temple, 10 AM, Sat **Aug 22 or 29, 2026**.
- **Grand finale:** winners announced at the main Janmashtami cultural program.

*Offered in service by the ISKCON South Bengaluru 60-50 Celebration Team. Hare Krishna.*
