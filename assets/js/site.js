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

  /* Shown under the privacy page's switch-off link once it has been clicked.
     Paraphrased through DeepSeek per the publishing rule, 7 Sep 2026. */
  var OPTOUT_DONE = "All done. The advertising pixel will not load again in this browser unless you clear your browser storage.";

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
      if (button) { button.disabled = true; button.textContent = "Sending…"; }
      note.hidden = false;
      note.textContent = "";

      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: input.value.trim(),
          website: pot.value,
          source: form.id || "site"
        })
      })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (res.ok) {
            form.hidden = true;
            var isSample = /^sample/.test(form.id || "");
            if (window.whop && isSample) { try { window.whop.track("complete_registration"); window.whop.track("lead"); } catch (e) {} }
            if (isSample && res.j && res.j.sample_url) {
              /* the server hands back the hosted PDF; show it right here rather
                 than promising an email that nothing sends yet */
              note.textContent = "Your sample is ready.";
              var dl = document.createElement("a");
              dl.className = "btn btn-primary";
              dl.href = res.j.sample_url;
              dl.target = "_blank";
              dl.rel = "noopener";
              dl.textContent = "Open the 30-page sample (PDF)";
              dl.style.cssText = "display:inline-block;margin-top:.7rem";
              note.appendChild(document.createElement("br"));
              note.appendChild(dl);
              dl.focus();
            } else if (isSample) {
              note.textContent = "Thank you. The download link did not come back; email owen@pub.cat and we will send it by hand.";
            } else {
              note.textContent = "Thank you. You are on the list.";
            }
          } else {
            throw new Error((res.j && res.j.error) || "failed");
          }
        })
        .catch(function () {
          note.textContent =
            "That did not go through. Please email us instead and we will add you by hand.";
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
    loadWhopPixel();
    loadMetaPixel();
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
      if (stored === "granted") loadPixels();
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
        var note = document.createElement("p");
        note.className = "small";
        note.setAttribute("role", "status");
        note.textContent = OPTOUT_DONE;
        a.parentNode.parentNode.insertBefore(note, a.parentNode.nextSibling);
      });
    });
  }

  function showBanner() {
    var bar = document.createElement("div");
    bar.className = "consent-bar";
    bar.setAttribute("role", "dialog");
    bar.setAttribute("aria-label", "Advertising cookie");
    bar.innerHTML =
      '<div class="consent-inner">' +
      '<p>We would like to set one advertising cookie, so that we are not paying to ' +
      'show an advert to someone who has already bought the book. Nothing else on this ' +
      'site uses cookies. <a href="/privacy/">What we collect</a>.</p>' +
      '<div class="consent-actions">' +
      '<button type="button" class="btn" data-consent="denied">No thanks</button>' +
      '<button type="button" class="btn btn-primary" data-consent="granted">Allow</button>' +
      '</div></div>';
    document.body.appendChild(bar);
    bar.addEventListener("click", function (ev) {
      var choice = ev.target && ev.target.getAttribute("data-consent");
      if (!choice) return;
      writeConsent(choice);
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
    box.setAttribute("aria-label", "Enlarged image");
    box.innerHTML =
      '<button class="lb-close" type="button" aria-label="Close">&times;</button>' +
      '<div class="lb-stage"><img alt="" draggable="false"></div>' +
      '<p class="lb-cap"></p>' +
      '<p class="lb-hint">Scroll or pinch to zoom in, drag to move around, Esc to close</p>';
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

  function start() {
    wireForm(document.getElementById("signup"));
    Array.prototype.forEach.call(document.querySelectorAll('form[id^="sample"]'), wireForm);
    banner();
    optOutLinks();
    lightbox();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
