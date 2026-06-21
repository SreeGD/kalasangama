/**
 * Kala Sangama 2026 — Registration Card / Level 1 Hall Ticket generator
 * --------------------------------------------------------------------
 * Reads the "Student Registration" responses, and for each PAID student mints a
 * unique registration ID + QR code, renders a saffron card to PDF, saves it to a
 * Drive folder, optionally emails it, and writes the ID + PDF link back to the Sheet.
 *
 * RECOMMENDED SETUP (gives you a one-click menu):
 *   1. Open the "Kala Sangama 2026 — Responses" spreadsheet.
 *   2. Extensions → Apps Script. Paste this file in. Save.
 *   3. Reload the spreadsheet → a "Kala Sangama" menu appears.
 *   4. Set STUDENT_TAB below to your Student Registration tab name.
 *   5. Menu → Kala Sangama → "Generate cards (paid only)".
 *
 * STANDALONE alternative: set SHEET_ID below and run generateCardsPaid() directly.
 *
 * The card design mirrors phase2-registration/card-preview.html — keep them in sync.
 */

// ---------------- Config ----------------
var SHEET_ID    = '';                     // only needed if NOT bound to the spreadsheet
var STUDENT_TAB = 'Student Registration'; // tab name of the student responses
var FOLDER_NAME = 'Kala Sangama 2026 — Registration Cards';
var ID_PREFIX   = 'KS2026-';
var EMAIL_CARDS = false;                   // true → email each card to the collected email
var PAID_ONLY   = true;                    // true → only students whose fee = "Paid"
var EVENT_TITLE = 'Kala Sangama 2026';
var ORG_LINE    = 'ISKCON South Bengaluru · ICC Mega School Outreach';
var THEME_LINE  = 'Theme: Sri Krishna at Vrindavan Village';

// QR verification (see Verify.gs). When VERIFY_URL is set, the QR scans to the
// live check-in page; otherwise it encodes the ID + details as plain text.
var VERIFY_URL    = '';  // paste the deployed Verify web-app /exec URL
var VERIFY_SECRET = '';  // optional anti-guessing secret — MUST match Verify.gs

// Columns we add to the sheet (created on first run if missing).
var COL_ID = 'Registration ID', COL_PDF = 'Card PDF', COL_AT = 'Card Generated At';

// ---------------- Menu ----------------
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Kala Sangama')
    .addItem('Generate cards (paid only)', 'generateCardsPaid')
    .addItem('Generate cards (ALL students)', 'generateCardsAll')
    .addItem('Regenerate ALL (overwrite)', 'regenerateAll')
    .addToUi();
}

function generateCardsPaid() { run_({ paidOnly: true,  overwrite: false }); }
function generateCardsAll()  { run_({ paidOnly: false, overwrite: false }); }
function regenerateAll()     { run_({ paidOnly: PAID_ONLY, overwrite: true }); }

// ---------------- Core ----------------
function run_(opts) {
  var ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActive();
  var sheet = ss.getSheetByName(STUDENT_TAB) || ss.getSheets()[0];
  var data = sheet.getDataRange().getValues();
  if (data.length < 2) return toast_('No student rows found in "' + sheet.getName() + '".');

  var headers = data[0].map(function (h) { return String(h).trim(); });
  var col = {
    school:   findCol_(headers, ['school']),
    student:  findCol_(headers, ['student full name', 'student name', 'student']),
    standard: findCol_(headers, ['standard', 'class']),
    category: findCol_(headers, ['category']),
    fee:      findCol_(headers, ['fee']),
    email:    findCol_(headers, ['email']),
  };
  if (col.student < 0) return toast_('Could not find a "Student full name" column.');

  var cId = ensureCol_(sheet, headers, COL_ID);
  var cPdf = ensureCol_(sheet, headers, COL_PDF);
  var cAt = ensureCol_(sheet, headers, COL_AT);
  data = sheet.getDataRange().getValues(); // re-read after possibly adding columns

  var folder = getFolder_(FOLDER_NAME);
  var seq = nextSeq_(data, cId);
  var made = 0, skipped = 0, failed = 0;

  for (var r = 1; r < data.length; r++) {
    var row = data[r];
    var name = String(row[col.student] || '').trim();
    if (!name) { continue; }

    var paid = col.fee < 0 ? true : /paid/i.test(String(row[col.fee]));
    if (opts.paidOnly && !paid) { skipped++; continue; }

    var existingId = String(row[cId] || '').trim();
    if (existingId && !opts.overwrite) { skipped++; continue; }

    var id = existingId || (ID_PREFIX + pad_(seq++, 4));
    try {
      var info = {
        id: id, name: name,
        school: get_(row, col.school), standard: get_(row, col.standard),
        category: get_(row, col.category),
      };
      var pdf = makeCardPdf_(info, folder);
      sheet.getRange(r + 1, cId + 1).setValue(id);
      sheet.getRange(r + 1, cPdf + 1).setValue(pdf.getUrl());
      sheet.getRange(r + 1, cAt + 1).setValue(new Date());
      if (EMAIL_CARDS && col.email >= 0) {
        var to = String(row[col.email] || '').trim();
        if (to) emailCard_(to, info, pdf);
      }
      made++;
    } catch (e) {
      failed++;
      Logger.log('Row %s (%s): %s', r + 1, name, e);
    }
  }
  toast_('Cards generated: ' + made + ' · skipped: ' + skipped +
         (failed ? (' · failed: ' + failed + ' (see logs)') : '') +
         '\nFolder: ' + folder.getUrl());
}

