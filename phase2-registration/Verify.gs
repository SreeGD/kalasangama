/**
 * Kala Sangama 2026 — QR check-in / verification web app
 * ------------------------------------------------------
 * Scanning a card's QR opens this page, which validates the registration ID
 * against the Student Registration sheet and lets a gate volunteer check the
 * student in (records a timestamp). Works on any phone — no Google login needed.
 *
 * DEPLOY (recommended: a SEPARATE Apps Script project, so its globals don't clash
 * with RegistrationCard.gs):
 *   1. https://script.google.com → New project. Paste this file in.
 *   2. Set SHEET_ID (the responses spreadsheet's ID), STUDENT_TAB, and optionally
 *      VERIFY_SECRET below.
 *   3. Deploy → New deployment → type "Web app".
 *        Execute as: Me.   Who has access: Anyone.
 *      Copy the /exec URL.
 *   4. Paste that URL into RegistrationCard.gs → VERIFY_URL, and copy the SAME
 *      VERIFY_SECRET into RegistrationCard.gs. Then regenerate cards so their QR
 *      codes point here.
 *   (You CAN instead add this as a file in the same bound project as
 *    RegistrationCard.gs, but then delete the duplicated shared declarations —
 *    SHEET_ID, STUDENT_TAB, VERIFY_SECRET, EVENT_TITLE, tokenFor_, findCol_ — from
 *    one of the two files to avoid "already declared" errors.)
 *
 * SECURITY: With a VERIFY_SECRET set, each QR carries a short token (&k=...) so
 * people can't guess IDs to view other students. Keep the secret private. Without
 * a secret, the page is open to anyone with a valid ID.
 */

// ---------------- Config (keep STUDENT_TAB / VERIFY_SECRET in sync where relevant) ----------------
var SHEET_ID      = '';                       // only if this is a SEPARATE project from the sheet
var STUDENT_TAB   = 'Student Registration';   // student responses tab
var VERIFY_SECRET = '';                       // optional; MUST match RegistrationCard.gs
var EVENT_TITLE   = 'Kala Sangama 2026';
var COL_CHECKIN   = 'Checked In At';          // created automatically on first check-in

// ---------------- Web entry point ----------------
function doGet(e) {
  var p = (e && e.parameter) || {};
  var id = String(p.id || '').trim();
  var k = String(p.k || '').trim();
  var action = String(p.action || '').trim();

  if (!id) return page_('prompt', { title: EVENT_TITLE, msg: 'Scan a registration QR code.' });

  // Token check (anti-guessing) when a secret is configured.
  if (VERIFY_SECRET && k !== tokenFor_(id, VERIFY_SECRET)) {
    return page_('invalid', { id: id, title: 'Invalid code',
      msg: 'This link is missing or has an incorrect security code.' });
  }

  var rec = lookup_(id);
  if (!rec) {
    return page_('invalid', { id: id, title: 'Not found',
      msg: 'No registration matches ' + id + '.' });
  }

  if (action === 'checkin' && !rec.checkedInAt) {
    rec.checkedInAt = checkIn_(rec.rowIndex);
    rec.justCheckedIn = true;
  }
  return page_('valid', rec);
}

// ---------------- Sheet lookup / check-in ----------------
function sheet_() {
  var ss = SHEET_ID ? SpreadsheetApp.openById(SHEET_ID) : SpreadsheetApp.getActive();
  return ss.getSheetByName(STUDENT_TAB) || ss.getSheets()[0];
}

function lookup_(id) {
  var sheet = sheet_();
  var data = sheet.getDataRange().getValues();
  var headers = data[0].map(function (h) { return String(h).trim(); });
  var c = {
    id: findCol_(headers, ['registration id']),
    student: findCol_(headers, ['student full name', 'student name', 'student']),
    school: findCol_(headers, ['school']),
    standard: findCol_(headers, ['standard', 'class']),
    category: findCol_(headers, ['category']),
    fee: findCol_(headers, ['fee']),
    checkin: headers.indexOf(COL_CHECKIN),
  };
  if (c.id < 0) return null; // no IDs minted yet
  for (var r = 1; r < data.length; r++) {
    if (String(data[r][c.id] || '').trim().toLowerCase() === id.toLowerCase()) {
      return {
        rowIndex: r + 1,
        id: String(data[r][c.id]).trim(),
        name: val_(data[r], c.student),
        school: val_(data[r], c.school),
        standard: val_(data[r], c.standard),
        category: val_(data[r], c.category),
        fee: val_(data[r], c.fee),
        checkedInAt: c.checkin >= 0 ? data[r][c.checkin] : '',
        justCheckedIn: false,
      };
    }
  }
  return null;
}

function checkIn_(rowIndex) {
  var lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    var sheet = sheet_();
    var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0]
                       .map(function (h) { return String(h).trim(); });
    var col = headers.indexOf(COL_CHECKIN);
    if (col < 0) { col = headers.length; sheet.getRange(1, col + 1).setValue(COL_CHECKIN); }
    var cell = sheet.getRange(rowIndex, col + 1);
    if (!cell.getValue()) {
      var now = new Date();
      cell.setValue(now);
      return now;
    }
    return cell.getValue();
  } finally {
    lock.releaseLock();
  }
}

