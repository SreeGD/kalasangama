# Phase 2 — Registration (Google Forms)

Registration runs on Google Forms so the committee needs **no servers** and gets
responses straight into a Google Sheet. `Code.gs` generates all three forms in one click.

## Forms created

| Form | Phase | Purpose |
|------|-------|---------|
| **School Registration** | 2 | A school coordinator registers the school + shares a point of contact. |
| **Student Registration** | 2 | Each student registers, picks category by standard, records fee status. |
| **Artwork Submission** | 3 | Coordinators upload photos of shortlisted artwork → feeds the AI judging pipeline. |

## Setup (one time)

1. Open <https://script.google.com> → **New project**.
2. Delete the sample code, paste in [`Code.gs`](./Code.gs), and **Save**.
3. Click **Run** → choose `setupAll` → approve the permission prompt (Forms + Sheets).
4. Open **View → Logs** (or *Execution log*) and copy the printed URLs.
5. Wire the two registration links into the website — edit [`/js/config.js`](../js/config.js):
   ```js
   forms: {
     school:  "https://forms.gle/....",   // School Registration "published" URL
     student: "https://forms.gle/....",   // Student Registration "published" URL
   }
   ```
   The site auto-enables the **Register** buttons once these are filled.

## ⚠ Add the file-upload question manually

Google Apps Script **cannot** create a *File upload* question. After `setupAll` runs:

1. Open the **Artwork Submission** form (use the `edit` URL from the log).
2. Add one question → type **File upload** → title it exactly **`Artwork photo`**.
3. Settings: **Allow only specific file types → Image**, **Maximum number of files: 1**,
   **Maximum file size: 10 MB**.
4. Uploaded images land in a Drive folder the form creates automatically; the response
   Sheet stores a link to each file. Phase 3 reads from there.

> File-upload forms require respondents to be signed into a Google account — fine for
> adult coordinators doing the uploads.

## Where responses go

All three forms write to one spreadsheet: **“Kala Sangama 2026 — Responses”** (one tab per
form). Note its **Sheet ID** from the log — Phase 3's `.env` needs it to read submissions.

## Registration card / hall ticket (auto-generated)

[`RegistrationCard.gs`](./RegistrationCard.gs) turns each **paid** student row into a
saffron card PDF — unique registration ID + QR code — that doubles as the Level 1 hall
ticket. Preview the design in [`card-preview.html`](./card-preview.html) (open in a browser).

**Setup (one-click menu):**
1. Open the **“Kala Sangama 2026 — Responses”** spreadsheet.
2. **Extensions → Apps Script**, paste in `RegistrationCard.gs`, **Save**.
3. Set `STUDENT_TAB` near the top to your Student Registration tab name.
4. Reload the spreadsheet → a **“Kala Sangama”** menu appears.
5. **Kala Sangama → Generate cards (paid only)** and approve the permission prompt.

**What it does per student:**
- Mints a stable ID `KS2026-0001`, `KS2026-0002`, … (kept in a new `Registration ID` column).
- Renders the card → PDF, saved to a Drive folder **“Kala Sangama 2026 — Registration Cards”**.
- Writes the PDF link + timestamp back to the sheet (`Card PDF`, `Card Generated At`).
- Optionally emails the card (set `EMAIL_CARDS = true`).

**Options (top of the file):** `PAID_ONLY`, `EMAIL_CARDS`, `ID_PREFIX`, `FOLDER_NAME`,
plus `SHEET_ID` if you run it standalone instead of bound to the sheet. Re-running is safe —
existing IDs are reused and already-generated rows are skipped (use *Regenerate ALL* to
overwrite). The QR encodes `ID | name | category | standard` by default; set `VERIFY_URL`
(below) to make it scan to the live check-in page instead.

## QR check-in / verification ([`Verify.gs`](./Verify.gs))

A mobile web app: scanning a card's QR opens a page that validates the ID against the
sheet and lets a gate volunteer **check the student in** (records a timestamp). Preview
the look in [`verify-preview.html`](./verify-preview.html).

**Deploy:**
1. New Apps Script project (recommended separate from the card generator). Paste in
   `Verify.gs`. Set `SHEET_ID`, `STUDENT_TAB`, and optionally `VERIFY_SECRET`.
2. **Deploy → New deployment → Web app**; *Execute as: Me*, *Who has access: Anyone*.
   Copy the `/exec` URL.
3. In `RegistrationCard.gs`, set `VERIFY_URL` to that URL and `VERIFY_SECRET` to the same
   secret, then **Regenerate ALL** so the QR codes point at the check-in page.

**At the venue:** a volunteer scans a card with any phone camera →
- ✓ green = valid, shows student + fee status + a **Check in** button;
- already checked in = shows when (prevents double entry);
- ✕ red = not found / wrong security code.

Check-in times are written to a `Checked In At` column in the sheet, giving you a live
attendance log.

**Security:** with `VERIFY_SECRET` set, each QR carries a short token (`&k=…`) so people
can't guess IDs to view other students. Without it, anyone with a valid ID can open the
page. Keep the secret private and identical in both files.