// ---------------- Card → PDF ----------------
function makeCardPdf_(info, folder) {
  var html = cardHtml_(info, qrDataUri_(info));
  var pdf = Utilities.newBlob(html, 'text/html', info.id + '.html')
                     .getAs('application/pdf')
                     .setName(info.id + ' - ' + info.name + '.pdf');
  // overwrite any prior file with the same name
  var existing = folder.getFilesByName(pdf.getName());
  while (existing.hasNext()) { existing.next().setTrashed(true); }
  return folder.createFile(pdf);
}

function cardHtml_(info, qrUri) {
  var esc = function (s) { return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); };
  var qr = qrUri
    ? '<img class="qr" src="' + qrUri + '" alt="QR"/>'
    : '<div class="qr qr-fallback">' + esc(info.id) + '</div>';
  return '' +
'<!doctype html><html><head><meta charset="utf-8"><style>' +
'  * { box-sizing: border-box; font-family: Helvetica, Arial, sans-serif; }' +
'  body { margin: 0; padding: 24px; }' +
'  .card { width: 540px; border: 2px solid #e07b1a; border-radius: 16px; overflow: hidden; }' +
'  .head { background: #e07b1a; color: #fff; padding: 16px 22px; }' +
'  .head .t { font-size: 22px; font-weight: bold; letter-spacing: .5px; }' +
'  .head .o { font-size: 11px; opacity: .95; margin-top: 2px; }' +
'  .head .badge { float: right; font-size: 10px; background: rgba(255,255,255,.2);' +
'    border: 1px solid rgba(255,255,255,.6); border-radius: 999px; padding: 4px 10px; }' +
'  .body { padding: 18px 22px; }' +
'  .theme { color: #a8500a; font-size: 12px; font-style: italic; margin: 0 0 12px; }' +
'  table { width: 100%; border-collapse: collapse; }' +
'  td { vertical-align: top; padding: 4px 0; }' +
'  .lbl { color: #7a5c44; font-size: 10px; text-transform: uppercase; letter-spacing: .06em; }' +
'  .val { color: #3a2414; font-size: 16px; font-weight: bold; }' +
'  .idval { color: #c4630b; font-size: 18px; font-weight: bold; letter-spacing: 1px; }' +
'  .qrcell { width: 130px; text-align: right; }' +
'  .qr { width: 120px; height: 120px; }' +
'  .qr-fallback { width: 120px; height: 120px; border: 1px dashed #c4630b; color: #c4630b;' +
'    font-size: 11px; display: table-cell; vertical-align: middle; text-align: center; }' +
'  .foot { border-top: 2px dashed #e0b48a; margin-top: 8px; padding: 12px 22px;' +
'    background: #fbf3e3; color: #6b3318; font-size: 11px; }' +
'  .foot b { color: #a8500a; }' +
'</style></head><body><div class="card">' +
'  <div class="head"><span class="badge">LEVEL 1 HALL TICKET</span>' +
'    <div class="t">' + esc(EVENT_TITLE) + '</div><div class="o">' + esc(ORG_LINE) + '</div></div>' +
'  <div class="body"><p class="theme">' + esc(THEME_LINE) + '</p>' +
'  <table><tr>' +
'    <td><div class="lbl">Registration ID</div><div class="idval">' + esc(info.id) + '</div>' +
'      <div style="height:10px"></div>' +
'      <div class="lbl">Student</div><div class="val">' + esc(info.name) + '</div>' +
'      <div style="height:8px"></div>' +
'      <div class="lbl">School</div><div class="val">' + esc(info.school || '—') + '</div>' +
'      <div style="height:8px"></div>' +
'      <table style="width:100%"><tr>' +
'        <td><div class="lbl">Standard</div><div class="val">' + esc(info.standard || '—') + '</div></td>' +
'        <td><div class="lbl">Category</div><div class="val">' + esc(info.category || '—') + '</div></td>' +
'      </tr></table>' +
'    </td>' +
'    <td class="qrcell">' + qr + '</td>' +
'  </tr></table></div>' +
'  <div class="foot"><b>Bring this card to the Level 1 competition.</b> It is your hall ticket — ' +
'    keep it safe. Valid only for the named student. Hare Krishna.</div>' +
'</div></body></html>';
}

