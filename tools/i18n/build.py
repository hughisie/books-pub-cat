#!/usr/bin/env python3
"""books.pub.cat in English, Spanish and Catalan. Plain stdlib, no build step for the site.

The English pages at the repo root are the source. Spanish lives under /es/, Catalan
under /ca/, with the same paths. The Spanish and Catalan wording is DeepSeek's
translation (tools/i18n/ds-translate.py, run on london); this script never writes prose.

    python3 tools/i18n/build.py chrome      # header, footer, hreflang on the English pages
    python3 tools/i18n/build.py extract     # tools/i18n/src/*.html: what to translate
    (translate src/*.html and chrome.en.html on london into tr/es and tr/ca)
    python3 tools/i18n/build.py assemble    # write es/ and ca/ from the English pages + tr/
    python3 tools/i18n/build.py js          # the interface strings inside assets/js/site.js
    python3 tools/i18n/build.py sitemap     # sitemap.xml with all three languages

After editing an English page: run chrome, extract, translate the changed file, assemble.
"""
import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = "https://books.pub.cat"
LANGS = ("es", "ca")
HTML_LANG = {"en": "en-GB", "es": "es", "ca": "ca"}
OG_LOCALE = {"en": "en_GB", "es": "es_ES", "ca": "ca_ES"}

# Pages that exist in all three languages: path -> (nav key for aria-current, slim chrome)
PAGES = {
    "/": (None, False),
    "/books/": ("books", False),
    "/shams-al-maarif/": ("shams", False),
    "/shams-al-maarif/read/": (None, True),
    "/mujarrabat-al-dayrabi/": ("dayrabi", False),
    "/mujarrabat-al-dayrabi/read/": (None, True),
    "/al-buni/": (None, False),
    "/what-is-ilm-al-huruf/": (None, False),
    "/magic-squares/": (None, False),
    "/editions/": ("editions", False),
    "/about/": ("about", False),
    "/faq/": (None, False),
    "/contact/": (None, False),
    "/refunds/": (None, False),
    "/privacy/": (None, False),
    "/terms/": (None, False),
}


def _gen_pages():
    """The Catalan book pages, written by tools/catalan/gen.py in all three languages.
    They join the switcher, hreflang and sitemap, but chrome/extract/assemble leave them alone."""
    import json
    f = os.path.join(ROOT, "tools", "catalan", "books.json")
    if not os.path.exists(f):
        return {}
    return {"/%s/" % b["slug"]: ("books", False) for b in json.load(open(f, encoding="utf-8"))["books"]}


GEN = _gen_pages()
ALL = {**PAGES, **GEN}
# English only (noindex): they get the chrome, and the switcher points at the home pages
EN_ONLY = {
    "/shams-al-maarif/thank-you/": "shams",
    "/mujarrabat-al-dayrabi/thank-you/": "dayrabi",
    "/404.html": None,
}
# Pages whose hero gets the "this book is in English" note in es/ca
BOOK_NOTE = ("/shams-al-maarif/", "/mujarrabat-al-dayrabi/", "/shams-al-maarif/read/",
             "/mujarrabat-al-dayrabi/read/")
SITE_NOTE = ("/", "/books/")


def fpath(p):
    return os.path.join(ROOT, p.strip("/"), "index.html") if p.endswith("/") else os.path.join(ROOT, p.strip("/"))


def rd(p):
    return open(p, encoding="utf-8").read()


