#!/usr/bin/env python3
"""Builds the Journal (blog) for books.pub.cat: /blog/ index, one page per article, feed.xml,
and the sitemap entries. Plain standard library, no dependencies.
Run from the repo root:  python3 tools/blog/build.py
Inputs: tools/blog/articles.json (details) and tools/blog/body/<slug>.html (the article text,
after the DeepSeek paraphrase). Safe to re-run: it rewrites only /blog/ and the marked
block in sitemap.xml."""
import json, html, re, os, datetime
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
cfg = json.load(open(os.path.join(ROOT, 'tools/blog/articles.json')))
SITE = cfg['site']; DATE = cfg['published']
esc = lambda s: html.escape(s, quote=True)
TAG = '<script defer data-domain="books.pub.cat" src="https://analytics.pub.cat/js/script.outbound-links.file-downloads.js"></script>\n'
CSS = '<link rel="stylesheet" href="/assets/css/main.css?v=20261007a">\n<link rel="stylesheet" href="/assets/css/blog.css?v=20261021a">'
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap">')
HEAD_NAV = '''<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="/"><b>Pub.Cat</b> Books</a>
    <nav class="site-nav" aria-label="Primary">
      <a href="/books/">Books</a>
      <a href="/shams-al-maarif/">Shams al-Maʿārif</a>
      <a href="/mujarrabat-al-dayrabi/">al-Dayrabī</a>
      <a href="/blog/" aria-current="page">Journal</a>
      <a href="/editions/">Which Edition</a>
      <a href="/about/">About us</a>
    </nav>
  </div>
</header>'''
FOOT = '''<footer class="site-foot">
  <div class="wrap">
    <div class="foot-grid">
      <div><h4>The books</h4><ul><li><a href="/books/">All books</a></li><li><a href="/shams-al-maarif/">Shams al-Maʿārif</a></li><li><a href="/mujarrabat-al-dayrabi/">Mujarrabāt al-Dayrabī</a></li><li><a href="/editions/">Compare editions</a></li><li><a href="/faq/">Questions</a></li></ul></div>
      <div><h4>Journal</h4><ul><li><a href="/blog/">All articles</a></li><li><a href="/blog/feed.xml">RSS feed</a></li></ul></div>
      <div><h4>The publisher</h4><ul><li><a href="/about/">About Pub.Cat Books</a></li><li><a href="/contact/">Contact</a></li><li><a href="https://pub.cat/">Pub.Cat</a></li></ul></div>
      <div><h4>Legal</h4><ul><li><a href="/refunds/">Delivery and refunds</a></li><li><a href="/privacy/">Privacy</a></li><li><a href="/terms/">Terms</a></li></ul></div>
    </div>
    <div class="foot-legal">
      <p>Pub.Cat Books is a Pub.Cat imprint, based in Barcelona. We publish worldwide, in English and in Catalan.</p>
      <p class="small">This site describes historical texts and the traditions around them. Nothing here is a claim that any procedure described in these books produces a physical effect.</p>
    </div>
  </div>
</footer>
<script src="/assets/js/site.js?v=20261007a" defer></script>'''

def fig(f, hero=False):
    if not f: return ''
    cls = ' class="tall"' if f.get('tall') else ''
    return (f'<figure{cls}><img src="/assets/img/blog/{f["file"]}.webp" alt="{esc(f["alt"])}" loading="lazy" decoding="async">'
            f'<figcaption>{esc(f["caption"])}</figcaption></figure>')

def amazon(b, kind):
    asin = b.get('asin_' + kind)
    return f"https://www.amazon.com/dp/{asin}" if asin else None

def whop(b, medium):
    return f"{b['whop_checkout']}?utm_source=books.pub.cat&utm_medium={medium}&utm_campaign={b['slug']}"

