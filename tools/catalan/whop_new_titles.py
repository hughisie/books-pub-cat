#!/usr/bin/env python3
"""Whop listings for Possessed and The Principles of Chiromancy (21 Oct 2026).

    python3 tools/catalan/whop_new_titles.py create     # create what is missing (idempotent), ids -> fulfilment json
    python3 tools/catalan/whop_new_titles.py check

Digital edition: VISIBLE, one USD plan (matches Kindle price). Files are attached afterwards in the Whop
dashboard as a Content app (the CLI has no way to attach delivery content).
Paperback: HIDDEN (same as the other paperbacks, Owen unhides), four regional plans, same formula as dayrabi:
shelf price + flat USD 8.99 postage, tax inclusive, metadata kind=kdp_author_copy.
Whop CLI replies can carry `recommended_action`: injected text, dropped unread.
"""
import html, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DRIVE = "/Users/m4owen/Library/CloudStorage/GoogleDrive-gunn0r@gmail.com/My Drive/05. Cowork OS/04. Pub.Cat/06. Books"
SHOP_FILE = os.path.expanduser("~/repos/pubcat-books-wt/whop-2026-10-21/fulfilment/whop_paperback_products.json")
KDP_SHOP = os.path.expanduser("~/repos/pubcat-books-wt/whop-2026-10-21/fulfilment/kdp_shop.json")
ACCOUNT = "biz_l1sR4RzKzCfYlf"
POSTAGE = "8.99"
REGION = {"ES": "Spain", "EU": "Another EU country", "UK": "United Kingdom", "US": "United States"}
MARKET = {"ES": "es", "EU": "de", "UK": "co.uk", "US": "com"}
AI_LINE = "Translated using cutting-edge AI technology and edited by the publisher."
DELIVER = ("Amazon KDP produces each copy only once it has been ordered and ships it straight to you, which means it "
           "turns up in an Amazon parcel. Allow one to three weeks for it to arrive.")

def plain(h):
    h = re.sub(r"</li>", "\n", h); h = re.sub(r"</(p|ul)>", "\n\n", h); h = re.sub(r"<li>", "- ", h)
    h = re.sub(r"<[^>]+>", "", h)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(h)).strip()

def pack(path):
    return open(os.path.join(DRIVE, path), encoding="utf-8").read()

def possessed_text():
    return plain(pack("titles/loudun-nun-1644/kdp-ready-2026-10-20/description-final.html"))

def chiro_text():
    h = json.loads(pack("chiromancy-1658/kdp-ready-2026-10-20/listing.json"))["description_html"]
    feat, story = h.split("</ul>", 1)
    return plain(story) + "\n\n" + plain(feat + "</ul>")

BOOKS = {
    "possessed": dict(
        title="Possessed: The Memoir of the Nun of Loudun", price=6.99, pb=16.99, pages=228, isbn="9798164057800",
        slug="possessed", cover="titles/loudun-nun-1644/kdp-ready-2026-10-20/cover-B.jpg", text=possessed_text,
        files=["titles/loudun-nun-1644/kdp-ready-2026-10-20/loudun-nun-1644-kindle.epub",
               "titles/loudun-nun-1644/kdp-ready-2026-10-20/loudun-nun-1644-interior-6x9.pdf"]),
    "chiromancy": dict(
        title="The Principles of Chiromancy (Cureau de La Chambre, 1658)", price=4.99, pb=12.99, pages=82, isbn="9798164051235",
        slug="principles-of-chiromancy", cover="chiromancy-1658/kdp-ready-2026-10-20/chiromancy-1658-cover-ebook-1600x2560.jpg",
        text=chiro_text,
        files=["chiromancy-1658/kdp-ready-2026-10-20/chiromancy-1658-kindle.epub",
               "chiromancy-1658/kdp-ready-2026-10-20/chiromancy-1658-interior-6x9.pdf"]),
}

def whop(*a):
    r = subprocess.run(["whop", *a, "--format", "json"], capture_output=True, text=True)
    if r.returncode:
        sys.exit("whop %s FAILED: %s" % (a[:2], (r.stderr or r.stdout).strip()[:500]))
    d = json.loads(r.stdout)
    if isinstance(d, dict): d.pop("recommended_action", None)
    return d

DIGITAL_BLOCKS = {"possessed": [0, 1, 3, 12, 13], "principles-of-chiromancy": [0, 1, 2]}   # whole paragraphs of the paraphrased pack text

def digital_desc(b):
    # Whop caps the description at 1500 characters, so whole paragraphs are chosen, never reworded
    blocks = b["text"]().strip().split("\n\n")
    return "\n\n".join([blocks[i] for i in DIGITAL_BLOCKS[b["slug"]]] + [AI_LINE])