// Builds what the QR encodes: a live verification URL if VERIFY_URL is set,
// else the ID + key details as plain scannable text.
function qrPayload_(info) {
  if (VERIFY_URL) {
    var u = VERIFY_URL + '?id=' + encodeURIComponent(info.id);
    if (VERIFY_SECRET) u += '&k=' + tokenFor_(info.id, VERIFY_SECRET);
    return u;
  }
  return [info.id, info.name, info.category, info.standard].join(' | ');
}

function qrDataUri_(info) {
  try {
    var url = 'https://api.qrserver.com/v1/create-qr-code/?size=240x240&margin=0&data=' +
              encodeURIComponent(qrPayload_(info));
    var blob = UrlFetchApp.fetch(url, { muteHttpExceptions: true }).getBlob();
    return 'data:image/png;base64,' + Utilities.base64Encode(blob.getBytes());
  } catch (e) {
    Logger.log('QR fetch failed for %s: %s', info.id, e);
    return ''; // card falls back to printing the ID in a box
  }
}

// Short anti-guessing token (mirror of the same function in Verify.gs).
function tokenFor_(id, secret) {
  if (!secret) return '';
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, id + '|' + secret);
  return raw.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); })
            .join('').substring(0, 8);
}

function emailCard_(to, info, pdf) {
  MailApp.sendEmail({
    to: to,
    subject: EVENT_TITLE + ' — Registration Card (' + info.id + ')',
    htmlBody: 'Hare Krishna,<br><br>Attached is the Kala Sangama registration card / ' +
      'Level 1 hall ticket for <b>' + info.name + '</b> (' + info.id + ').<br>' +
      'Please print it and bring it to the Level 1 competition.<br><br>' +
      'Theme: <i>Sri Krishna at Vrindavan Village</i>.<br><br>ISKCON South Bengaluru',
    attachments: [pdf.getAs('application/pdf')],
    name: EVENT_TITLE,
  });
}

// ---------------- Helpers ----------------
function findCol_(headers, needles) {
  for (var i = 0; i < headers.length; i++) {
    var h = headers[i].toLowerCase();
    for (var j = 0; j < needles.length; j++) if (h.indexOf(needles[j]) !== -1) return i;
  }
  return -1;
}
function ensureCol_(sheet, headers, name) {
  var idx = headers.indexOf(name);
  if (idx >= 0) return idx;
  idx = headers.length;
  sheet.getRange(1, idx + 1).setValue(name);
  headers.push(name);
  return idx;
}
function get_(row, idx) { return idx >= 0 ? String(row[idx] || '').trim() : ''; }
function nextSeq_(data, cId) {
  var max = 0;
  for (var r = 1; r < data.length; r++) {
    var m = String(data[r][cId] || '').match(/(\d+)\s*$/);
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max + 1;
}
function pad_(n, w) { var s = String(n); while (s.length < w) s = '0' + s; return s; }
function getFolder_(name) {
  var it = DriveApp.getFoldersByName(name);
  return it.hasNext() ? it.next() : DriveApp.createFolder(name);
}
function toast_(msg) {
  try { SpreadsheetApp.getActive().toast(msg, 'Kala Sangama', 8); } catch (e) {}
  Logger.log(msg);
}
