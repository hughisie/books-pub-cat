/* books.pub.cat — email capture and the consent-gated advertising pixels.
 *
 * Two rules this file exists to keep:
 *   1. The privacy page promises that visitors in the EU, the EEA, the UK and
 *      Switzerland are asked before the advertising pixel loads, and that
 *      everyone else gets it on the first visit with a switch-off link on the
 *      privacy page. Owen's decision, 7 Sep 2026. The country comes from a
 *      Pub.Cat endpoint; if it cannot be reached we ask, never assume.
 *   2. The forms must actually deliver. They post to the Pub.Cat endpoint and
 *      report success or failure in the page rather than silently doing nothing.
 */
(function () {
  "use strict";

  var ENDPOINT = "https://mcp.pub.cat/books/subscribe";

  /* Set this once the Pub.Cat Books Meta account exists. While it is empty no
     pixel code is loaded and no consent banner is shown, because there would be
     nothing to consent to. */
  var META_PIXEL_ID = "";

  /* Whop's own pixel. Whop runs the Meta ads and records every checkout and
     purchase server-side; the site only has to report page views and the
     free-sample lead. Same consent gate as the Meta pixel: nothing loads until
     the visitor clicks Allow. */
  var WHOP_BIZ_ID = "biz_l1sR4RzKzCfYlf";

  var STORE_KEY = "pubcat-books-consent";

  /* ------------------------------------------------ measurement (6 Oct 2026)
     Draft on branch tracking-2026-10-06, not live. What it adds:
       1. The ad a reader came from. Whop's ad tool tags its links with
          wacid (campaign), wasid (ad group) and waid (ad); with utm_* those are
          campaign labels, not personal identifiers. They go with the sample
          sign-up to our server, so each sign-up, and any later Whop sale by the
          same email, can be tied to the ad that brought it.
       2. The same labels are carried onto Whop checkout links, so a reader who
          goes from our page to Whop still carries the ad's tags.
       3. Buy-intent clicks to Amazon are reported to Whop's pixel as
          "add_to_cart" plus a per-ASIN custom event, so Whop and Meta can see
          (and later optimise for) people who head off to buy. Amazon itself
          has no pixel, so this is the last thing we can see.
       4. Visitors who arrived from a paid ad get a separate Amazon Attribution
          tag when ATTRIB_PAID has one for that ASIN, so Meta-driven Amazon
          sales stop being lumped in with everyone else's "Site" clicks.
       5. A sign-up made before the visitor answers the consent banner is held
          and sent if they then click Allow, instead of being lost.
     Consent rule unchanged: nothing goes to Whop or Meta, and nothing is
     stored in the browser, unless the advertising pixels are allowed. */
  var AD_PARAMS = ["wacid", "wasid", "waid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
  var CLICK_ID_PARAMS = ["fbclid"];           /* person-level: only sent once the pixels are allowed */
  var AD_KEY = "pubcat-books-ad";             /* sessionStorage, written only after consent */

  /* ASIN -> Amazon Attribution "maas" value for readers who came from a paid ad.
     Empty until Owen creates the ad groups in Amazon Attribution (free), e.g.
     "Meta via site: Dayrabi Kindle". Until then the "Site ..." tags stay as they are. */
  var ATTRIB_PAID = {};

  /* Whop's pixel accepts the reader's email in plain text to match the event to
     a Meta user (better match, better optimisation). Off until Owen decides and
     the privacy page says so. */
  var SEND_EMAIL_TO_WHOP = false;

  var pixelsOn = false;        /* true once loadPixels() has run */
  var consentDenied = false;   /* true once the visitor said no */
  var heldEvents = [];         /* events waiting on the consent banner */

  function paramsFrom(search, names) {
    var out = {};
    try {
      var q = new URLSearchParams(search || "");
      names.forEach(function (n) { var v = q.get(n); if (v) out[n] = v.slice(0, 120); });
    } catch (e) {}
    return out;
  }
  var LANDING_AD = paramsFrom(window.location.search, AD_PARAMS);
  var LANDING_CLICK = paramsFrom(window.location.search, CLICK_ID_PARAMS);
  function hasKeys(o) { for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) return true; return false; }

  function storedAd() {
    try { return JSON.parse(window.sessionStorage.getItem(AD_KEY) || "null") || {}; }
    catch (e) { return {}; }
  }
  /* The ad labels for this visit: from this page's address, else from earlier in the visit. */
  function currentAd() {
    if (hasKeys(LANDING_AD)) return LANDING_AD;
    var s = storedAd();
    return s.ad || {};
  }
  function currentClick() {
    if (!pixelsOn) return {};
    if (hasKeys(LANDING_CLICK)) return LANDING_CLICK;
    var s = storedAd();
    return s.click || {};
  }
  function rememberAd() {
    if (!hasKeys(LANDING_AD) && !hasKeys(LANDING_CLICK)) return;
    try { window.sessionStorage.setItem(AD_KEY, JSON.stringify({ ad: LANDING_AD, click: LANDING_CLICK, page: window.location.pathname })); }
    catch (e) {}
  }
  function fromPaidAd() {
    var a = currentAd();
    return !!(a.waid || a.wasid || a.wacid || /^(fb|ig|facebook|instagram|meta|whop)/i.test(a.utm_source || ""));
  }

  function eventId(prefix) {
    return prefix + "-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  /* One door to Whop's pixel: sends now, holds while the banner is unanswered,
     drops if the visitor said no. */
  function track(name, props) {
    if (window.whop && pixelsOn) {
      try { props ? window.whop.track(name, props) : window.whop.track(name); } catch (e) {}
      return;
    }
    if (!consentDenied && heldEvents.length < 20) heldEvents.push([name, props]);
  }
  function flushHeld() {
    var q = heldEvents; heldEvents = [];
    q.forEach(function (ev) { track(ev[0], ev[1]); });
  }

  /* Every visible string, per language (2 Oct 2026). The English is the copy that was
     already live; Spanish and Catalan are DeepSeek's translations, written in here by
     tools/i18n/build.py js. Do not edit between the markers by hand. */
  /* I18N:BEGIN */
  var I18N = {
    "en": {
      "js_sending": "Sending…",
      "js_ready": "Your sample is ready.",
      "js_open_sample": "Open the 30-page sample (PDF)",
      "js_no_link": "Thank you. The download link did not come back; email owen@pub.cat and we will send it by hand.",
      "js_listed": "Thank you. You are on the list.",
      "js_failed": "That did not go through. Please email us instead and we will add you by hand.",
      "js_optout_done": "All done. The advertising pixel will not load again in this browser unless you clear your browser storage.",
      "js_consent_label": "Advertising cookie",
      "js_consent_text": "We would like to set one advertising cookie, so that we are not paying to show an advert to someone who has already bought the book. Nothing else on this site uses cookies.",
      "js_consent_link": "What we collect",
      "js_no_thanks": "No thanks",
      "js_allow": "Allow",
      "js_lb_label": "Enlarged image",
      "js_lb_close": "Close",
      "js_lb_hint": "Scroll or pinch to zoom in, drag to move around, Esc to close"
    },
    "es": {
      "js_sending": "Enviando…",
      "js_ready": "Tu muestra está lista.",
      "js_open_sample": "Abrir la muestra de 30 páginas (PDF)",
      "js_no_link": "Gracias. El enlace de descarga no ha llegado; escribe a owen@pub.cat y te lo enviaremos a mano.",
      "js_listed": "Gracias. Ya estás en la lista.",
      "js_failed": "No se ha podido completar. Escríbenos por correo y te añadiremos a mano.",
      "js_optout_done": "Ya está. El píxel publicitario no volverá a cargarse en este navegador a menos que borres el almacenamiento del navegador.",
      "js_consent_label": "Cookie publicitaria",
      "js_consent_text": "Nos gustaría instalar una cookie publicitaria, para no pagar por mostrar un anuncio a alguien que ya ha comprado el libro. Nada más en este sitio utiliza cookies.",
      "js_consent_link": "Qué recopilamos",
      "js_no_thanks": "No, gracias",
      "js_allow": "Permitir",
      "js_lb_label": "Imagen ampliada",
      "js_lb_close": "Cerrar",
      "js_lb_hint": "Desplázate o pellizca para ampliar, arrastra para moverte, Esc para cerrar"
    },
    "ca": {
      "js_sending": "S'està enviant…",
      "js_ready": "La teva mostra ja està a punt.",
      "js_open_sample": "Obre la mostra de 30 pàgines (PDF)",
      "js_no_link": "Gràcies. L'enllaç de descàrrega no ha arribat; escriu a owen@pub.cat i te'l farem arribar manualment.",
      "js_listed": "Gràcies. Ja ets a la llista.",
      "js_failed": "No s'ha pogut completar. Escriu-nos directament i t'afegirem manualment.",
      "js_optout_done": "Fet. El píxel publicitari no es tornarà a carregar en aquest navegador tret que esborris l'emmagatzematge del navegador.",
      "js_consent_label": "Galeta publicitària",
      "js_consent_text": "Voldríem instal·lar una galeta publicitària, per no pagar per mostrar un anunci a algú que ja ha comprat el llibre. Cap altra part d'aquest lloc utilitza galetes.",
      "js_consent_link": "Què recollim",
      "js_no_thanks": "No, gràcies",
      "js_allow": "Permet",
      "js_lb_label": "Imatge ampliada",
      "js_lb_close": "Tanca",
      "js_lb_hint": "Fes scroll o pessiga per ampliar, arrossega per moure't, Esc per tancar"
    }
  };
  /* I18N:END */
  var LANG = ((document.documentElement.getAttribute("lang") || "en").slice(0, 2)).toLowerCase();
  if (!I18N[LANG]) LANG = "en";
  var PREFIX = LANG === "en" ? "" : "/" + LANG;
  function T(k) { return (I18N[LANG] && I18N[LANG][k]) || (I18N.en && I18N.en[k]) || ""; }

  function readConsent() {
    try { return window.localStorage.getItem(STORE_KEY); }
    catch (e) { return null; }
  }
  function writeConsent(v) {
    try { window.localStorage.setItem(STORE_KEY, v); } catch (e) {}
  }

  /* ---------------------------------------------------------- email forms */

  function wireForm(form) {
    if (!form) return;
    var note = document.createElement("p");
    note.className = "small";
    note.setAttribute("role", "status");
    note.setAttribute("aria-live", "polite");
    note.style.marginTop = "0.6rem";
    note.hidden = true;
    form.parentNode.insertBefore(note, form.nextSibling);

    /* bots fill every field they can see; humans never see this one */
    var pot = document.createElement("input");
    pot.type = "text";
    pot.name = "website";
    pot.tabIndex = -1;
    pot.autocomplete = "off";
    pot.setAttribute("aria-hidden", "true");
    pot.style.cssText = "position:absolute;left:-9999px;width:1px;height:1px;";
    form.appendChild(pot);

    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var input = form.querySelector('input[type="email"]');
      var button = form.querySelector('button[type="submit"]');
      if (!input || !input.value) return;

      var original = button ? button.textContent : "";
      var signupId = eventId("su");
      if (button) { button.disabled = true; button.textContent = T("js_sending"); }
      note.hidden = false;
      note.textContent = "";

      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: input.value.trim(),
          website: pot.value,
          source: form.id || "site",
          /* which ad, page and click this sign-up came from (draft, 6 Oct 2026);
             the server ignores fields it does not know until its own patch is in */
          event_id: signupId,
          page: window.location.pathname,
          ad: currentAd(),
          click: currentClick()
        })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok) {
            form.hidden = true;
            var isSample = /^sample/.test(form.id || "");
            if (isSample) {
              /* same event_id on both, so a later server-side copy can be de-duplicated */
              var who = SEND_EMAIL_TO_WHOP ? { email: input.value.trim() } : {};
              who.event_id = signupId;
              track("complete_registration", who);
              track("lead", { event_id: signupId });
            }
            if (isSample && res.j && res.j.sample_url) {
              /* the server hands back the hosted PDF; show it right here rather
                 than promising an email that nothing sends yet */
              note.textContent = T("js_ready");
              var dl = document.createElement("a");
              dl.className = "btn btn-primary";
              dl.href = res.j.sample_url;
              dl.target = "_blank";
              dl.rel = "noopener";
              /* a page with a different sample names it on the form:
                 <form data-download-label="..."> (added 28 Sep 2026 for al-Dayrabī) */
              dl.textContent = form.getAttribute("data-download-label") || T("js_open_sample");
              dl.style.cssText = "display:inline-block;margin-top:.7rem";
              note.appendChild(document.createElement("br"));
              note.appendChild(dl);
              dl.addEventListener("click", function () { track("sample_opened", { event_id: signupId + "-open" }); });
              dl.focus();
            } else if (isSample) {
              note.textContent = T("js_no_link");
            } else {
              note.textContent = T("js_listed");
            }
          } else {
            throw new Error((res.j && res.j.error) || "failed");
          }
        })
        .catch(function () {
          note.textContent = T("js_failed");
          if (button) { button.disabled = false; button.textContent = original; }
        });
    });
  }

  /* ------------------------------------------------------ the Meta pixel */

  function loadWhopPixel() {
    if (!WHOP_BIZ_ID || window.whop) return;
    /* eslint-disable */
    !function(w,d,s,u,n,a,b){if(w[n])return;a=w[n]={q:[],t:+new Date,s:[],o:u,track:function(){a.q.push([+new Date].concat([].slice.call(arguments)))},setScope:function(){a.s=[].slice.call(arguments).filter(function(x){return typeof x==="string"});a.q.push([+new Date,"setScope"].concat(a.s))},scope:function(){var c=[].slice.call(arguments);return{track:function(){a.q.push([+new Date].concat([].slice.call(arguments)).concat([{__scope:c}]))}}}};b=d.createElement(s);b.async=1;b.src=u+"/s.js";d.getElementsByTagName(s)[0].parentNode.insertBefore(b,d.getElementsByTagName(s)[0])}(window,document,"script","https://t.whop.tw","whop");
    /* eslint-enable */
    window.whop.setScope(WHOP_BIZ_ID);
    window.whop.track("page");
  }

  function loadPixels() {
    pixelsOn = true;
    loadWhopPixel();
    loadMetaPixel();
    rememberAd();
    flushHeld();
  }

  function loadMetaPixel() {
    if (!META_PIXEL_ID || window.fbq) return;
    /* eslint-disable */
    !function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?
    n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;
    n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;
    t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}
    (window,document,'script','https://connect.facebook.net/en_US/fbevents.js');
    /* eslint-enable */
    window.fbq('init', META_PIXEL_ID);
    window.fbq('track', 'PageView');
  }

  /* Consent geography (Owen, 7 Sep 2026). A stored choice always wins. With no
     stored choice, a tiny Pub.Cat endpoint reports which country the visitor is
     in from Cloudflare's header: the EU, the EEA, the UK and Switzerland get
     the banner and nothing loads until they click Allow; everywhere else the
     pixels load at once with no banner, and the privacy page carries the
     switch-off link. If the lookup fails or is slow, we ask; asking is the
     safe default. */
  var GEO_ENDPOINT = "https://mcp.pub.cat/books/geo";

  function banner() {
    if (!META_PIXEL_ID && !WHOP_BIZ_ID) return;   /* nothing to consent to yet */
    var stored = readConsent();
    if (stored) {
      if (stored === "granted") loadPixels(); else { consentDenied = true; heldEvents = []; }
      return;
    }
    var decided = false;
    function ask() { if (decided) return; decided = true; showBanner(); }
    function allow() { if (decided) return; decided = true; loadPixels(); }
    try {
      var ctrl = window.AbortController ? new AbortController() : null;
      var timer = setTimeout(function () { if (ctrl) ctrl.abort(); ask(); }, 2500);
      window.fetch(GEO_ENDPOINT, { signal: ctrl ? ctrl.signal : undefined, credentials: "omit" })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function (g) {
          clearTimeout(timer);
          if (g && g.consent_required === false) allow(); else ask();
        })
        .catch(function () { clearTimeout(timer); ask(); });
    } catch (e) { ask(); }
  }

  /* The switch-off link on the privacy page: <a data-consent-optout>. */
  function optOutLinks() {
    var links = document.querySelectorAll("[data-consent-optout]");
    if (!links.length) return;
    Array.prototype.forEach.call(links, function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        writeConsent("denied");
        consentDenied = true; heldEvents = [];
        var note = document.createElement("p");
        note.className = "small";
        note.setAttribute("role", "status");
        note.textContent = T("js_optout_done");
        a.parentNode.parentNode.insertBefore(note, a.parentNode.nextSibling);
      });
    });
  }

  function showBanner() {
    var bar = document.createElement("div");
    bar.className = "consent-bar";
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", T("js_consent_label"));
    bar.innerHTML =
      '<div class="consent-inner">' +
      '<p>' + T("js_consent_text") + ' <a href="' + PREFIX + '/privacy/">' + T("js_consent_link") + '</a>.</p>' +
      '<div class="consent-actions">' +
      '<button type="button" class="btn" data-consent="denied">' + T("js_no_thanks") + '</button>' +
      '<button type="button" class="btn btn-primary" data-consent="granted">' + T("js_allow") + '</button>' +
      '</div></div>';
    document.body.appendChild(bar);
    bar.addEventListener("click", function (ev) {
      var choice = ev.target && ev.target.getAttribute("data-consent");
      if (!choice) return;
      writeConsent(choice);
      if (choice !== "granted") { consentDenied = true; heldEvents = []; }
      bar.parentNode.removeChild(bar);
      if (choice === "granted") loadPixels();
    });
  }


  /* ------------------------------------------------------------ lightbox
     Any <a class="zoom" href="large.webp"> opens its target full-screen.
     Scroll wheel or pinch to zoom, drag to pan, Esc or a click outside closes. */
  function lightbox() {
    var links = document.querySelectorAll("a.zoom");
    if (!links.length) return;
    var box = document.createElement("div");
    box.className = "lb";
    box.hidden = true;
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", T("js_lb_label"));
    box.innerHTML =
      '<button class="lb-close" type="button" aria-label="' + T("js_lb_close") + '">&times;</button>' +
      '<div class="lb-stage"><img alt="" draggable="false"></div>' +
      '<p class="lb-cap"></p>' +
      '<p class="lb-hint">' + T("js_lb_hint") + '</p>';
    document.body.appendChild(box);
    var stage = box.querySelector(".lb-stage");
    var img = box.querySelector("img");
    var cap = box.querySelector(".lb-cap");
    var closeBtn = box.querySelector(".lb-close");
    var scale = 1, tx = 0, ty = 0, drag = false, sx = 0, sy = 0, pinch = null, last = null, moved = false;

    function apply() { img.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")"; }
    function setScale(v) { scale = Math.min(6, Math.max(1, v)); if (scale === 1) { tx = 0; ty = 0; } apply(); }
    function open(a) {
      last = document.activeElement;
      img.src = a.getAttribute("href");
      var small = a.querySelector("img");
      img.alt = small ? small.alt : "";
      var fig = a.closest ? a.closest("figure") : null;
      var fc = fig && fig.querySelector("figcaption");
      cap.textContent = a.getAttribute("data-caption") || (fc ? fc.textContent : "");
      scale = 1; tx = 0; ty = 0; apply();
      box.hidden = false;
      document.body.style.overflow = "hidden";
      closeBtn.focus();
    }
    function close() {
      box.hidden = true;
      document.body.style.overflow = "";
      img.removeAttribute("src");
      if (last && last.focus) last.focus();
    }
    Array.prototype.forEach.call(links, function (a) {
      a.addEventListener("click", function (ev) { ev.preventDefault(); open(a); });
    });
    closeBtn.addEventListener("click", close);
    box.addEventListener("click", function (ev) { if (ev.target === box || ev.target === cap) close(); });
    stage.addEventListener("click", function (ev) { if (ev.target === stage && !moved) close(); });
    document.addEventListener("keydown", function (ev) { if (!box.hidden && ev.key === "Escape") close(); });
    stage.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      setScale(scale * (ev.deltaY < 0 ? 1.15 : 1 / 1.15));
    }, { passive: false });
    img.addEventListener("dblclick", function () { setScale(scale > 1 ? 1 : 2.5); });
    stage.addEventListener("pointerdown", function (ev) {
      if (scale === 1 || ev.pointerType === "touch" && pinch) return;
      drag = true; moved = false; sx = ev.clientX - tx; sy = ev.clientY - ty;
      try { stage.setPointerCapture(ev.pointerId); } catch (e) {}
    });
    stage.addEventListener("pointermove", function (ev) {
      if (!drag) return;
      moved = true; tx = ev.clientX - sx; ty = ev.clientY - sy; apply();
    });
    function endDrag() { drag = false; setTimeout(function () { moved = false; }, 50); }
    stage.addEventListener("pointerup", endDrag);
    stage.addEventListener("pointercancel", endDrag);
    function dist(t) { var dx = t[0].clientX - t[1].clientX, dy = t[0].clientY - t[1].clientY; return Math.sqrt(dx * dx + dy * dy); }
    stage.addEventListener("touchstart", function (ev) {
      if (ev.touches.length === 2) { drag = false; pinch = { d: dist(ev.touches), s: scale }; }
    }, { passive: true });
    stage.addEventListener("touchmove", function (ev) {
      if (pinch && ev.touches.length === 2) { ev.preventDefault(); setScale(pinch.s * dist(ev.touches) / pinch.d); }
    }, { passive: false });
    stage.addEventListener("touchend", function (ev) { if (ev.touches.length < 2) pinch = null; });
  }

  /* ------------------------------------------- outbound buy clicks (6 Oct 2026)
     Amazon: report the buy-intent click to Whop's pixel, and swap in the paid-ad
     Attribution tag when this visit came from an ad and one exists for the ASIN.
     Whop checkout: carry the ad's wacid/wasid/waid onto the link (Whop records the
     checkout and the purchase itself, so no event is fired for it). */
  function outboundClicks() {
    document.addEventListener("click", function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest("a[href]") : null;
      if (!a) return;
      var url;
      try { url = new URL(a.href); } catch (e) { return; }
      var host = url.hostname.replace(/^www\./, "");
      var ad = currentAd();

      if (host === "whop.com" && /^\/checkout\//.test(url.pathname)) {
        ["wacid", "wasid", "waid"].forEach(function (k) {
          if (ad[k] && !url.searchParams.get(k)) url.searchParams.set(k, ad[k]);
        });
        a.href = url.toString();
        return;
      }

      if (!/^amazon\.(com|es|co\.uk|ca|de|fr|it)$/.test(host)) return;
      var m = url.pathname.match(/\/dp\/([A-Z0-9]{10})/);
      var asin = m ? m[1] : "unknown";
      if (fromPaidAd() && ATTRIB_PAID[asin]) {
        url.searchParams.set("maas", ATTRIB_PAID[asin]);
        url.searchParams.set("ref_", "aa_maas");
        url.searchParams.set("tag", "maas");
        a.href = url.toString();
      }
      var id = eventId("az");
      track("add_to_cart", { event_id: id });
      track("amazon_click_" + host.split(".").slice(1).join(".") + "_" + asin, { event_id: id + "-x" });

      /* give the pixel a moment to send before the page is left; new tabs and
         modified clicks need no wait */
      var plain = !ev.defaultPrevented && ev.button === 0 && !ev.metaKey && !ev.ctrlKey &&
        !ev.shiftKey && !ev.altKey && (a.target || "_self") === "_self";
      if (plain && window.whop && pixelsOn) {
        ev.preventDefault();
        var go = a.href;
        setTimeout(function () { window.location.href = go; }, 250);
      }
    }, true);
  }

  function start() {
    /* form ids carry a language suffix on /es/ and /ca/ (signup-es, sample-dayrabi-ca);
       the id is the source value the server and the email sequences match on */
    Array.prototype.forEach.call(document.querySelectorAll('form[id^="signup"], form[id^="sample"]'), wireForm);
    banner();
    optOutLinks();
    lightbox();
    outboundClicks();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