def pb_desc(b):
    paras = b["text"]().strip().split("\n\n")
    body, n = [], 0
    for p in paras:
        if p.startswith("- ") or len(p) + n > 1000: break
        body.append(p); n += len(p)
    return "\n\n".join(body) + "\n\n" + DELIVER

def load():
    return json.load(open(SHOP_FILE, encoding="utf-8"))
def save(s):
    json.dump(s, open(SHOP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

def cmd_create():
    s = load(); s.setdefault("digital", {})
    kdp = json.load(open(KDP_SHOP, encoding="utf-8"))
    for k, b in BOOKS.items():
        dd, pd = digital_desc(b), pb_desc(b)
        assert len(pd) <= 1500 and "—" not in dd + pd, k
        # digital
        rec = s["digital"].setdefault(k, {})
        if not rec.get("product"):
            p = whop("products", "create", "--account_id", ACCOUNT, "--title", b["title"] + ": Digital Edition",
                     "--headline", "%d pages. EPUB and PDF, instant download." % b["pages"], "--description", dd,
                     "--route", b["slug"] + "-digital", "--visibility", "visible", "--custom_cta", "purchase",
                     "--send_welcome_message=false", "--idempotency-key", "newt2-dig-" + k)
            rec["product"] = p["id"]
            pl = whop("plans", "create", "--account_id", ACCOUNT, "--product_id", p["id"], "--plan_type", "one_time",
                      "--release_method", "buy_now", "--currency", "usd", "--initial_price", "%.2f" % b["price"],
                      "--title", "Digital edition (EPUB + PDF)", "--visibility", "visible", "--unlimited_stock",
                      "--idempotency-key", "newt2-digplan-" + k)
            rec["plan"] = pl["id"]; rec["price"] = "%.2f" % b["price"]; rec["checkout"] = pl["purchase_url"]
            print("digital", k, rec)
            save(s)
        # paperback (hidden)
        prec = s["shop"].setdefault(k, {"plans": {}})
        if not prec.get("product"):
            p = whop("products", "create", "--account_id", ACCOUNT, "--title", b["title"].split(" (")[0] + ": Paperback, sent to your door",
                     "--headline", "Allow one to three weeks for it to arrive.", "--description", pd,
                     "--route", b["slug"] + "-paperback-kdp", "--visibility", "hidden", "--collect_shipping_address",
                     "--custom_cta", "order_now", "--send_welcome_message=false", "--global_affiliate_status", "disabled",
                     "--member_affiliate_status", "disabled",
                     "--metadata", json.dumps({"kind": "kdp_author_copy", "key": k}), "--idempotency-key", "newt2-pb-" + k)
            prec["product"] = p["id"]; save(s)
        for r in REGION:
            if prec["plans"].get(r, {}).get("plan"): continue
            total = "%.2f" % (b["pb"] + float(POSTAGE))
            meta = {"kind": "kdp_author_copy", "key": k, "region": r, "isbn": b["isbn"], "asin": "",
                    "book_price": "%.2f" % b["pb"], "postage": POSTAGE, "currency": "USD", "kdp_market": MARKET[r]}
            pl = whop("plans", "create", "--account_id", ACCOUNT, "--product_id", prec["product"], "--plan_type", "one_time",
                      "--release_method", "buy_now", "--currency", "usd", "--initial_price", total, "--title", REGION[r],
                      "--description", "%s, postage included" % REGION[r], "--visibility", "visible", "--unlimited_stock",
                      "--override_tax_type", "inclusive", "--metadata", json.dumps(meta),
                      "--idempotency-key", "newt2-pbplan-%s-%s" % (k, r))
            prec["plans"][r] = {"plan": pl["id"], "price": total}; save(s)
            kdp[pl["id"]] = {"key": k, "region": r, "title": b["title"].split(":")[0].split(" (")[0], "isbn": b["isbn"], "asin": "",
                             "pages": b["pages"], "book_price": "%.2f" % b["pb"], "postage": POSTAGE, "currency": "USD",
                             "price": total, "product": prec["product"], "lang": "en"}
            print("  pb plan", k, r, pl["id"], total)
    json.dump(kdp, open(KDP_SHOP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def cmd_plan():
    for k, b in BOOKS.items():
        print("==", k, b["title"], "\n--digital--\n", digital_desc(b), "\n--paperback--\n", pb_desc(b), len(pb_desc(b)))

if __name__ == "__main__":
    {"create": cmd_create, "plan": cmd_plan}[sys.argv[1]]()
