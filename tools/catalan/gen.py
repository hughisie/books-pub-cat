#!/usr/bin/env python3
"""The Catalan classics on books.pub.cat, and the own-site paperback shop. Plain stdlib.

    python3 tools/catalan/gen.py content     # text/<slug>.ca.html from the paraphrased descriptions
    python3 tools/catalan/gen.py translate   # text/<slug>.{en,es}.html by DeepSeek on london
    python3 tools/catalan/gen.py build       # book pages (en, es, ca), catalogue cards, shop boxes
    python3 tools/i18n/build.py sitemap      # then the sitemap, which already knows these pages

Wording rules (Owen's publishing rule):
  * The Catalan text is the published KDP/Whop description, already paraphrased by Gemini
    (pubcat-books titles/<work>/public/description.md). Nothing here writes Catalan prose.
  * English and Spanish book text is DeepSeek's translation of that Catalan (translate).
  * Interface labels: labels.en.html (sentences rewritten by DeepSeek), labels.es/ca.html
    (DeepSeek translations). REUSED holds strings already live on the site in all three languages.

books.json "paperback_shop": false keeps every own-site paperback button and offer out of the
pages and the structured data. Owen says go: set it true, build, check locally, push.
"""
import html
import json
import os
import re
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "i18n"))
import build  # noqa: E402  (chrome, hreflang, language prefixes)

BOOKS_REPO = os.path.expanduser(os.environ.get("PUBCAT_BOOKS_REPO", "~/repos/pubcat-books"))
SITE = "https://books.pub.cat"
LANGS = ("en", "es", "ca")
DATA = json.load(open(os.path.join(HERE, "books.json"), encoding="utf-8"))
SHOP_ON = bool(DATA.get("paperback_shop"))
# the hidden Whop plan ids stay in the private books repo until the shop goes live
_SHOP_FILE = os.path.join(BOOKS_REPO, "fulfilment", "whop_paperback_products.json")
SHOP = json.load(open(_SHOP_FILE, encoding="utf-8"))["shop"] if os.path.exists(_SHOP_FILE) else {}
UTM = "utm_source=books.pub.cat&amp;utm_medium={m}&amp;utm_campaign={c}"

# Already live on books.pub.cat in all three languages (al-Dayrabi page and catalogue).
REUSED = {
    "choose_edition": ("Choose an edition", "Elige una edición", "Tria una edició"),
    "editions": ("Editions", "Ediciones", "Edicions"),
    "pick_format": ("Pick a format", "Elige un formato", "Tria un format"),
    "what_is": ("What this book is", "Qué es este libro", "Què és aquest llibre"),
    "formats": ("Formats", "Formatos", "Formats"),
    "translator": ("Translator", "Traductor", "Traductor"),
    "paperback": ("Paperback", "Rústica", "En paper"),
    "digital": ("Digital", "Digital", "Digital"),
    "kindle_li": ("Sent to your Kindle device or the Kindle app",
                  "Se envía a tu dispositivo Kindle o a la aplicación Kindle",
                  "Enviat al teu dispositiu Kindle o a l'aplicació Kindle"),
    "amazon_price": ("Pricing controlled by Amazon", "El precio lo controla Amazon", "Preu controlat per Amazon"),
    "buy_amazon": ("Buy on Amazon", "Comprar en Amazon", "Compra a Amazon"),
    "pb_size": ("229 x 152 mm, black and white", "229 x 152 mm, blanco y negro", "229 x 152 mm, blanc i negre"),
    "pb_dispatched": ("Dispatched by Amazon", "Enviada por Amazon", "Enviat per Amazon"),
    "buy_digital": ("Buy the digital edition", "Comprar la edición digital", "Compra l'edició digital"),
    "about_book": ("About the book", "Sobre el libro", "Sobre el llibre"),
}
FMT = {"en": "EPUB", "es": "EPUB", "ca": "EPUB"}
REGIONS = ("ES", "EU", "UK", "US")


