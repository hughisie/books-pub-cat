/* books.pub.cat — email capture and the consent-gated Meta pixel.
 *
 * Two rules this file exists to keep:
 *   1. The privacy page promises "you will be asked before it loads" about the
 *      advertising pixel, with no geographic exception. So the pixel loads only
 *      after an explicit click, for every visitor, everywhere.
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
            if (window.whop && form.id === "sample-form") { try { window.whop.track("complete_registration"); window.whop.track("lead"); } catch (e) {} }
            note.textContent = form.id === "sample-form"
              ? "Thank you. The sample is on its way to " + input.value.trim() + "."
              : "Thank you. You are on the list.";
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

  function banner() {
    if (!META_PIXEL_ID && !WHOP_BIZ_ID) return;   /* nothing to consent to yet */
    if (readConsent()) {
      if (readConsent() === "granted") loadPixels();
      return;
    }
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

  function start() {
    wireForm(document.getElementById("signup"));
    wireForm(document.getElementById("sample-form"));
    banner();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
