"""Meta Conversions API relay for books.pub.cat (12 Oct 2026, cc-metaturn1).

The site is static (GitHub Pages), so the browser posts each consented pixel event here as
well, with the same event id, and this module forwards it to Meta server-side. Meta keeps one
copy of each event (pixel and server share the event id), and gets a better match because the
server adds the visitor's IP address and browser string.

Wiring (not live until Owen approves card books-meta-tracking-approve):
  server.py do_POST:  if path == "/books/capi": capi_relay.handle(self); return
  Caddyfile @books:   add /books/capi to the path list
  env:                BOOKS_META_PIXEL_ID, BOOKS_META_CAPI_TOKEN (written by meta_pixel_install.py)
While either env value is missing the endpoint answers 204 and sends nothing.

Rules kept: no email or other personal detail is accepted or sent; the token is never logged;
only five event names are passed on; only requests from books.pub.cat are accepted.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request

LOG = logging.getLogger("books.capi")
GRAPH = "https://graph.facebook.com/v21.0"
ALLOWED_EVENTS = {"PageView", "ViewContent", "AddToCart", "Lead", "AmazonBuyClick"}
ALLOWED_ORIGINS = {"https://books.pub.cat"}
CUSTOM_KEYS = {"content_ids", "content_name", "content_type", "content_category", "value", "currency", "asin", "store"}
_RATE: dict[str, list[float]] = {}
_RATE_LOCK = threading.Lock()
MAX_PER_MIN = 60


def config(env=os.environ):
    return env.get("BOOKS_META_PIXEL_ID", "").strip(), env.get("BOOKS_META_CAPI_TOKEN", "").strip()


def _rate_ok(ip: str, now: float | None = None) -> bool:
    now = now or time.time()
    with _RATE_LOCK:
        hits = [t for t in _RATE.get(ip, []) if now - t < 60]
        if len(hits) >= MAX_PER_MIN:
            _RATE[ip] = hits
            return False
        hits.append(now)
        _RATE[ip] = hits
        return True


def _clean_custom(d) -> dict:
    out = {}
    if not isinstance(d, dict):
        return out
    for k, v in d.items():
        if k not in CUSTOM_KEYS:
            continue
        if k == "content_ids":
            if isinstance(v, list):
                out[k] = [str(x)[:60] for x in v[:5]]
        elif k == "value":
            try:
                out[k] = round(float(v), 2)
            except (TypeError, ValueError):
                pass
        else:
            out[k] = str(v)[:80]
    return out


def build_event(body: dict, ip: str, ua: str, now: float | None = None) -> dict | None:
    """Turn the browser's JSON into one Meta server event, or None if it is not acceptable."""
    name = body.get("event_name")
    eid = str(body.get("event_id") or "")[:80]
    url = str(body.get("event_source_url") or "")[:500]
    if name not in ALLOWED_EVENTS or not eid or not url.startswith("https://books.pub.cat/"):
        return None
    user = {"client_ip_address": ip, "client_user_agent": ua[:400]}
    for k in ("fbp", "fbc"):
        v = str(body.get(k) or "")
        if v.startswith("fb.") and len(v) < 400:
            user[k] = v
    return {
        "event_name": name,
        "event_time": int(now or time.time()),
        "event_id": eid,
        "action_source": "website",
        "event_source_url": url,
        "user_data": user,
        "custom_data": _clean_custom(body.get("custom_data")),
    }


def send(event: dict, pixel: str, token: str, opener=urllib.request.urlopen) -> int:
    data = json.dumps({"data": [event]}).encode()
    req = urllib.request.Request(f"{GRAPH}/{pixel}/events?access_token={token}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with opener(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        LOG.warning("capi: Meta refused %s (%s)", event["event_name"], e.code)
        return e.code
    except Exception as e:  # noqa: BLE001
        LOG.warning("capi: send failed for %s: %s", event["event_name"], type(e).__name__)
        return 0


def handle(h, env=os.environ, opener=urllib.request.urlopen, background=True) -> None:
    """h is the BaseHTTPRequestHandler; the body has already been read into h._capi_raw."""
    origin = h.headers.get("Origin", "")
    hdrs = {"Cache-Control": "no-store"}
    if origin in ALLOWED_ORIGINS:
        hdrs.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
    pixel, token = config(env)
    ip = (h.headers.get("CF-Connecting-IP") or h.headers.get("X-Forwarded-For", "").split(",")[0]
          or h.client_address[0]).strip()
    if not pixel or not token or origin not in ALLOWED_ORIGINS or not _rate_ok(ip):
        h._send(204, {}, hdrs)
        return
    try:
        body = json.loads(h._capi_raw.decode() or "{}")
    except (ValueError, UnicodeDecodeError):
        h._send(204, {}, hdrs)
        return
    ev = build_event(body, ip, h.headers.get("User-Agent", "")) if isinstance(body, dict) else None
    if ev:
        if background:
            threading.Thread(target=send, args=(ev, pixel, token, opener), daemon=True).start()
        else:
            send(ev, pixel, token, opener)
    h._send(204, {}, hdrs)
