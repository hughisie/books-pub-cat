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

  function loadPixel() {
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
    if (!META_PIXEL_ID) return;            /* nothing to consent to yet */
    if (readConsent()) {
      if (readConsent() === "granted") loadPixel();
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
      if (choice === "granted") loadPixel();
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