def rd(p):
    return open(p, encoding="utf-8").read()


def wr(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(s)


def labels(lang):
    d = dict(re.findall(r'<p data-k="(\w+)">(.*?)</p>', rd(os.path.join(HERE, "labels.%s.html" % lang)), re.S))
    i = LANGS.index(lang)
    d.update({k: v[i] for k, v in REUSED.items()})
    return d


L = {lang: labels(lang) for lang in LANGS}


def book(slug):
    return next(b for b in DATA["books"] if b["slug"] == slug)


def money(amount, cur, lang):
    a = "%.2f" % float(amount)
    if cur == "USD":
        return "$" + a
    return "€" + a if lang == "en" else a.replace(".", ",") + " €"


def esc(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- content (Catalan source)

def md_inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    return re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)


def parse_description(path):
    """The published description: '# heading', a bold line, bullets, story paragraphs, then the
    style paragraph ('Aquesta traducció' / 'Aquesta versió') and the credit ('Traducció ...')."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", rd(path)) if b.strip()]
    bullets, about, translation = [], [], []
    for b in blocks:
        if b.startswith("#") or (b.startswith("**") and b.endswith("**")):
            continue
        if b.startswith("- "):
            bullets += [x[2:].strip() for x in b.splitlines() if x.startswith("- ")]
        elif re.match(r"(Aquesta (traducció|versió)|Traducció )", b):
            translation.append(b)
        else:
            about.append(b)
    return bullets, about, translation


def fragment(lede, bullets, about, translation):
    out = ['<div data-part="lede">\n<p>%s</p>\n</div>' % md_inline(lede)]
    if bullets:
        out.append('<div data-part="edition">\n<ul>\n%s\n</ul>\n</div>' % "\n".join(
            "<li>%s</li>" % md_inline(x) for x in bullets))
    out.append('<div data-part="about">\n%s\n</div>' % "\n".join(about))
    out.append('<div data-part="translation">\n%s\n</div>' % "\n".join(
        "<p>%s</p>" % md_inline(x) for x in translation))
    return "\n".join(out) + "\n"


def cmd_content():
    for b in DATA["books"]:
        if "combines" in b:
            continue
        bullets, about, tr = parse_description(os.path.join(BOOKS_REPO, b["description_md"]))
        wr(os.path.join(HERE, "text", b["slug"] + ".ca.html"),
           fragment(b["lede_ca"], bullets, ["<p>%s</p>" % md_inline(x) for x in about], tr))
    # the two-story paperback: both stories' plot paragraphs under their own titles, one credit
    for b in DATA["books"]:
        if "combines" not in b:
            continue
        about, tr = [], None
        for s in b["combines"]:
            part = book(s)
            _, ab, t = parse_description(os.path.join(BOOKS_REPO, part["description_md"]))
            about.append("<h3>%s</h3>" % esc(part["title"]))
            about += ["<p>%s</p>" % md_inline(x) for x in ab]
            tr = tr or [x for x in t if x.startswith("Traducció ")]
        wr(os.path.join(HERE, "text", b["slug"] + ".ca.html"), fragment(b["lede_ca"], [], about, tr))
    print("content: %d Catalan fragments" % len(DATA["books"]))


def cmd_translate():
    """DeepSeek on london (key in /opt/pubcat/secrets/.env); scratch in /root/scratch, never /tmp."""
    tool = os.path.join(ROOT, "tools", "i18n", "ds-translate.py")
    tag = "cat-" + uuid.uuid4().hex[:8]
    subprocess.run(["ssh", "london", "mkdir -p /root/scratch && chmod 700 /root/scratch && cat > /root/scratch/%s-tr.py" % tag],
                   input=open(tool, "rb").read(), check=True)
    only = sys.argv[2:]
    for b in DATA["books"]:
        if only and b["slug"] not in only:
            continue
        src = os.path.join(HERE, "text", b["slug"] + ".ca.html")
        subprocess.run(["ssh", "london", "cat > /root/scratch/%s-%s.ca.html" % (tag, b["slug"])],
                       input=open(src, "rb").read(), check=True)
        for lang in ("en", "es"):
            r = subprocess.run(["ssh", "london", "set -a; . /opt/pubcat/secrets/.env; set +a; cd /root/scratch; "
                                "python3 %s-tr.py --src ca --lang %s --in %s-%s.ca.html --out %s-%s.%s.html && cat %s-%s.%s.html"
                                % (tag, lang, tag, b["slug"], tag, b["slug"], lang, tag, b["slug"], lang)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                sys.exit("translate %s %s FAILED: %s" % (b["slug"], lang, r.stderr.strip()[-600:]))
            wr(os.path.join(HERE, "text", "%s.%s.html" % (b["slug"], lang)), r.stdout)
            print("translated %s -> %s" % (b["slug"], lang))
    subprocess.run(["ssh", "london", "rm -f /root/scratch/%s-*" % tag], check=True)


def parts(slug, lang):
    s = rd(os.path.join(HERE, "text", "%s.%s.html" % (slug, lang)))
    return {k: v.strip() for k, v in re.findall(r'<div data-part="(\w+)">(.*?)</div>', s, re.S)}


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


# ---------------------------------------------------------------- shop

def shop_plans(key):
    return SHOP.get(key) or {}


def shop_box(key, pb, lang, medium):
    """The own-site paperback box. Empty unless the shop is on and the Whop plans exist."""
    plans = shop_plans(key)
    if not (SHOP_ON and plans.get("plans")):
        return ""
    t = L[lang]
    cur = pb["currency"]
    rows = []
    for r in REGIONS:
        p = plans["plans"].get(r)
        if not p:
            continue
        url = "https://whop.com/checkout/%s?%s" % (p["plan"], UTM.format(m=medium + "-paperback", c=key))
        rows.append('<li><span class="f-name"><a href="%s">%s</a></span> <span class="f-price">%s</span></li>'
                    % (url, t["region_" + r], money(p["price"], cur, lang)))
    return ('<div class="buybox" id="paperback-shop" style="border-color:var(--gold)">\n'
            '<h3>%s <span class="price">%s</span></h3>\n<p class="small dim">%s</p>\n'
            '<ul>\n<li>%s</li>\n<li>%s</li>\n<li>%s</li>\n</ul>\n'
            '<ul class="formats">\n%s\n</ul>\n<p class="small dim">%s</p>\n</div>'
            % (t["pb_shop_title"], money(pb["price"], cur, lang), t["pb_shop_sub"], t["pb_shop_li1"],
               t["pb_shop_li2"], t["pb_shop_li3"], "\n".join(rows), t["incl_postage"]))


def shipping_ld(key, pb):
    """schema.org shippingDetails per region, from the Whop plan prices (book price + postage)."""
    plans = shop_plans(key).get("plans", {})
    countries = {"ES": ["ES"], "EU": ["PT", "FR", "DE", "IT", "NL", "BE", "AT", "IE"], "UK": ["GB"], "US": ["US"]}
    h0, h1 = DATA["handling_days"]
    t0, t1 = DATA["delivery_days"]
    out = []
    for r, p in plans.items():
        out.append({
            "@type": "OfferShippingDetails",
            "shippingRate": {"@type": "MonetaryAmount", "value": "%.2f" % (float(p["price"]) - float(pb["price"])),
                             "currency": pb["currency"]},
            "shippingDestination": [{"@type": "DefinedRegion", "addressCountry": c} for c in countries[r]],
            "deliveryTime": {"@type": "ShippingDeliveryTime",
                             "handlingTime": {"@type": "QuantitativeValue", "minValue": h0, "maxValue": h1, "unitCode": "DAY"},
                             "transitTime": {"@type": "QuantitativeValue", "minValue": t0, "maxValue": t1, "unitCode": "DAY"}},
        })
    return out


def paperback_ld(key, pb, title, url, lang):
    """The paperback as Book + Product with its ISBN. Our own offer only when the shop is on;
    otherwise the Amazon offer, as on the rest of the site."""
    amazon = "https://www.amazon.%s/dp/%s" % (pb["kdp_marketplace_home"], pb["asin"])
    item = {
        "@type": ["Book", "Product"],
        "name": "%s (%s)" % (title, REUSED["paperback"][0].lower()),
        "bookFormat": "https://schema.org/Paperback",
        "isbn": pb["isbn"], "gtin13": pb["isbn"], "sku": "PCB-" + pb["isbn"],
        "numberOfPages": pb["pages"],
        "brand": {"@type": "Brand", "name": "Independently published"},
        "sameAs": amazon,
    }
    if SHOP_ON and shop_plans(key).get("plans"):
        item["offers"] = {
            "@type": "Offer", "price": pb["price"], "priceCurrency": pb["currency"],
            "availability": "https://schema.org/InStock", "itemCondition": "https://schema.org/NewCondition",
            "url": url + "#paperback-shop", "priceValidUntil": "2026-12-31",
            "shippingDetails": shipping_ld(key, pb),
            "hasMerchantReturnPolicy": {
                "@type": "MerchantReturnPolicy", "applicableCountry": "ES",
                "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                "merchantReturnDays": 14, "returnMethod": "https://schema.org/ReturnByMail",
                "returnFees": "https://schema.org/ReturnShippingFees",
                "merchantReturnLink": SITE + build.pre(lang) + "/refunds/"},
        }
    else:
        item["offers"] = {"@type": "Offer", "price": pb["price"], "priceCurrency": pb["currency"],
                          "availability": "https://schema.org/InStock", "url": amazon}
    return item


# ---------------------------------------------------------------- pages

def head(b, lang, title, desc, url, ld):
    return f"""<!doctype html>
<html lang="{build.HTML_LANG[lang]}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="book">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">{'' if lang == 'en' else chr(10) + '<meta property="og:locale" content="%s">' % build.OG_LOCALE[lang]}
<meta property="og:image" content="{SITE}/assets/img/og-{b['img']}.jpg">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap">
<link rel="stylesheet" href="/assets/css/main.css?v=20261006a">
<script type="application/ld+json">
{json.dumps(ld, ensure_ascii=False, indent=1)}
</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head"></header>
"""


def buy_section(b, lang, p):
    t = L[lang]
    pre = build.pre(lang)
    medium = "book-page" if lang == "en" else "book-page-" + lang
    boxes = []
    if "ebook" in b:
        e = b["ebook"]
        boxes.append(f"""        <div class="buybox">
<h3>{t['digital']} <span class="price">{money(e['price'], 'EUR', lang)}</span></h3>
<p class="small dim">{t['digital_sub']}</p>
<ul>
<li>{t['digital_li']}</li>
</ul>
<a class="btn btn-primary" href="https://whop.com/checkout/{e['plan']}?{UTM.format(m=medium, c=b['work'])}">{t['buy_digital']}</a>
        </div>""")
    if "kindle" in b:
        k = b["kindle"]
        boxes.append(f"""        <div class="buybox">
<h3>Kindle <span class="price">{money(k['price'], 'EUR', lang)}</span></h3>
<p class="small dim">{t['kindle_sub']}</p>
<ul>
<li>{t['kindle_li']}</li>
<li>{t['amazon_price']}</li>
</ul>
<a class="btn btn-ghost" href="https://www.amazon.es/dp/{k['asin']}">{t['buy_amazon']}</a>
        </div>""")
    if "paperback" in b:
        pb = b["paperback"]
        boxes.append(f"""        <div class="buybox">
<h3>{t['paperback']} <span class="price">{money(pb['price'], pb['currency'], lang)}</span></h3>
<p class="small dim">{t['pb_amazon_sub']}</p>
<ul>
<li>{t['pb_size']}</li>
<li>{t['pb_dispatched']}</li>
</ul>
<a class="btn btn-ghost" href="https://www.amazon.es/dp/{pb['asin']}">{t['buy_amazon']}</a>
        </div>""")
        sb = shop_box(b["slug"], pb, lang, medium)
        if sb:
            boxes.append("        " + sb)
    if "paperback_in" in b:
        two = book(b["paperback_in"])
        boxes.append(f"""        <div class="buybox">
<h3>{t['paperback']} <span class="price">{money(two['paperback']['price'], 'EUR', lang)}</span></h3>
<p class="small dim">{esc(two['title'])}</p>
<ul>
<li>{t['pb_in_note']}</li>
</ul>
<a class="btn btn-ghost" href="{pre}/{two['slug']}/#buy">{t['pb_in_btn']}</a>
        </div>""")
    return "\n".join(boxes)


def page(b, lang):
    t = L[lang]
    p = parts(b["slug"], lang)
    path = "/%s/" % b["slug"]
    url = SITE + build.pre(lang) + path
    title_vars = {"title": b["title"], "author": b["author"]}
    title = t["title_tpl"].format(**title_vars)
    lede = strip_tags(p["lede"])
    if "combines" in b:
        desc = t["desc_tpl_two"].format(**title_vars)
    elif "kindle" in b:
        desc = t["desc_tpl"].format(**title_vars)
    else:
        desc = "%s %s." % (lede, t["cat_digital"])
    # structured data: the work, its digital editions, and the paperback as a Product with its ISBN
    examples = []
    if "ebook" in b:
        examples.append({"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": "%s (EPUB)" % b["title"],
                         "offers": {"@type": "Offer", "price": b["ebook"]["price"], "priceCurrency": "EUR",
                                    "availability": "https://schema.org/InStock",
                                    "url": "https://whop.com/checkout/%s" % b["ebook"]["plan"]}})
    if "kindle" in b:
        examples.append({"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": "%s (Kindle)" % b["title"],
                         "offers": {"@type": "Offer", "price": b["kindle"]["price"], "priceCurrency": "EUR",
                                    "availability": "https://schema.org/InStock",
                                    "url": "https://www.amazon.es/dp/%s" % b["kindle"]["asin"]}})
    if "paperback" in b:
        examples.append(paperback_ld(b["slug"], b["paperback"], b["title"], url, lang))
    authors = [{"@type": "Person", "name": a.strip()} for a in b["author"].split(",")]
    ld = {"@context": "https://schema.org", "@type": "Book", "@id": url + "#book", "name": b["title"],
          "url": url, "author": authors if len(authors) > 1 else authors[0],
          "translator": {"@type": "Person", "name": b["translator"]}, "inLanguage": "ca",
          "publisher": {"@type": "Organization", "name": "Pub.Cat Books"},
          "image": "%s/assets/img/%s-cover-1200.webp" % (SITE, b["img"]),
          "description": desc, "workExample": examples}
    if b.get("first_published"):
        ld["datePublished"] = b["first_published"]
    pb = b.get("paperback") or (book(b["paperback_in"])["paperback"] if "paperback_in" in b else None)
    spec = []
    if pb:
        spec.append((t["spec_pages"], str(pb["pages"]) if "paperback" in b else None))
        spec.append((t["paperback"], "229 x 152 mm"))
    fm = [x for x, ok in ((t["digital"] + " (EPUB)", "ebook" in b), ("Kindle", "kindle" in b),
                          (t["paperback"], pb is not None)) if ok]
    spec.append((t["formats"], ", ".join(fm)))
    if "paperback" in b:
        spec.append(("ISBN", pb["isbn"]))
    spec.append((t["translator"], b["translator"]))
    if b.get("first_published"):
        spec.append((t["spec_first"], b["first_published"]))
    spec.append((t["spec_language"], t["language_ca"]))
    spec_html = "\n".join("<div><dt>%s</dt><dd>%s</dd></div>" % (k, esc(v)) for k, v in spec if v)
    note = "" if lang == "ca" else '\n<p class="lang-note">%s</p>' % t["lang_note_book"]
    cover_alt = esc(t["cover_alt"].format(title=b["title"]))
    edition = ""
    if p.get("edition"):
        edition = f"""      <h2>{t['h_edition']}</h2>
{p['edition']}
"""
    sub = ""
    if b.get("subtitle_ca"):
        sub = '\n<p class="small dim">%s</p>' % esc(b["subtitle_ca"])
    body = f"""<main id="main">

  <div class="hero">
    <div class="wrap">
      <div class="hero-grid">
        <div class="hero-media">
          <a class="zoom" href="/assets/img/{b['img']}-cover-1200.webp" data-caption="{cover_alt}"><img class="cover" src="/assets/img/{b['img']}-cover-640.webp" width="{b['cover_w']}" height="640" alt="{cover_alt}" fetchpriority="high"></a>
        </div>
        <div class="hero-copy">
<p class="eyebrow">{esc(b['author'])}</p>
<h1>{esc(b['title'])}</h1>{sub}
<p class="lede">{lede}</p>{note}
<div class="btn-row"><a class="btn btn-primary" href="#buy">{t['choose_edition']}</a></div>
        </div>
      </div>
    </div>
  </div>

  <section class="spec-section">
    <div class="wrap">
<dl class="spec">
{spec_html}
</dl>
    </div>
  </section>

  <section>
    <div class="wrap narrow">
      <h2>{t['what_is']}</h2>
{p['about']}
{edition}      <h2>{t['h_translation']}</h2>
{p['translation']}
    </div>
  </section>

  <section id="buy">
    <div class="wrap">
<p class="eyebrow">{t['editions']}</p>
<h2>{t['pick_format']}</h2>
      <div class="grid" style="margin-top:2.5rem">
{buy_section(b, lang, p)}
      </div>
    </div>
  </section>
</main>
<footer class="site-foot"></footer>
<script src="/assets/js/site.js?v=20261006a" defer></script>
</body>
</html>
"""
    s = head(b, lang, title, desc, url, ld) + body
    return build.set_chrome(s, build.strings(lang), lang, path, "books", False)


def card(b, lang):
    t = L[lang]
    pre = build.pre(lang)
    medium = "books" if lang == "en" else "books-" + lang
    rows = []
    if "ebook" in b:
        rows.append(('<a href="https://whop.com/checkout/%s?%s">%s</a>' % (b["ebook"]["plan"], UTM.format(m=medium, c=b["work"]), t["cat_digital"]),
                     money(b["ebook"]["price"], "EUR", lang)))
    if "kindle" in b:
        rows.append(('<a href="https://www.amazon.es/dp/%s">%s</a>' % (b["kindle"]["asin"], t["cat_kindle"]), money(b["kindle"]["price"], "EUR", lang)))
    if "paperback" in b:
        rows.append(('<a href="https://www.amazon.es/dp/%s">%s</a>' % (b["paperback"]["asin"], t["cat_pb_amazon"]),
                     money(b["paperback"]["price"], "EUR", lang)))
        if SHOP_ON and shop_plans(b["slug"]).get("plans"):
            rows.append(('<a href="%s/%s/#paperback-shop">%s</a>' % (pre, b["slug"], t["cat_pb_shop"]), money(b["paperback"]["price"], "EUR", lang)))
    if "paperback_in" in b:
        two = book(b["paperback_in"])
        rows.append(('<a href="%s/%s/">%s</a>' % (pre, two["slug"], t["cat_pb_in"]), money(two["paperback"]["price"], "EUR", lang)))
    lis = "\n".join('<li><span class="f-name">%s</span> <span class="f-price">%s</span></li>' % r for r in rows)
    who = esc(b["author"]) + (", %s" % b["first_published"] if b.get("first_published") else "")
    alt = esc(t["cover_alt"].format(title=b["title"]))
    lede = strip_tags(parts(b["slug"], lang)["lede"])
    return f"""<article class="card book-card">
<a class="book-cover" href="{pre}/{b['slug']}/"><img src="/assets/img/{b['img']}-cover-640.webp" width="{b['cover_w']}" height="640" alt="{alt}" loading="lazy"></a>
<h3>{esc(b['title'])}</h3>
<p class="small dim">{who}</p>
<p>{esc(lede)}</p>
<ul class="formats">
{lis}
</ul>
<p class="card-actions"><a class="btn btn-primary" href="{pre}/{b['slug']}/">{t['about_book']}</a></p>
</article>"""


def catalogue(lang):
    t = L[lang]
    cards = "\n".join(card(b, lang) for b in DATA["books"])
    return f"""<!-- catalan:BEGIN (tools/catalan/gen.py) -->
  <section id="catala">
    <div class="wrap">
<p class="eyebrow">{t['cat_eyebrow']}</p>
<h2>{t['cat_h2']}</h2>
<p class="lede">{t['cat_intro']}</p>
      <div class="grid book-grid" style="margin-top:2.25rem">
{cards}
      </div>
    </div>
  </section>
<!-- catalan:END -->"""


MARK = re.compile(r"<!-- catalan:BEGIN.*?<!-- catalan:END -->", re.S)


def put_catalogue(path, lang):
    s = rd(path)
    block = catalogue(lang)
    if MARK.search(s):
        s = MARK.sub(lambda m: block, s)
    else:  # first time: after the first section of the catalogue page
        s = s.replace("  </section>\n</main>", "  </section>\n" + block + "\n</main>", 1)
        assert block in s, path
    wr(path, s)


SHOP_MARK = re.compile(r"<!-- pbshop:(\S+) -->.*?<!-- /pbshop -->", re.S)


def put_shop_boxes(path, lang):
    """English titles (al-Dayrabi, Shams volumes): the own-site paperback box sits between
    <!-- pbshop:KEY --> markers in their buy grids; empty while the shop is off."""
    s = rd(path)
    by_key = {e["key"]: e for e in DATA["english"]}

    def fill(m):
        e = by_key[m.group(1)]
        box = shop_box(e["key"], e["paperback"], lang, "book-page" if lang == "en" else "book-page-" + lang) if e.get("show_shop") else ""
        return "<!-- pbshop:%s -->%s<!-- /pbshop -->" % (m.group(1), ("\n" + box + "\n") if box else "")
    wr(path, SHOP_MARK.sub(fill, s))


def cmd_build():
    n = 0
    for b in DATA["books"]:
        for lang in LANGS:
            out = os.path.join(ROOT, build.pre(lang).strip("/"), b["slug"], "index.html")
            wr(out, page(b, lang))
            n += 1
    for lang in LANGS:
        put_catalogue(os.path.join(ROOT, build.pre(lang).strip("/"), "books", "index.html"), lang)
        if lang != "en":
            put_catalogue(os.path.join(ROOT, "tools", "i18n", "tr", lang, "books.html"), lang)
        for e in {x["slug"] for x in DATA["english"]}:
            put_shop_boxes(os.path.join(ROOT, build.pre(lang).strip("/"), e, "index.html"), lang)
            if lang != "en":
                put_shop_boxes(os.path.join(ROOT, "tools", "i18n", "tr", lang, e + ".html"), lang)
    print("build: %d book pages, catalogue in 3 languages, paperback shop %s" % (n, "ON" if SHOP_ON else "off"))


if __name__ == "__main__":
    {"content": cmd_content, "translate": cmd_translate, "build": cmd_build}[sys.argv[1]]()