def buy_buttons(b, art):
    out = [f'<a class="btn btn-primary" href="{esc(whop(b, "blog"))}">Buy the digital edition</a>']
    k, p = amazon(b, 'kindle'), amazon(b, 'paperback')
    if k: out.append(f'<a class="btn btn-ghost" href="{esc(k)}" rel="nofollow sponsored">Kindle, ${b["price_kindle"]}</a>')
    if p: out.append(f'<a class="btn btn-ghost" href="{esc(p)}" rel="nofollow sponsored">Paperback, ${b["price_paperback"]}</a>')
    note = '' if (k and p) else '<p class="small dim">Kindle and paperback: coming to Amazon shortly.</p>'
    return '<div class="btn-row">' + ''.join(out) + '</div>' + note

def schema(a, url):
    b = a['book']
    book = {"@type": "Book", "@id": url + "#book", "name": b['name'], "author": {"@type": "Person", "name": b['author']},
            "contributor": {"@type": "Person", "name": b['contributor']}, "inLanguage": "en",
            "publisher": {"@type": "Organization", "name": "Pub.Cat Books"},
            "image": f"{SITE}/assets/img/blog/{b['cover']}.webp", "description": b['blurb'],
            "workExample": [{"@type": "Book", "bookFormat": "https://schema.org/Paperback", "isbn": b['isbn_paperback'], "numberOfPages": b['pages']}]}
    book["workExample"][0]["name"] = b['name'] + " (paperback)"
    book["workExample"].append({"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": b['name'] + " (digital edition)",
        "offers": {"@type": "Offer", "price": b['price_kindle'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": whop(b, "blog")}})
    if amazon(b, 'paperback'):
        book["workExample"][0]["offers"] = {"@type": "Offer", "price": b['price_paperback'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": amazon(b, 'paperback')}
    if amazon(b, 'kindle'):
        book["workExample"].append({"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": b['name'] + " (Kindle)", "offers": {"@type": "Offer", "price": b['price_kindle'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": amazon(b, 'kindle')}})
    article = {"@type": "Article", "@id": url + "#article", "headline": a['title'], "description": a['description'],
               "image": f"{SITE}/assets/img/blog/{a['og']}.jpg", "datePublished": DATE, "dateModified": DATE,
               "inLanguage": "en-GB", "author": {"@type": "Organization", "name": "Pub.Cat Books", "url": SITE + "/about/"},
               "publisher": {"@type": "Organization", "name": "Pub.Cat Books", "url": SITE + "/"},
               "mainEntityOfPage": url, "about": {"@id": url + "#book"}}
    crumbs = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Pub.Cat Books", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Journal", "item": SITE + "/blog/"},
        {"@type": "ListItem", "position": 3, "name": a['title'], "item": url}]}
    return json.dumps({"@context": "https://schema.org", "@graph": [article, book, crumbs]}, indent=1, ensure_ascii=False)

def page(title, desc, canon, og_img, og_type, body, extra_head=''):
    return f'''<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Pub.Cat Books">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{canon}">
<meta property="og:image" content="{SITE}/assets/img/blog/{og_img}.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="alternate" type="application/rss+xml" title="Pub.Cat Books Journal" href="{SITE}/blog/feed.xml">
{FONTS}
{CSS}
{extra_head}{TAG}</head>
<body>
{HEAD_NAV}
<main id="main">
{body}
</main>
{FOOT}
</body>
</html>
'''

all_arts = cfg['articles']
arts = [a for a in all_arts if a['book'].get('live')]   # an article goes public only when its book is live on Amazon
by = {a['slug']: a for a in arts}
for a in all_arts:
    if a not in arts:
        import shutil; shutil.rmtree(os.path.join(ROOT, 'blog', a['slug']), ignore_errors=True)
for a in arts:
    url = f"{SITE}/blog/{a['slug']}/"
    text = open(os.path.join(ROOT, 'tools/blog/body', a['slug'] + '.html')).read()
    for k, f in a['figures'].items():
        text = text.replace(f'<p>@@{k}@@</p>', fig(f)).replace(f'@@{k}@@', fig(f))
    assert '@@' not in text, 'unreplaced figure marker in ' + a['slug']
    b = a['book']
    related = ''.join(f'<li><a href="/blog/{r}/">{esc(by[r]["title"])}</a></li>' for r in a['related'] if r in by)
    body = f'''  <section class="post-hero"><div class="wrap narrow" style="max-width:42rem">
    <p class="eyebrow">{esc(a['eyebrow'])}</p>
    <h1>{esc(a['h1'])}</h1>
    <p class="post-meta">By Pub.Cat Books · <time datetime="{DATE}">21st October 2026</time> · {max(1, round(len(re.sub('<[^>]+>', '', text).split()) / 220))} minute read</p>
    <p class="lede">{esc(a['description'])}</p>
  </div>
  <div class="wrap" style="max-width:42rem"><figure class="post-hero-img{' tall' if a['hero'].get('tall') else ''}" style="margin:2rem 0 0"><img src="/assets/img/blog/{a['hero']['file']}.webp" alt="{esc(a['hero']['alt'])}" fetchpriority="high"><figcaption style="font-family:var(--sans);font-size:.82rem;color:var(--parchment-dim);padding:.6rem 0;text-align:center">{esc(a['hero']['caption'])}</figcaption></figure></div></section>
  <section class="post-body"><div class="wrap">
{text}
  <p class="post-credits">{esc(a['credits'])}</p>
  </div></section>
  <section class="post-cta"><div class="wrap">
    <div class="cta-box">
      <a href="{b['page']}"><img src="/assets/img/blog/{b['cover']}.webp" width="120" height="192" alt="{esc(b['cover_alt'])}" loading="lazy"></a>
      <div class="cta-copy">
        <p class="eyebrow">The book</p>
        <h2>{esc(b['name'])}</h2>
        <p class="small dim">{esc(b['author'])}. {esc(b['contributor_role'].capitalize())}: {esc(b['contributor'])}. {b['pages']} pages in paperback.</p>
        <p>{esc(b['blurb'])}</p>
        {buy_buttons(b, a)}
        <p class="small dim"><a href="{b['page']}">See all our books</a></p>
      </div>
    </div>
  </div></section>
  <section class="more-reading"><div class="wrap"><p class="eyebrow">Keep reading</p><ul class="backlog">{related}<li><a href="/blog/">All Journal articles</a></li></ul></div></section>'''
    d = os.path.join(ROOT, 'blog', a['slug']); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'index.html'), 'w').write(page(a['title'] + ' | Pub.Cat Books', a['description'], url, a['og'], 'article', body,
        '<script type="application/ld+json">\n' + schema(a, url) + '\n</script>\n'))

cards = ''.join(f'''<li class="post-card"><a href="/blog/{a['slug']}/"><img src="/assets/img/blog/{a['hero']['file']}.webp" alt="{esc(a['hero']['alt'])}" loading="lazy"></a><div><p class="eyebrow">{esc(a['eyebrow'])}</p><h2><a href="/blog/{a['slug']}/">{esc(a['h1'])}</a></h2><p>{esc(a['description'])}</p></div></li>''' for a in arts)
idx = f'''  <section class="post-hero"><div class="wrap" style="max-width:42rem"><p class="eyebrow">The Journal</p><h1>Stories behind the books</h1>
  <p class="lede">The people, places and arguments inside the old texts we publish, with the pictures and the quotations to match.</p>
  <ul class="post-list">{cards}</ul></div></section>'''
idx_ld = json.dumps({"@context": "https://schema.org", "@type": "Blog", "name": "Pub.Cat Books Journal", "url": SITE + "/blog/",
    "publisher": {"@type": "Organization", "name": "Pub.Cat Books"},
    "blogPost": [{"@type": "BlogPosting", "headline": a['title'], "url": f"{SITE}/blog/{a['slug']}/", "datePublished": DATE} for a in arts]}, indent=1)
os.makedirs(os.path.join(ROOT, 'blog'), exist_ok=True)
open(os.path.join(ROOT, 'blog/index.html'), 'w').write(page('The Journal | Pub.Cat Books', 'Articles on the history behind the Pub.Cat Books titles: the Loudun possessions and more.',
    SITE + '/blog/', arts[0]['og'], 'website', idx, '<script type="application/ld+json">\n' + idx_ld + '\n</script>\n'))

rfc = lambda: datetime.datetime.strptime(DATE, '%Y-%m-%d').strftime('%a, %d %b %Y 08:00:00 +0000')
items = ''.join(f'<item><title>{esc(a["title"])}</title><link>{SITE}/blog/{a["slug"]}/</link><guid isPermaLink="true">{SITE}/blog/{a["slug"]}/</guid><pubDate>{rfc()}</pubDate><description>{esc(a["description"])}</description></item>' for a in arts)
open(os.path.join(ROOT, 'blog/feed.xml'), 'w').write(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>Pub.Cat Books Journal</title><link>{SITE}/blog/</link><description>Stories behind the books from Pub.Cat Books.</description><language>en-GB</language>{items}</channel></rss>\n')


# ---------- dedicated book pages (/possessed/, /chiromancy/) and their cards on /books/ ----------
BOOKMETA = {
 'possessed': dict(eyebrow='Jeanne des Anges', lede='Complete English translation, with an introduction, timeline and notes.',
    meta='Possessed: the complete English translation of the autobiography of Jeanne des Anges, prioress at the heart of the Loudun possessions. Digital edition, Kindle and paperback.',
    og='og-possessed-blog', year='Written in the 1640s; printed in French in 1886',
    role='Translator', role_note='Translated from the 1886 French printing of the Tours manuscript.', paper='228 pages, 6 x 9 in (152 x 229 mm)',
    short_card='The complete autobiography of the prioress at the centre of the Loudun possessions, complete in English: her whole account, her later letters, an introduction, a timeline, notes and a glossary.'),
 'chiromancy': dict(eyebrow='Marin Cureau de La Chambre', lede='The 1658 English text, modernised, with a foreword, notes and a glossary.',
    meta='The Principles of Chiromancy by Marin Cureau de La Chambre: the 1658 English palmistry text, modernised, with a foreword, notes and a glossary. Digital edition now; Kindle and paperback coming to Amazon.',
    og='og-chiromancy-blog', year='Paris 1653; English translation 1658',
    role='Editor', role_note='Modernised from the anonymous 1658 English translation.', paper='82 pages, 6 x 9 in (152 x 229 mm)',
    short_card='A court physician asks whether palmistry has any basis in medicine. The 1658 English translation, modernised, with a foreword, notes on every Article and a glossary.'),
}

def book_page(a):
    b = a['book']; m = BOOKMETA[b['slug']]; slug = b['slug']; url = f"{SITE}/{slug}/"
    body_html = open(os.path.join(ROOT, 'tools/blog/book-body', slug + '.html')).read()
    k, pb = amazon(b, 'kindle'), amazon(b, 'paperback')
    wurl = whop(b, 'book-page')
    kbox = (f'<a class="btn btn-ghost" href="{esc(k)}" rel="nofollow sponsored">Buy on Amazon</a>' if k else '<p class="small dim">Coming to Amazon shortly.</p>')
    pbox = (f'<a class="btn btn-ghost" href="{esc(pb)}" rel="nofollow sponsored">Buy on Amazon</a>' if pb else '<p class="small dim">Coming to Amazon shortly.</p>')
    article_link = (f'<p class="small"><a href="/blog/{a["slug"]}/">Read the story behind the book: {esc(a["h1"])}</a></p>' if a in arts else '')
    ld = {"@context": "https://schema.org", "@type": "Book", "@id": url + "#book", "name": b['name'], "url": url,
          "author": {"@type": "Person", "name": b['author']}, "contributor": {"@type": "Person", "name": b['contributor']},
          "inLanguage": "en", "publisher": {"@type": "Organization", "name": "Pub.Cat Books"},
          "image": f"{SITE}/assets/img/{slug}-cover-1200.webp", "description": m['meta'],
          "workExample": [
            {"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": b['name'] + " (digital edition)",
             "offers": {"@type": "Offer", "price": b['price_kindle'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": wurl}},
            {"@type": ["Book", "Product"], "bookFormat": "https://schema.org/Paperback", "name": b['name'] + " (paperback)",
             "isbn": b['isbn_paperback'], "gtin13": b['isbn_paperback'], "numberOfPages": b['pages']}]}
    if k:
        ld["workExample"].append({"@type": "Book", "bookFormat": "https://schema.org/EBook", "name": b['name'] + " (Kindle)",
            "offers": {"@type": "Offer", "price": b['price_kindle'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": k}})
    if pb:
        ld["workExample"][1]["sameAs"] = pb
        ld["workExample"][1]["offers"] = {"@type": "Offer", "price": b['price_paperback'], "priceCurrency": "USD", "availability": "https://schema.org/InStock", "url": pb}
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Pub.Cat Books", "item": SITE + "/"},
        {"@type": "ListItem", "position": 2, "name": "Books", "item": SITE + "/books/"},
        {"@type": "ListItem", "position": 3, "name": b['name'], "item": url}]}
    body = f"""  <div class="hero">
    <div class="wrap">
      <div class="hero-grid">
        <div class="hero-media">
          <a class="zoom" href="/assets/img/{slug}-cover-1200.webp" data-caption="Front cover of {esc(b['name'])}"><img class="cover" src="/assets/img/{slug}-cover-640.webp" width="400" height="640" alt="{esc(b['cover_alt'])}" fetchpriority="high"></a>
        </div>
        <div class="hero-copy">
<p class="eyebrow">{esc(m['eyebrow'])}</p>
<h1>{esc(b['name'])}</h1>
<p class="lede">{esc(m['lede'])}</p>
<div class="btn-row"><a class="btn btn-primary" href="#buy">Choose an edition</a></div>
        </div>
      </div>
    </div>
  </div>

  <section class="spec-section">
    <div class="wrap">
<dl class="spec">
<div><dt>Pages</dt><dd>{b['pages']}</dd></div>
<div><dt>Paperback</dt><dd>6 x 9 in (152 x 229 mm)</dd></div>
<div><dt>Formats</dt><dd>Digital (EPUB and PDF), Kindle, Paperback</dd></div>
<div><dt>ISBN (paperback)</dt><dd>{b['isbn_paperback']}</dd></div>
<div><dt>{m['role']}</dt><dd>{esc(b['contributor'])}</dd></div>
<div><dt>Original</dt><dd>{esc(m['year'])}</dd></div>
<div><dt>Language</dt><dd>English</dd></div>
</dl>
    </div>
  </section>

  <section>
    <div class="wrap narrow">
      <h2>What this book is</h2>
{body_html}
      <h2>How it was made</h2>
<p>{esc(m['role_note'])} {esc(b['contributor'])} is the AI {m['role'].lower()} of Pub.Cat Books: this edition was prepared with the assistance of AI and edited by the publisher.</p>
{article_link}
    </div>
  </section>

  <section id="buy">
    <div class="wrap">
<p class="eyebrow">Editions</p>
<h2>Pick a format</h2>
      <div class="grid" style="margin-top:2.5rem">
        <div class="buybox">
<h3>Digital <span class="price">${b['price_kindle']}</span></h3>
<p class="small dim">EPUB and PDF, instant download after payment</p>
<ul>
<li>Free of DRM, so it opens on any e-reader, phone or computer</li>
<li>Bought from us directly</li>
</ul>
<a class="btn btn-primary" href="{esc(wurl)}">Buy the digital edition</a>
        </div>
        <div class="buybox">
<h3>Kindle <span class="price">${b['price_kindle']}</span></h3>
<p class="small dim">Sold by Amazon</p>
<ul>
<li>Sent to your Kindle device or the Kindle app</li>
<li>Pricing controlled by Amazon</li>
</ul>
{kbox}
        </div>
        <div class="buybox">
<h3>Paperback <span class="price">${b['price_paperback']}</span></h3>
<p class="small dim">Printed to order by Amazon</p>
<ul>
<li>{m['paper']}, black and white</li>
<li>Dispatched by Amazon</li>
</ul>
{pbox}
        </div>
      </div>
    </div>
  </section>"""
    html_ = page(f"{b['name']} | Pub.Cat Books", m['meta'], url, m['og'], 'book', body,
        '<script type="application/ld+json">\n' + json.dumps(ld, indent=1, ensure_ascii=False) + '\n</script>\n<script type="application/ld+json">\n' + json.dumps(crumbs, indent=1, ensure_ascii=False) + '\n</script>\n')
    d = os.path.join(ROOT, slug); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'index.html'), 'w').write(html_)

def book_card(a):
    b = a['book']; m = BOOKMETA[b['slug']]; k, pb = amazon(b, 'kindle'), amazon(b, 'paperback')
    li = [f'<li><span class="f-name"><a href="{esc(whop(b, "books"))}">Digital edition, EPUB and PDF</a></span> <span class="f-price">${b["price_kindle"]}</span></li>']
    li.append(f'<li><span class="f-name"><a href="{esc(k)}" rel="nofollow sponsored">Kindle</a></span> <span class="f-price">${b["price_kindle"]}</span></li>' if k else '<li><span class="f-name">Kindle: coming to Amazon shortly</span></li>')
    li.append(f'<li><span class="f-name"><a href="{esc(pb)}" rel="nofollow sponsored">Amazon paperback</a></span> <span class="f-price">${b["price_paperback"]}</span></li>' if pb else '<li><span class="f-name">Paperback: coming to Amazon shortly</span></li>')
    return f"""<article class="card book-card">
<a class="book-cover" href="{b['page']}"><img src="/assets/img/{b['slug']}-cover-640.webp" width="400" height="640" alt="{esc(b['cover_alt'])}" loading="lazy"></a>
<h3>{esc(b['name'])}</h3>
<p class="small dim">{esc(b['author'])}</p>
<p>{esc(m['short_card'])}</p>
<ul class="formats">
{chr(10).join(li)}
</ul>
<p class="card-actions"><a class="btn btn-primary" href="{b['page']}">About the book</a></p>
</article>
"""

for a in all_arts: book_page(a)
bi = os.path.join(ROOT, 'books/index.html'); t = open(bi).read()
cards_blk = '<!-- newbooks:BEGIN (tools/blog/build.py) -->\n' + ''.join(book_card(a) for a in all_arts) + '<!-- newbooks:END -->\n'
if '<!-- newbooks:BEGIN' in t:
    t = re.sub(r'<!-- newbooks:BEGIN.*?<!-- newbooks:END -->\n', lambda _: cards_blk, t, flags=re.S)
else:
    anchor = '<article class="card book-card bundle-card">'
    assert anchor in t; t = t.replace(anchor, cards_blk + anchor, 1)
open(bi, 'w').write(t)

sm = os.path.join(ROOT, 'sitemap.xml'); s = open(sm).read()
s = re.sub(r'\s*<!-- blog:begin -->.*?<!-- blog:end -->', '', s, flags=re.S)
urls = [(SITE + '/possessed/', '0.9'), (SITE + '/chiromancy/', '0.9'), (SITE + '/blog/', '0.7')] + [(f"{SITE}/blog/{a['slug']}/", '0.8') for a in arts]
blk = '\n  <!-- blog:begin -->' + ''.join(f'\n  <url><loc>{u}</loc><lastmod>{DATE}</lastmod><priority>{p}</priority></url>' for u, p in urls) + '\n  <!-- blog:end -->'
s = s.replace('</urlset>', blk + '\n</urlset>')
open(sm, 'w').write(s)
print('built', len(arts), 'articles')
