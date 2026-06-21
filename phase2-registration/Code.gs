/**
 * Kala Sangama 2026 — Registration & Submission form generator
 * ----------------------------------------------------------------
 * Google Apps Script. Run `setupAll()` once to create:
 *   1. School Registration Form   (Phase 2)
 *   2. Student Registration Form  (Phase 2)
 *   3. Artwork Submission Form    (Phase 3 — feeds the AI judging pipeline)
 * All three are linked to a single Google Sheet for easy export.
 *
 * HOW TO USE
 *   1. Go to https://script.google.com  →  New project.
 *   2. Paste this file in, Save.
 *   3. Run `setupAll`. Approve the permission prompt (Forms + Sheets).
 *   4. Open "Execution log" (View → Logs) and copy the printed URLs:
 *        - Paste the two registration form links into  /js/config.js
 *        - The Submission form's response Sheet ID goes into the Phase 3 .env
 *   5. IMPORTANT: Google Apps Script cannot add a "File upload" question.
 *      Open the Submission form in the editor and add ONE File-upload question
 *      titled "Artwork photo" (Images only, max 1 file, ~10 MB). See README.
 */

var EVENT = 'Kala Sangama 2026';

function setupAll() {
  var ss = SpreadsheetApp.create('Kala Sangama 2026 — Responses');
  var ssId = ss.getId();

  var school = createSchoolForm(ssId);
  var student = createStudentForm(ssId);
  var submission = createSubmissionForm(ssId);

  Logger.log('==================================================');
  Logger.log('RESPONSES SHEET : %s', ss.getUrl());
  Logger.log('SHEET ID (.env) : %s', ssId);
  Logger.log('--------------------------------------------------');
  Logger.log('SCHOOL FORM  (config.js forms.school):  %s', school.getPublishedUrl());
  Logger.log('SCHOOL  edit:  %s', school.getEditUrl());
  Logger.log('STUDENT FORM (config.js forms.student): %s', student.getPublishedUrl());
  Logger.log('STUDENT edit:  %s', student.getEditUrl());
  Logger.log('SUBMISSION FORM (Phase 3 input):        %s', submission.getPublishedUrl());
  Logger.log('SUBMISSION edit (add File-upload here): %s', submission.getEditUrl());
  Logger.log('==================================================');
}

/* ---------- 1. School registration (Phase 2) ---------- */
function createSchoolForm(ssId) {
  var form = FormApp.create('Kala Sangama 2026 — School Registration');
  form.setDescription(
    'Register your school for the Kala Sangama inter-school coloring & painting ' +
    'competition (Sri Krishna Janmashtami 2026). A coordinator from ISKCON South ' +
    'Bengaluru will follow up to confirm permissions and schedule the Level 1 round.'
  );
  form.setCollectEmail(true);

  form.addTextItem().setTitle('School name').setRequired(true);
  form.addParagraphTextItem().setTitle('School address / area').setRequired(true);
  form.addMultipleChoiceItem().setTitle('Board')
      .setChoiceValues(['State', 'CBSE', 'ICSE', 'IB / IGCSE', 'Other']);
  form.addTextItem().setTitle('Coordinator name (school point of contact)').setRequired(true);
  form.addTextItem().setTitle('Coordinator mobile number').setRequired(true);
  form.addTextItem().setTitle('Coordinator email');
  form.addTextItem().setTitle('Approx. students interested — Coloring (Std 2–5)');
  form.addTextItem().setTitle('Approx. students interested — Painting (Std 6–10)');
  form.addParagraphTextItem().setTitle('Preferred Level 1 dates (second half of July)');
  form.addParagraphTextItem().setTitle('Anything else we should know?');

  form.setDestination(FormApp.DestinationType.SPREADSHEET, ssId);
  form.setConfirmationMessage('Hare Krishna! Your school is registered. Our team will reach out shortly.');
  return form;
}

/* ---------- 2. Student registration (Phase 2) ---------- */
function createStudentForm(ssId) {
  var form = FormApp.create('Kala Sangama 2026 — Student Registration');
  form.setDescription(
    'Theme: "Sri Krishna at Vrindavan Village". Coloring is for Std 2–5; ' +
    'Painting is for Std 6–10. After fee payment each student receives a ' +
    'registration card that doubles as the Level 1 hall ticket.'
  );
  form.setCollectEmail(true);

  form.addTextItem().setTitle('School name').setRequired(true);
  form.addTextItem().setTitle('Student full name').setRequired(true);
  form.addListItem().setTitle('Standard / Class').setRequired(true)
      .setChoiceValues(['2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']);
  form.addMultipleChoiceItem().setTitle('Category').setRequired(true)
      .setChoiceValues(['Coloring (Std 2–5)', 'Painting (Std 6–10)']);
  form.addTextItem().setTitle('Section / Division');
  form.addTextItem().setTitle('Parent / Guardian name').setRequired(true);
  form.addTextItem().setTitle('Parent / Guardian mobile number').setRequired(true);
  form.addMultipleChoiceItem().setTitle('Participation fee')
      .setChoiceValues(['Paid', 'To be paid at school']);
  form.addTextItem().setTitle('Fee receipt / registration card number');
  form.addCheckboxItem().setTitle('Consent')
      .setChoiceValues(['I consent to my child participating and to ISKCON using competition photos for promotion.'])
      .setRequired(true);

  form.setDestination(FormApp.DestinationType.SPREADSHEET, ssId);
  form.setConfirmationMessage('Hare Krishna! Registration received. Collect your registration card / hall ticket from your school coordinator.');
  return form;
}

/* ---------- 3. Artwork submission (Phase 3 input) ---------- */
function createSubmissionForm(ssId) {
  var form = FormApp.create('Kala Sangama 2026 — Artwork Submission (Level 1 Shortlist)');
  form.setDescription(
    'For school coordinators: upload a clear photo/scan of each shortlisted ' +
    'artwork (top 3 per category). These feed the judging shortlist. ' +
    'NOTE: add the "Artwork photo" file-upload question manually in the editor.'
  );
  form.setCollectEmail(true);

  form.addTextItem().setTitle('School name').setRequired(true);
  form.addTextItem().setTitle('Student full name').setRequired(true);
  form.addTextItem().setTitle('Registration card / hall ticket number');
  form.addListItem().setTitle('Standard / Class').setRequired(true)
      .setChoiceValues(['2nd', '3rd', '4th', '5th', '6th', '7th', '8th', '9th', '10th']);
  form.addMultipleChoiceItem().setTitle('Category').setRequired(true)
      .setChoiceValues(['Coloring (Std 2–5)', 'Painting (Std 6–10)']);
  form.addTextItem().setTitle('Artwork title (optional)');
  // ⚠ Add a FILE UPLOAD question titled "Artwork photo" here in the editor —
  //   Apps Script cannot create file-upload items programmatically.

  form.setDestination(FormApp.DestinationType.SPREADSHEET, ssId);
  form.setConfirmationMessage('Artwork submitted. Thank you!');
  return form;
}