// ---------------- HTML page ----------------
function page_(kind, d) {
  var esc = function (s) { return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); };
  var fmt = function (dt) {
    if (!dt) return '';
    try { return Utilities.formatDate(new Date(dt),
      Session.getScriptTimeZone() || 'Asia/Kolkata', 'd MMM yyyy, h:mm a'); }
    catch (e) { return String(dt); }
  };

  var accent, icon, head, sub, body = '';
  if (kind === 'valid') {
    var paidOk = !d.fee || /paid/i.test(d.fee);
    accent = '#2e7d32'; icon = '✓'; head = 'Valid registration'; sub = esc(d.id);
    body =
      row_('Student', esc(d.name)) +
      row_('School', esc(d.school || '—')) +
      row_('Standard', esc(d.standard || '—')) +
      row_('Category', esc(d.category || '—')) +
      row_('Fee', (paidOk ? '<b style="color:#2e7d32">' + esc(d.fee || 'Paid') + '</b>'
                          : '<b style="color:#c62828">' + esc(d.fee || 'Not paid') + '</b>'));
    if (d.checkedInAt) {
      body += '<div class="status in">' + (d.justCheckedIn ? 'Checked in just now' :
        'Already checked in') + '<br><small>' + esc(fmt(d.checkedInAt)) + '</small></div>';
    } else {
      var url = ScriptApp.getService().getUrl() + '?id=' + encodeURIComponent(d.id) +
        (VERIFY_SECRET ? '&k=' + tokenFor_(d.id, VERIFY_SECRET) : '') + '&action=checkin';
      body += '<a class="btn" href="' + url + '">Check in ✓</a>';
    }
  } else if (kind === 'invalid') {
    accent = '#c62828'; icon = '✕'; head = esc(d.title || 'Invalid'); sub = esc(d.id || '');
    body = '<p class="msg">' + esc(d.msg || '') + '</p>';
  } else { // prompt
    accent = '#e07b1a'; icon = '☼'; head = esc(EVENT_TITLE); sub = '';
    body = '<p class="msg">' + esc(d.msg || '') + '</p>';
  }

  var html =
'<!doctype html><html><head><meta charset="utf-8">' +
'<meta name="viewport" content="width=device-width,initial-scale=1">' +
'<title>' + esc(EVENT_TITLE) + ' — Check-in</title><style>' +
' body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;' +
'   background:#fbf8e9;color:#3a2414;display:flex;justify-content:center;}' +
' .wrap{max-width:420px;width:100%;padding:18px;}' +
' .card{background:#fff;border-radius:18px;box-shadow:0 10px 30px rgba(74,29,10,.12);overflow:hidden;}' +
' .top{background:' + accent + ';color:#fff;text-align:center;padding:26px 18px;}' +
' .ic{font-size:46px;line-height:1;}' +
' .top h1{margin:8px 0 2px;font-size:20px;} .top .sub{opacity:.95;font-size:13px;letter-spacing:1px;}' +
' .rows{padding:8px 20px 4px;} .r{display:flex;justify-content:space-between;gap:14px;' +
'   padding:11px 0;border-bottom:1px solid #f0e6cf;} .r:last-child{border-bottom:0;}' +
' .r .l{color:#7a5c44;font-size:12px;text-transform:uppercase;letter-spacing:.05em;}' +
' .r .v{font-size:16px;font-weight:600;text-align:right;}' +
' .msg{padding:20px;text-align:center;color:#6b3318;}' +
' .btn{display:block;margin:14px 20px 22px;background:#2e7d32;color:#fff;text-align:center;' +
'   padding:15px;border-radius:12px;font-size:17px;font-weight:700;text-decoration:none;}' +
' .status{margin:14px 20px 22px;background:#eaf5ea;color:#2e7d32;border:1px solid #b7dcb7;' +
'   border-radius:12px;padding:14px;text-align:center;font-weight:700;}' +
' .ev{text-align:center;color:#a8500a;font-size:12px;margin:14px 0 0;}' +
'</style></head><body><div class="wrap"><div class="card">' +
'  <div class="top"><div class="ic">' + icon + '</div><h1>' + head + '</h1>' +
   (sub ? '<div class="sub">' + sub + '</div>' : '') + '</div>' +
   (body.indexOf('class="r"') >= 0 || kind === 'valid'
      ? '<div class="rows">' + body + '</div>' : body) +
'</div><p class="ev">' + esc(EVENT_TITLE) + ' · Level 1 check-in</p></div></body></html>';

  return HtmlService.createHtmlOutput(html)
    .setTitle(EVENT_TITLE + ' — Check-in')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function row_(label, valueHtml) {
  return '<div class="r"><span class="l">' + label + '</span>' +
         '<span class="v">' + valueHtml + '</span></div>';
}

// ---------------- Shared helpers (mirror RegistrationCard.gs) ----------------
function tokenFor_(id, secret) {
  if (!secret) return '';
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, id + '|' + secret);
  return raw.map(function (b) { return ('0' + (b & 0xff).toString(16)).slice(-2); })
            .join('').substring(0, 8);
}
function findCol_(headers, needles) {
  for (var i = 0; i < headers.length; i++) {
    var h = headers[i].toLowerCase();
    for (var j = 0; j < needles.length; j++) if (h.indexOf(needles[j]) !== -1) return i;
  }
  return -1;
}
function val_(row, idx) { return idx >= 0 ? String(row[idx] || '').trim() : ''; }
