/* ============================================================
   Kala Sangama — site configuration
   ------------------------------------------------------------
   ⚠ PLACEHOLDER VALUES — swap before going live.
   Search this file for "REPLACE" to find every value to update.
   ============================================================ */
window.KALA_CONFIG = {
  // Phase 2 — Google Form links (paste the published form URLs from the
  // Apps Script setupAll log). These activate the "Register" buttons.
  forms: {
    school:  "https://forms.gle/REPLACE-school-registration",   // REPLACE
    student: "https://forms.gle/REPLACE-student-registration",  // REPLACE
  },

  // Contact details for the core committee.
  contact: {
    whatsapp:  "910000000000",                       // REPLACE — country code + number, digits only
    email:     "enquiries@kalasangama.example",      // REPLACE — committee enquiry email
    volunteer: "https://forms.gle/REPLACE-volunteer", // REPLACE — seva sign-up form/link
  },

  // Pre-filled WhatsApp share message (used by the "Share on WhatsApp" button).
  shareText: "Kala Sangama — Sri Krishna Janmashtami 2026 inter-school painting & coloring competition by ISKCON South Bengaluru. Theme: Sri Krishna at Vrindavan Village.",
};
