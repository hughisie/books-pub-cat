#!/usr/bin/env python3
"""Read-only checker: hreflang, canonical and JSON-LD sanity for books.pub.cat.

    python3 tools/check_hreflang.py

Checks every indexable page (English, /es/, /ca/): en, es, ca and x-default for translated groups; en and x-default for English-only pages;
every alternate is reciprocal and points at a file that exists; canonical is the page itself;
JSON-LD parses; Offers carry price, currency, availability, url; no ISBN is claimed.
Exit code 1 if anything fails (ISBN claims are warnings only). Writes nothing.
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://books.pub.cat"
LANGS = ("en", "es", "ca")


def pages():
    out = []
    for f in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True) + [os.path.join(ROOT, "404.html")]:
        rel = os.path.relpath(f, ROOT)
        if rel.startswith(("tools" + os.sep, ".git")):
            continue
        out.append(f)
    return sorted(out)


def url_of(f):
    rel = os.path.relpath(f, ROOT)
    if rel == "404.html":
        return SITE + "/404.html"
    return SITE + "/" + rel[: -len("index.html")]


def file_of(url):
    p = url[len(SITE):]
    return os.path.join(ROOT, p.strip("/"), "index.html") if p.endswith("/") else os.path.join(ROOT, p.strip("/"))


def attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


warnings = []


def main():
    problems = []
    global warnings
    warnings = []
    info = {}
    for f in pages():
        src = open(f, encoding="utf-8").read()
        u = url_of(f)
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', src):
            continue
        alts = {}
        for tag in re.findall(r'<link\b[^>]*rel="alternate"[^>]*>', src):
            a = attrs(tag)
            if "hreflang" in a:
                if a["hreflang"] in alts:
                    problems.append((u, "duplicate hreflang " + a["hreflang"]))
                alts[a["hreflang"]] = a.get("href", "")
        info[u] = alts
        relative = u[len(SITE):].lstrip('/')
        if relative.startswith(('es/', 'ca/')):
            relative = relative.split('/', 1)[1]
        translated = any(os.path.exists(file_of(SITE + '/' + lang + '/' + relative))
                         for lang in ('es', 'ca'))
        expected = set(LANGS) | {'x-default'} if translated else {'en', 'x-default'}
        if set(alts) != expected:
            problems.append((u, "hreflang set is %s" % sorted(alts)))
        canon = re.findall(r'<link\b[^>]*rel="canonical"[^>]*>', src)
        if len(canon) != 1 or attrs(canon[0]).get("href") != u:
            problems.append((u, "canonical is %s, expected %s" % ([attrs(c).get("href") for c in canon], u)))
        if u not in alts.values():
            problems.append((u, "page not listed in its own hreflang set"))
        for lang, href in alts.items():
            if not href.startswith(SITE + "/") or not os.path.exists(file_of(href)):
                problems.append((u, "hreflang %s -> %s: file missing" % (lang, href)))
            if "/es/es/" in href or "/ca/ca/" in href or "/es/ca/" in href or "/ca/es/" in href:
                problems.append((u, "hreflang %s has a double language prefix: %s" % (lang, href)))
        # JSON-LD
        for i, blk in enumerate(re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S)):
            try:
                d = json.loads(blk)
            except Exception as e:
                problems.append((u, "JSON-LD block %d does not parse: %s" % (i, e)))
                continue
            walk(d, u, problems)
    # reciprocity
    for u, alts in info.items():
        for lang, href in alts.items():
            if href == u or href not in info:
                continue
            if info[href].get(lang) != href or u not in info[href].values():
                problems.append((u, "not reciprocal with " + href))
        if alts.get("x-default") and alts["x-default"] != alts.get("en"):
            problems.append((u, "x-default differs from en"))
    for u, m in problems:
        print("FAIL %s  %s" % (u, m))
    for u, m in warnings:
        print("WARN %s  %s" % (u, m))
    print("%d indexable pages checked, %d problems, %d warnings" % (len(info), len(problems), len(warnings)))
    return 1 if problems else 0


def walk(d, u, problems, top_checked=False):
    if isinstance(d, list):
        for x in d:
            walk(x, u, problems, top_checked)
    elif isinstance(d, dict):
        t = d.get("@type")
        ts = t if isinstance(t, list) else [t]
        if "Offer" in ts:
            for k in ("price", "priceCurrency", "availability", "url"):
                if not d.get(k):
                    problems.append((u, "Offer missing " + k))
        if "Book" in ts and not top_checked:
            top_checked = True
            for k in ("inLanguage", "author"):
                if k not in d:
                    problems.append((u, "Book missing " + k))
        for k in d:
            if k.lower() in ("isbn",) :
                warnings.append((u, "JSON-LD claims an ISBN (KDP-issued; Owen to rule)"))
        for v in d.values():
            walk(v, u, problems, top_checked)


if __name__ == "__main__":
    sys.exit(main())
