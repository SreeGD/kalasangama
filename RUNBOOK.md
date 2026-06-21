# Kala Sangama 2026 — Operations Runbook

The full playbook to run the competition end-to-end, from setup to the grand finale.
Hand this to the core committee. Tick the boxes as you go.

- **Live site:** https://sreegd.github.io/kalasangama/
- **Code repo:** https://github.com/SreeGD/kalasangama
- **Event:** Sri Krishna Janmashtami 2026 · Theme *“Sri Krishna at Vrindavan Village”*
- **Categories:** Coloring (Std 2–5) · Painting (Std 6–10) · top 3 per school advance
- **Core committee:** Svayamprakash Das · Gaurashakti Das · Pratik Kulkarni · Chaitanyaprasad Das

> **Golden rule:** the AI judging is an **advisory pre-screen only**. Human judges decide
> every winner.

---

## Timeline at a glance

| When | Milestone | Section |
|------|-----------|---------|
| **Now → ASAP** | One-time setup: forms, cards, check-in, wire the site, print posters | [1](#1-one-time-setup-do-this-first) |
| **Now → mid-July** | School outreach + registration | [2](#2-school-outreach--registration) |
| **2nd half of July** (before Independence Day) | Level 1 — in-school competition | [3](#3-level-1--in-school) |
| **After each school's Level 1** | Photograph + name + judge artwork | [4](#4-collect--judge-artwork) |
| **Sat Aug 22 or 29, 10 AM, ICC Temple** | Level 2 — inter-school final + check-in | [5](#5-level-2--inter-school-final) |
| **Main Janmashtami program** | Grand finale — prize cheques | [6](#6-grand-finale) |

> ⚠️ The deck's outreach target was **June 10**. If you're past that, prioritise
> [Section 1](#1-one-time-setup-do-this-first) → [Section 2](#2-school-outreach--registration) today.

---

## 1. One-time setup (do this first)

**Owner: tech volunteer + Svayamprakash Das.** ~30–45 min total.

### 1a. Create the registration forms
- [ ] Open <https://script.google.com> → **New project**.
- [ ] Paste in [`phase2-registration/Code.gs`](phase2-registration/Code.gs), **Save**.
- [ ] Run **`setupAll`**, approve the permission prompt.
- [ ] From **View → Logs**, copy: the **School form URL**, the **Student form URL**, the
      **Submission form** edit URL, and the **Responses Sheet ID**. Keep these safe.
- [ ] Open the **Artwork Submission** form → add the **File upload** question manually
      (Apps Script can't): title it `Artwork photo`, Images only, 1 file, 10 MB.

### 1b. Wire the site (go-live)
- [ ] Edit [`js/config.js`](js/config.js) — replace all 5 `REPLACE` placeholders:
      `forms.school`, `forms.student`, `contact.whatsapp`, `contact.email`, `contact.volunteer`.
- [ ] Commit + push → the live site updates in ~1 min. The browser console warning
      disappears once no placeholder remains.
      ```bash
      git add js/config.js && git commit -m "Wire real form + contact values" && git push
      ```
- [ ] (Optional) drop real `assets/poster-en.png` / `poster-kn.png` / `og-image.png` if the
      design team supplies finals; otherwise the generated posters are already in place.

### 1c. Registration cards (hall tickets)
- [ ] Open the **Responses** spreadsheet → **Extensions → Apps Script**.
- [ ] Add [`phase2-registration/RegistrationCard.gs`](phase2-registration/RegistrationCard.gs),
      set `STUDENT_TAB` to the Student Registration tab name, **Save**.
- [ ] Reload the sheet → use the **Kala Sangama** menu when fees are collected (Section 2).

### 1d. QR check-in web app
- [ ] New Apps Script project → paste [`phase2-registration/Verify.gs`](phase2-registration/Verify.gs).
- [ ] Set `SHEET_ID`, `STUDENT_TAB`, and a private **`VERIFY_SECRET`**.
- [ ] **Deploy → Web app**, *Execute as: Me*, *Who has access: Anyone*. Copy the `/exec` URL.
- [ ] In `RegistrationCard.gs`, set `VERIFY_URL` to that URL and the **same** `VERIFY_SECRET`.
- [ ] Keep `VERIFY_SECRET` private — it stops people guessing IDs.

### 1e. Print posters
- [ ] Send [`assets/print/kala-sangama-posters-print.pdf`](assets/print/kala-sangama-posters-print.pdf)
      to the printer. Tell them **print 100% / actual size** (300×400 mm, 3 mm bleed, crop marks).

✅ **Setup done when:** the live site's Register buttons open real forms, contact chips work,
and a test student row can produce a card PDF.

---

## 2. School outreach & registration

**Owner: whole team, coordinated by Svayamprakash Das.**

- [ ] Approach schools (focus: neighbourhoods around the ICC temple + outposts). Secure
      official permission. Record each school's **point-of-contact**.
- [ ] Share the **poster** (EN/Kannada) + the **School Registration** form link; announce via
      posters, assemblies, WhatsApp.
- [ ] As students pay the fee, the coordinator records them via the **Student Registration**
      form (or bulk-collects and one person enters them).
- [ ] **Issue cards:** in the Responses sheet → **Kala Sangama → Generate cards (paid only)**.
      Print each student's card PDF (from the Drive folder *“Kala Sangama 2026 — Registration
      Cards”*) — it's their **Level 1 hall ticket**.

**Tip:** visit schools regularly to keep momentum (assembly announcements if permitted).

---

## 3. Level 1 — in-school

**Owner: school coordinator + assigned volunteer. Second half of July, before Aug 15.**

- [ ] Students bring their **registration card / hall ticket** to the competition.
- [ ] Theme: *Sri Krishna at Vrindavan Village*. Coloring = Std 2–5, Painting = Std 6–10.
- [ ] Run the competition; each school shortlists its **top 3 coloring + top 3 painting**.
- [ ] (Optional proposals from the deck: customised drawing sheets, Janmashtami invitation
      cards + dry prasad to participants, honour school toppers on Independence Day.)

---

## 4. Collect & judge artwork

**Owner: tech volunteer.** Runs after each school finishes Level 1.

### 4a. Photograph + name the artwork
- [ ] Take a clear, flat, well-lit photo of each shortlisted piece.
- [ ] Name each file (full guide: [`phase3-ai-judging/NAMING.md`](phase3-ai-judging/NAMING.md)):
      ```
      School__Category__Student__YYYY-MM-DD__HHMM[__RegID].jpg
      ```
- [ ] **Shortcut:** generate names from the roster instead of typing —
      ```bash
      python tools/build_filenames.py --csv students.csv --date 2026-07-20            # checklist
      python tools/build_filenames.py --csv students.csv --date 2026-07-20 --rename ./photos --apply
      ```

### 4b. Run the AI pre-screen
- [ ] One-time: `cd phase3-ai-judging && python3 -m venv .venv && source .venv/bin/activate &&
      pip install -r requirements.txt`, then `cp .env.example .env` and add `ANTHROPIC_API_KEY`
      (keep `INPUT_MODE=local-folder`).
- [ ] Put named photos in `input/images/` (or set `IMAGES_DIR`), then:
      ```bash
      python judge.py --dry-run     # check what will be judged
      python judge.py               # judge → output/results.html
      ```
- [ ] Review **`output/results.html`**: per-criterion scores, the **inter-school leaderboard**,
      and AI-recommended **top 3 per school & category**. `output/shortlist.csv` is the
      advancement list.

> The score is **advisory**. Spot-check the AI's top and bottom picks before finalising.
> Rubric lives in [`phase3-ai-judging/rubric.yaml`](phase3-ai-judging/rubric.yaml) — edit freely.

---

## 5. Level 2 — inter-school final

**Owner: full committee. Sat Aug 22 or 29, 10:00 AM, ICC Temple.**

- [ ] Confirm and lock the **single date** (22 *or* 29) — update posters/site if it changes.
- [ ] **Check-in:** a volunteer scans each finalist's card QR with a phone → the
      [Verify](#1d-qr-check-in-web-app) page shows valid/invalid + records attendance. Already
      checked-in shows the time (prevents double entry).
- [ ] Run the finals; **human judges** pick **3 winners per category** (use the AI report as a
      starting reference, not the verdict).
- [ ] Programme: finals + kirtan + short talk + Janmashtami invitations + light prasad +
      press/media coverage.

---

## 6. Grand finale

**Owner: full committee. Main Janmashtami cultural program.**

- [ ] Announce winners and award **prize cheques** on the main stage.
- [ ] Collect photos/coverage for follow-up relationship-building with schools (the long-term
      goal: value-education classes, school programs, festivals, Bhagavad-gita distribution —
      *not* pitched now; built through genuine relationships).

---

## Quick reference

**Values to set once (Section 1):**
`js/config.js` → 5 values · `RegistrationCard.gs` → `STUDENT_TAB`, `VERIFY_URL`, `VERIFY_SECRET`
· `Verify.gs` → `SHEET_ID`, `STUDENT_TAB`, `VERIFY_SECRET` · `phase3-ai-judging/.env` → `ANTHROPIC_API_KEY`

**Where things live:**
| Need | File |
|------|------|
| Site text / translations | `js/i18n.js` |
| Form/contact links | `js/config.js` |
| Generate forms | `phase2-registration/Code.gs` |
| Cards / hall tickets | `phase2-registration/RegistrationCard.gs` |
| QR check-in | `phase2-registration/Verify.gs` |
| Judging | `phase3-ai-judging/judge.py` |
| Filename helper | `phase3-ai-judging/tools/build_filenames.py` |
| Rubric | `phase3-ai-judging/rubric.yaml` |
| Print posters | `assets/print/kala-sangama-posters-print.pdf` |

**Common fixes:**
- *Register buttons say “soon” / console warns* → real values not yet in `js/config.js` (1b).
- *Cards have no QR / QR is plain text* → set `VERIFY_URL` in `RegistrationCard.gs`, regenerate.
- *A photo wasn't judged* → filename didn't match; check the report's “skipped” list, rename, re-run.
- *Judging says “Set ANTHROPIC_API_KEY”* → add it to `phase3-ai-judging/.env`.

*Offered in service by the ISKCON South Bengaluru 60-50 Celebration Team. Hare Krishna.*