def wr(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def strings(lang):
    f = os.path.join(HERE, "chrome.en.html") if lang == "en" else os.path.join(HERE, "tr", lang, "chrome.html")
    return dict(re.findall(r'<p data-k="([a-z_]+)">(.*?)</p>', rd(f), re.S))


def pre(lang):
    return "" if lang == "en" else "/" + lang


def switcher(t, lang, path):
    links = []
    for l in ("en", "es", "ca"):
        href = (pre(l) + path) if path in ALL else (pre(l) + "/")
        cur = ' aria-current="true"' if l == lang else ""
        links.append(f'<a href="{href}" hreflang="{l}" lang="{l}"{cur}>{l.upper()}</a>')
    return f'    <nav class="lang-switch" aria-label="{t["lang_label"]}">\n      ' + "\n      ".join(links) + "\n    </nav>"


def header(t, lang, path, current, slim):
    p = pre(lang)
    if slim:
        return (f'<header class="site-head slim">\n  <div class="wrap">\n'
                f'    <a class="brand" href="{p}/"><b>Pub.Cat</b> Books</a>\n'
                f'{switcher(t, lang, path)}\n  </div>\n</header>')
    items = [("books", p + "/books/", t["nav_books"]),
             ("shams", p + "/shams-al-maarif/", "Shams al-Maʿārif"),
             ("dayrabi", p + "/mujarrabat-al-dayrabi/", "al-Dayrabī"),
             ("editions", p + "/editions/", t["nav_editions"]),
             ("about", p + "/about/", t["nav_about"])]
    cur_attr = ' aria-current="page"'
    nav = "\n".join(f'      <a href="{h}"{cur_attr if k == current else ""}>{x}</a>'
                    for k, h, x in items)
    return (f'<header class="site-head">\n  <div class="wrap">\n'
            f'    <a class="brand" href="{p}/"><b>Pub.Cat</b> Books</a>\n'
            f'    <nav class="site-nav" aria-label="{t["nav_label"]}">\n{nav}\n    </nav>\n'
            f'{switcher(t, lang, path)}\n  </div>\n</header>')


def footer(t, lang, slim):
    p = pre(lang)
    note = f'\n      <p class="small lang-note-site">{t["lang_note_site"]}</p>' if lang != "en" else ""
    if slim:
        return (f'<footer class="site-foot slim">\n  <div class="wrap">\n    <div class="foot-legal">\n'
                f'      <p>{t["slim_imprint"]} <a href="{p}/privacy/">{t["slim_privacy"]}</a> · '
                f'<a href="{p}/terms/">{t["slim_terms"]}</a></p>{note}\n'
                f'      <p class="small">{t["slim_disclaimer"]}</p>\n    </div>\n  </div>\n</footer>')

    def col(h, rows):
        lis = "\n".join(f'          <li><a href="{u}">{x}</a></li>' for u, x in rows)
        return f"      <div>\n        <h4>{h}</h4>\n        <ul>\n{lis}\n        </ul>\n      </div>"
    cols = [
        col(t["f_books"], [(p + "/books/", t["f_all"]),
                           (p + "/shams-al-maarif/", "Shams al-Maʿārif"),
                           (p + "/mujarrabat-al-dayrabi/", "Mujarrabāt al-Dayrabī"),
                           (p + "/shams-al-maarif/read/", t["f_sample_shams"]),
                           (p + "/mujarrabat-al-dayrabi/read/", t["f_sample_dayrabi"]),
                           (p + "/editions/", t["f_editions"]),
                           (p + "/faq/", t["f_faq"])]),
        col(t["f_background"], [(p + "/al-buni/", t["f_buni"]),
                                (p + "/what-is-ilm-al-huruf/", t["f_letters"]),
                                (p + "/magic-squares/", t["f_squares"])]),
        col(t["f_press"], [(p + "/about/", t["f_about"]), (p + "/contact/", t["f_contact"]),
                           ("https://pub.cat/", "Pub.Cat")]),
        col(t["f_legal"], [(p + "/refunds/", t["f_refunds"]), (p + "/privacy/", t["f_privacy"]),
                           (p + "/terms/", t["f_terms"])]),
    ]
    return (f'<footer class="site-foot">\n  <div class="wrap">\n    <div class="foot-grid">\n'
            + "\n".join(cols) +
            f'\n    </div>\n    <div class="foot-legal">\n      <p>{t["imprint"]}</p>{note}\n'
            f'      <p class="small">{t["disclaimer"]}</p>\n    </div>\n  </div>\n</footer>')


def hreflang(path):
    out = ["<!-- hreflang -->"]
    for l in ("en", "es", "ca"):
        out.append(f'<link rel="alternate" hreflang="{l}" href="{SITE}{pre(l)}{path}">')
    out.append(f'<link rel="alternate" hreflang="x-default" href="{SITE}{path}">')
    return "\n".join(out) + "\n<!-- /hreflang -->"


def set_chrome(s, t, lang, path, current, slim):
    s = re.sub(r'<a class="skip" href="#main">.*?</a>', f'<a class="skip" href="#main">{t["skip"]}</a>', s, count=1)
    s = re.sub(r"<header class=\"site-head[^\"]*\">.*?</header>", lambda m: header(t, lang, path, current, slim), s, count=1, flags=re.S)
    s = re.sub(r"<footer class=\"site-foot[^\"]*\">.*?</footer>", lambda m: footer(t, lang, slim), s, count=1, flags=re.S)
    s = re.sub(r"\n<!-- hreflang -->.*?<!-- /hreflang -->", "", s, flags=re.S)
    if path in ALL:
        s = re.sub(r'(<link rel="canonical"[^>]*>)', lambda m: m.group(1) + "\n" + hreflang(path), s, count=1)
    s = re.sub(r'main\.css(\?v=[\w]+)?"', 'main.css?v=20261002a"', s)
    s = re.sub(r'site\.js(\?v=[\w]+)?"', 'site.js?v=20261006t"', s)
    return s


def cmd_chrome():
    t = strings("en")
    for path, (cur, slim) in PAGES.items():
        f = fpath(path)
        wr(f, set_chrome(rd(f), t, "en", path, cur, slim))
    for path, cur in EN_ONLY.items():
        f = fpath(path)
        wr(f, set_chrome(rd(f), t, "en", path, cur, False))
    print("chrome: %d pages" % (len(PAGES) + len(EN_ONLY)))


META = (("title", r"<title>(.*?)</title>"),
        ("desc", r'<meta name="description" content="(.*?)">'),
        ("ogtitle", r'<meta property="og:title" content="(.*?)">'),
        ("ogdesc", r'<meta property="og:description" content="(.*?)">'))


def slug(path):
    return path.strip("/").replace("/", "__") or "home"


def cmd_extract():
    for path in PAGES:
        s = rd(fpath(path))
        parts = []
        for k, rx in META:
            v = html.unescape(re.search(rx, s, re.S).group(1))
            parts.append(f'<p data-k="{k}">{html.escape(v, quote=False)}</p>')
        main = re.search(r"<main id=\"main\">.*?</main>", s, re.S).group(0)
        wr(os.path.join(HERE, "src", slug(path) + ".html"), "\n".join(parts) + "\n" + main + "\n")
    print("extract: %d pages into tools/i18n/src" % len(PAGES))


def localise_links(s, lang):
    p = "/" + lang
    s = re.sub(r'href="/(?!assets/|/)', f'href="{p}/', s)
    s = re.sub(r"(utm_medium=)([\w-]+)", lambda m: m.group(1) + m.group(2) + "-" + lang, s)
    s = re.sub(r'(<form\b[^>]*\bid=")((?:signup|sample)[\w-]*)(")', lambda m: m.group(1) + m.group(2) + "-" + lang + m.group(3), s)
    return s


def cmd_assemble():
    for lang in LANGS:
        t = strings(lang)
        for path, (cur, slim) in PAGES.items():
            s = rd(fpath(path))
            tr = rd(os.path.join(HERE, "tr", lang, slug(path) + ".html"))
            meta = dict(re.findall(r'<p data-k="([a-z]+)">(.*?)</p>', tr.split("<main", 1)[0], re.S))
            main = re.search(r"<main id=\"main\">.*?</main>", tr, re.S).group(0)
            main = localise_links(main, lang)
            if path in BOOK_NOTE or path in SITE_NOTE:
                key = "lang_note" if path in BOOK_NOTE else "lang_note_site"
                main = re.sub(r'(<p class="lede">.*?</p>)',
                              lambda m: m.group(1) + f'\n          <p class="lang-note">{t[key]}</p>', main, count=1, flags=re.S)
            s = s.replace('<html lang="en-GB">', f'<html lang="{HTML_LANG[lang]}">', 1)

            def attr(v):
                return html.escape(html.unescape(v), quote=True)
            s = re.sub(r"<title>.*?</title>", lambda m: f"<title>{meta['title']}</title>", s, count=1, flags=re.S)
            s = re.sub(r'<meta name="description" content=".*?">', lambda m: f'<meta name="description" content="{attr(meta["desc"])}">', s, count=1)
            s = re.sub(r'<meta property="og:title" content=".*?">', lambda m: f'<meta property="og:title" content="{attr(meta["ogtitle"])}">', s, count=1)
            s = re.sub(r'<meta property="og:description" content=".*?">', lambda m: f'<meta property="og:description" content="{attr(meta["ogdesc"])}">', s, count=1)
            s = s.replace(f'<link rel="canonical" href="{SITE}{path}">', f'<link rel="canonical" href="{SITE}/{lang}{path}">', 1)
            s = s.replace(f'<meta property="og:url" content="{SITE}{path}">',
                          f'<meta property="og:url" content="{SITE}/{lang}{path}">\n<meta property="og:locale" content="{OG_LOCALE[lang]}">', 1)
            # the FAQ structured data is English; better none than a mismatch
            s = re.sub(r'<script type="application/ld\+json">\{"@context":"https://schema.org","@type":"FAQPage".*?</script>\n?', "", s, flags=re.S)
            s = re.sub(r"<main id=\"main\">.*?</main>", lambda m: main, s, count=1, flags=re.S)
            s = set_chrome(s, t, lang, path, cur, slim)
            assert f"/{lang}{path}" in s
            wr(os.path.join(ROOT, lang, path.strip("/"), "index.html") if path != "/" else os.path.join(ROOT, lang, "index.html"), s)
    print("assemble: %d pages per language" % len(PAGES))


def cmd_sitemap():
    pr = {"/": "0.9", "/books/": "1.0", "/shams-al-maarif/": "1.0", "/mujarrabat-al-dayrabi/": "1.0",
          "/shams-al-maarif/read/": "0.8", "/mujarrabat-al-dayrabi/read/": "0.8", "/contact/": "0.3",
          "/refunds/": "0.3", "/privacy/": "0.2", "/terms/": "0.2", "/faq/": "0.5", "/about/": "0.5"}
    pr.update({p: "0.9" for p in GEN})
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for path in ALL:
        alts = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{l}" href="{SITE}{pre(l)}{path}"/>' for l in ("en", "es", "ca"))
        alts += f'\n    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE}{path}"/>'
        for l in ("en", "es", "ca"):
            out.append(f"  <url><loc>{SITE}{pre(l)}{path}</loc><priority>{pr.get(path, '0.7')}</priority>{alts}\n  </url>")
    out.append("</urlset>")
    wr(os.path.join(ROOT, "sitemap.xml"), "\n".join(out) + "\n")
    print("sitemap: %d urls" % (len(ALL) * 3))


def cmd_js():
    import json
    d = {}
    for lang in ("en",) + LANGS:
        t = strings(lang)
        d[lang] = {k: html.unescape(v) for k, v in t.items() if k.startswith("js_")}
    block = "  var I18N = " + json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\n  ") + ";\n"
    f = os.path.join(ROOT, "assets", "js", "site.js")
    s = rd(f)
    s = re.sub(r"(/\* I18N:BEGIN \*/\n).*?(  /\* I18N:END \*/)", lambda m: m.group(1) + block + m.group(2), s, count=1, flags=re.S)
    wr(f, s)
    print("js: strings for %s" % ", ".join(d))


if __name__ == "__main__":
    {"chrome": cmd_chrome, "extract": cmd_extract, "assemble": cmd_assemble, "sitemap": cmd_sitemap,
     "js": cmd_js}[sys.argv[1]]()
