/* ============================================================
   Kala Sangama — interactions: language toggle, nav, links, share
   ============================================================ */
(function () {
  "use strict";

  var I18N = window.KALA_I18N || {};
  var CFG = window.KALA_CONFIG || {};
  var STORAGE_KEY = "kala-lang";
  var SUPPORTED = ["en", "kn"];

  /* ---------- Translation ---------- */
  function applyLang(lang) {
    if (SUPPORTED.indexOf(lang) === -1) lang = "en";
    var dict = I18N[lang] || {};
    document.documentElement.setAttribute("lang", lang);

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (dict[key] != null) el.innerHTML = dict[key];
    });

    document.querySelectorAll("[data-lang-label]").forEach(function (el) {
      el.classList.toggle("active", el.getAttribute("data-lang-label") === lang);
    });

    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
  }

  function initLang() {
    var saved;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    var browser = (navigator.language || "").toLowerCase().indexOf("kn") === 0 ? "kn" : "en";
    applyLang(saved || browser);

    var toggle = document.getElementById("langToggle");
    if (toggle) {
      toggle.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("lang");
        applyLang(current === "en" ? "kn" : "en");
      });
    }
  }

  /* ---------- Mobile nav ---------- */
  function initNav() {
    var burger = document.getElementById("navBurger");
    var nav = document.querySelector(".main-nav");
    if (!burger || !nav) return;

    burger.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      burger.setAttribute("aria-expanded", String(open));
    });
    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        nav.classList.remove("open");
        burger.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ---------- Registration form links ---------- */
  function initRegLinks() {
    var forms = CFG.forms || {};
    document.querySelectorAll("[data-reg-link]").forEach(function (el) {
      var which = el.getAttribute("data-reg-link");
      var url = forms[which];
      if (url) {
        el.setAttribute("href", url);
        el.setAttribute("target", "_blank");
        el.setAttribute("rel", "noopener");
      } else {
        // No form yet — disable and route users to contact section.
        el.setAttribute("href", "#contact");
        el.classList.add("is-pending");
        el.setAttribute("title", "Form opens soon — contact the committee for early access.");
      }
    });
  }

  /* ---------- Contact chips ---------- */
  function initContact() {
    var c = CFG.contact || {};
    var map = {
      whatsapp: c.whatsapp ? "https://wa.me/" + c.whatsapp : null,
      email: c.email ? "mailto:" + c.email : null,
      volunteer: c.volunteer || null,
    };
    document.querySelectorAll("[data-contact]").forEach(function (el) {
      var url = map[el.getAttribute("data-contact")];
      if (url) {
        el.setAttribute("href", url);
        if (url.indexOf("http") === 0) { el.setAttribute("target", "_blank"); el.setAttribute("rel", "noopener"); }
      } else {
        el.style.display = "none";
      }
    });
  }

  /* ---------- WhatsApp share ---------- */
  function initShare() {
    var btn = document.getElementById("shareWhatsApp");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var text = (CFG.shareText || document.title) + " " + window.location.href;
      var url = "https://wa.me/?text=" + encodeURIComponent(text);
      if (navigator.share) {
        navigator.share({ title: "Kala Sangama 2026", text: CFG.shareText, url: window.location.href })
          .catch(function () { window.open(url, "_blank", "noopener"); });
      } else {
        window.open(url, "_blank", "noopener");
      }
    });
  }

  /* ---------- Promotional video ---------- */
  function initVideo() {
    var id = (CFG.video || {}).driveId;
    var frame = document.getElementById("videoFrame");
    var iframe = document.getElementById("promoVideo");
    var fallback = document.getElementById("videoFallback");
    if (id && frame && iframe) {
      iframe.setAttribute("src", "https://drive.google.com/file/d/" + id + "/preview");
      frame.hidden = false;
      if (fallback) fallback.style.display = "none";
    }
  }

  /* ---------- Placeholder config warning ---------- */
  function warnPlaceholders() {
    var pending = [];
    var f = CFG.forms || {}, c = CFG.contact || {};
    function check(label, val) {
      if (!val || /REPLACE|\bexample\b|^9?10000000000$/.test(String(val))) {
        pending.push(label + ' = "' + (val || "") + '"');
      }
    }
    check("forms.school", f.school);
    check("forms.student", f.student);
    check("contact.whatsapp", c.whatsapp);
    check("contact.email", c.email);
    check("contact.volunteer", c.volunteer);

    if (pending.length) {
      console.warn(
        "%cKala Sangama — placeholder config still in use (" + pending.length + ")",
        "color:#c4630b;font-weight:bold;font-size:13px"
      );
      console.warn("Edit js/config.js and replace these before going live:\n  • " +
        pending.join("\n  • "));
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    initLang();
    initNav();
    initRegLinks();
    initContact();
    initShare();
    initVideo();
    warnPlaceholders();
  });
})();
