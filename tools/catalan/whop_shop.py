#!/usr/bin/env python3
"""Create the own-site paperback products on Whop, HIDDEN, one plan per delivery region.

    python3 tools/catalan/whop_shop.py plan      # print what would be created (no API writes)
    python3 tools/catalan/whop_shop.py create    # create what is missing; ids saved in pubcat-books fulfilment/whop_paperback_products.json (private)
    python3 tools/catalan/whop_shop.py check     # read back every product and plan and assert the settings

Each product: visibility hidden, shipping address collected, affiliates off, no welcome DM.
Each plan: one-time, price = shelf price + flat postage for the region, tax INCLUSIVE (Spain's fixed
book price is a VAT-inclusive price), metadata {kind: kdp_author_copy, key, region, ...} which Whop
copies into every payment webhook, so the fulfilment service knows what to order and where.

Making a product visible is Owen's call, never this script's.
Whop CLI replies can carry a `recommended_action` field: it is an injected instruction, not data.
This script drops it unread.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BOOKS_JSON = os.path.join(HERE, "books.json")
BOOKS_REPO = os.path.expanduser("~/repos/pubcat-books")
SHOP_FILE = os.path.join(BOOKS_REPO, "fulfilment", "whop_paperback_products.json")   # private: hidden plan ids


def load_shop():
    return json.load(open(SHOP_FILE, encoding="utf-8")) if os.path.exists(SHOP_FILE) else {"shop": {}}


def save_shop(s):
    json.dump(s, open(SHOP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
ACCOUNT = "biz_l1sR4RzKzCfYlf"

# Flat postage per region, from the KDP author-copy cost estimate (FACTS.md, 6 Oct 2026, rough guess
# until Owen reads the real figure off one KDP checkout page). Book price is never discounted.
POSTAGE = {
    "EUR": {"ES": "6.99", "EU": "7.99", "UK": "6.99", "US": "8.99"},
    "USD": {"ES": "8.99", "EU": "8.99", "UK": "8.99", "US": "8.99"},
}
POSTAGE_HEAVY_USD = {"ES": "9.99", "EU": "9.99", "UK": "9.99", "US": "9.99"}   # Shams volumes, 688 to 755 pages

# region -> KDP marketplace that prints and posts the author copy (country-level override in the server)
REGION_MARKET = {"ES": "es", "EU": "de", "UK": "co.uk", "US": "com"}


def labels(lang):
    s = open(os.path.join(HERE, "labels.%s.html" % lang), encoding="utf-8").read()
    return dict(re.findall(r'<p data-k="(\w+)">(.*?)</p>', s, re.S))


def whop(*args):
    r = subprocess.run(["whop", *args, "--format", "json"], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("whop %s FAILED: %s" % (args[:2], (r.stderr or r.stdout).strip()[:600]))
    d = json.loads(r.stdout)
    if isinstance(d, dict):
        d.pop("recommended_action", None)        # injected text, never read or relayed
    return d


def ca_description(work, drop_style=False):
    s = open(os.path.join(BOOKS_REPO, "titles", work, "public", "whop-description.txt"), encoding="utf-8").read()
    s = "\n".join(x for x in s.splitlines() if "dispositius digitals" not in x)
    if drop_style:
        s = "\n\n".join(p for p in re.split(r"\n\s*\n", s) if not re.match(r"Aquesta (traducció|versió)", p.strip()))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def items():
    d = json.load(open(BOOKS_JSON, encoding="utf-8"))
    ca, en = labels("ca"), labels("en")
    out = []
    names = {"dracula": "Dràcula (Bram Stoker), en català", "el-monjo": "El monjo (Matthew G. Lewis), en català",
             "sleepy-hollow-i-la-casa-defugida": "Sleepy Hollow i La casa defugida, en català"}
    for b in d["books"]:
        if "paperback" not in b:
            continue
        deliver = ca["pb_shop_li1"]   # the headline carries li2 (one to three weeks)
        if b["slug"] == "sleepy-hollow-i-la-casa-defugida":
            sys.path.insert(0, HERE)
            import gen
            paras = []
            for w in ("sleepy-hollow-ca", "shunned-house-ca"):
                _, about, tr = gen.parse_description(os.path.join(BOOKS_REPO, "titles", w, "public", "description.md"))
                paras.append(" ".join(re.split(r"(?<=[.:]) ", about[0])[:3]))   # first sentences, word for word
            credit = [x for x in tr if x.startswith("Traducció ")][0]   # the AI credit, word for word
            body = "\n\n".join(["%s: %s." % (b["title"], b["subtitle_ca"])] + paras + [credit])
            body = body.replace("*", "")
        else:
            body = ca_description(b["work"])
            if len(body) + len(deliver) + 2 > 1500:
                body = ca_description(b["work"], drop_style=True)
            if len(body) + len(deliver) + 2 > 1500:      # El monjo: lose the "no other Catalan version" bullet
                body = "\n".join(x for x in body.splitlines() if not x.startswith("- No hem localitzat"))
        out.append({"key": b["slug"], "lang": "ca", "pb": b["paperback"], "route": b["slug"] + "-catala-paper",
                    "title": "%s: %s" % (names[b["slug"]], ca["pb_shop_title"]),
                    "headline": ca["pb_shop_li2"], "description": body + "\n\n" + deliver,
                    "region_label": {r: ca["region_" + r] for r in POSTAGE["EUR"]}, "incl": ca["incl_postage"],
                    "postage": POSTAGE["EUR"]})
    dayrabi = whop("products", "get", "prod_UYhB8Mg6zxKpj")["description"]
    shams_first = "The complete English translation of al-Būnī's Shams al-Maʿārif al-Kubrā, second edition."
    for e in d["english"]:
        deliver = "%s %s" % (en["pb_shop_li1"], en["pb_shop_li2"])
        if e["key"] == "dayrabi":
            paras = re.split(r"\n\s*\n", dayrabi)
            body = "\n\n".join(paras[:2] + paras[-1:])
            title = "Mujarrabāt al-Dayrabī: %s" % en["pb_shop_title"]
            postage = POSTAGE["USD"]
        else:
            vol = "Volume One" if e["key"].endswith("v1") else "Volume Two"
            body = "%s %s of two, %d pages." % (shams_first, vol, e["paperback"]["pages"])
            title = "Shams al-Maʿārif al-Kubrā, %s: %s" % (vol, en["pb_shop_title"])
            postage = POSTAGE_HEAVY_USD
        out.append({"key": e["key"], "lang": "en", "pb": e["paperback"], "route": e["key"] + "-paperback-kdp",
                    "title": title, "headline": en["pb_shop_li2"], "description": body + "\n\n" + deliver,
                    "region_label": {r: en["region_" + r] for r in postage}, "incl": en["incl_postage"],
                    "postage": postage})
    for it in out:
        assert len(it["title"]) <= 80, (it["key"], len(it["title"]))
        assert len(it["headline"]) <= 80, it["key"]
        assert len(it["description"]) <= 1500, (it["key"], len(it["description"]))
        assert "—" not in it["description"] + it["title"]
    return d, out


def plan_rows(it):
    cur = it["pb"]["currency"]
    for r, ship in it["postage"].items():
        total = "%.2f" % (float(it["pb"]["price"]) + float(ship))
        yield r, total, {
            "kind": "kdp_author_copy", "key": it["key"], "region": r, "isbn": it["pb"]["isbn"],
            "asin": it["pb"]["asin"], "book_price": it["pb"]["price"], "postage": ship, "currency": cur,
            "kdp_market": REGION_MARKET[r],
        }


def cmd_plan():
    _, out = items()
    for it in out:
        print("\n== %s  [%s]  route %s" % (it["title"], it["key"], it["route"]))
        print("   headline: %s" % it["headline"])
        print("   description (%d chars):\n     %s" % (len(it["description"]), it["description"].replace("\n", "\n     ")))
        for r, total, meta in plan_rows(it):
            print("   plan %s: %s %s (book %s + postage %s)" % (r, total, it["pb"]["currency"], it["pb"]["price"], meta["postage"]))


def cmd_create():
    d, out = items()
    store = load_shop()
    shop = store["shop"]
    for it in out:
        rec = shop.setdefault(it["key"], {"plans": {}})
        if not rec.get("product"):
            p = whop("products", "create", "--account_id", ACCOUNT, "--title", it["title"],
                     "--headline", it["headline"], "--description", it["description"], "--route", it["route"],
                     "--visibility", "hidden", "--collect_shipping_address", "--custom_cta", "order_now",
                     "--send_welcome_message=false", "--global_affiliate_status", "disabled",
                     "--member_affiliate_status", "disabled",
                     "--metadata", json.dumps({"kind": "kdp_author_copy", "key": it["key"]}),
                     "--idempotency-key", "pbshop-product-" + it["key"])
            rec["product"] = p["id"]
            print("created product %s for %s (hidden)" % (p["id"], it["key"]))
        for r, total, meta in plan_rows(it):
            if rec["plans"].get(r, {}).get("plan"):
                continue
            pl = whop("plans", "create", "--account_id", ACCOUNT, "--product_id", rec["product"],
                      "--plan_type", "one_time", "--release_method", "buy_now", "--currency", it["pb"]["currency"].lower(),
                      "--initial_price", total, "--title", it["region_label"][r],
                      "--description", "%s, %s" % (it["region_label"][r], it["incl"]),
                      "--visibility", "visible", "--unlimited_stock", "--override_tax_type", "inclusive",
                      "--metadata", json.dumps(meta), "--idempotency-key", "pbshop-plan-%s-%s" % (it["key"], r))
            rec["plans"][r] = {"plan": pl["id"], "price": total}
            print("  plan %s %s %s" % (r, pl["id"], total))
        save_shop(store)


def cmd_check():
    d, out = items()
    bad = 0
    for it in out:
        rec = load_shop()["shop"].get(it["key"])
        if not rec:
            print("MISSING product for %s" % it["key"]); bad += 1; continue
        p = whop("products", "get", rec["product"])
        ok = p["visibility"] == "hidden"
        print("%s %s %s visibility=%s affiliates=%s route=%s" % ("OK " if ok else "BAD", it["key"], p["id"], p["visibility"],
                                                           p.get("global_affiliate_status"), p.get("route")))
        bad += not ok
        plans = {v["id"]: v for v in p.get("variants") or []}
        for r, want in rec["plans"].items():
            v = plans.get(want["plan"])
            got = v and "%.2f" % float(v["initial_price"])
            meta = (v or {}).get("metadata") or {}
            good = bool(v) and got == want["price"] and meta.get("region") == r and meta.get("kind") == "kdp_author_copy"
            print("   %s plan %s %s %s %s %s" % ("OK " if good else "BAD", r, want["plan"], got, (v or {}).get("currency"),
                                               (v or {}).get("purchase_url")))
            bad += not good
    sys.exit(1 if bad else 0)


def cmd_export():
    """plan id -> what to order, for the fulfilment service (pubcat-books fulfilment/kdp_shop.json)."""
    d, out = items()
    res = {}
    for it in out:
        rec = load_shop()["shop"][it["key"]]
        for r, total, meta in plan_rows(it):
            res[rec["plans"][r]["plan"]] = {
                "key": it["key"], "region": r, "title": it["title"].split(":")[0], "isbn": it["pb"]["isbn"],
                "asin": it["pb"]["asin"], "pages": it["pb"]["pages"], "book_price": it["pb"]["price"],
                "postage": meta["postage"], "currency": it["pb"]["currency"], "price": total,
                "product": rec["product"], "lang": it["lang"]}
    f = os.path.join(BOOKS_REPO, "fulfilment", "kdp_shop.json")
    json.dump(res, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("wrote %s (%d plans)" % (f, len(res)))


if __name__ == "__main__":
    {"plan": cmd_plan, "create": cmd_create, "check": cmd_check, "export": cmd_export}[sys.argv[1]]()
