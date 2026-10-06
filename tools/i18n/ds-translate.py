#!/usr/bin/env python3
"""Translate an English HTML fragment into Spanish or Catalan with DeepSeek
(or, with --src ca, a Catalan fragment into English or Spanish).

Runs on london (the key lives in /opt/pubcat/secrets/.env):

    set -a; . /opt/pubcat/secrets/.env; set +a
    python3 ds-translate.py --lang es --in page.html --out page.es.html

The text on books.pub.cat in Spanish and Catalan must be DeepSeek's translation, never
Claude's (Owen's publishing rule). This script only translates; tools/i18n/build.py
assembles the pages.

Guards, per chunk; a chunk that fails is retried, and after the last retry the whole
run fails loudly and writes nothing:
  - identical tag sequence, and identical href, src, id and class values in order
  - the same numbers (thousand separators ignored)
  - every transliterated Arabic word (any word with a macron, dot-under or ayn) survives
  - no em dash; an en dash only between digits
  - the answer finished normally (no truncation) and carries no code fence
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

API = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
CHUNK = 7000

LANGS = {
    "en": "British English, in a neutral, clear register suitable for a small literary publisher",
    "es": "Spanish as written in Spain, in a neutral, clear register suitable for a "
          "small literary publisher (address the reader as 'tú' where the English "
          "speaks to the reader directly)",
    "ca": "Catalan (central standard), following the 2016 orthography of the Institut "
          "d'Estudis Catalans (for example 'dona', 'os', 'pel' without the old diacritic "
          "accents), in a neutral, clear register suitable for a small literary publisher",
}

SYSTEM = """You are a professional translator for Pub.Cat Books, a small publisher in Barcelona.
Translate the HTML you are given from British English into {lang}.

ABSOLUTE RULES, breaking any of these fails the job:
- Translate the visible text, and the values of the alt, aria-label, title, placeholder,
  data-caption and data-download-label attributes. Translate nothing else.
- Keep every tag, every attribute and the order of elements exactly as given. Never
  change an href, src, id, class, style, width, height or any URL or email address.
- Keep exactly as written, with every diacritic: all Arabic transliterations (any word
  containing ā ī ū ḥ ṣ ṭ ḍ ẓ ʿ or ʾ, for example Shams al-Maʿārif al-Kubrā, Mujarrabāt
  al-Dayrabī, al-Būnī, al-Sanūsī, Shāfiʿī, awfāq, ʿilm al-ḥurūf). Write them with
  exactly the same letters and diacritics even where the grammar of the target language
  would adapt them; only the capital at the start of a sentence may change. The same goes
  for book titles, personal names, and the
  names Pub.Cat, Pub.Cat Books, Kindle, Amazon, Whop, PDF, EPUB, DRM.
- Keep every number. Prices stay exactly as written, with the $ sign before the number
  (for example $24.99). Dates such as 1347 AH may use the local abbreviation for AH.
- These books are English translations of Arabic texts and are published in English.
  Whenever the source says the book is in English, the translation must keep that
  meaning plainly.
- NEVER use an em dash. Use a comma, a colon, brackets or a full stop instead.
- Do not add, drop or summarise sentences, links or list items.
- Return ONLY the translated HTML. No preamble, no explanation, no code fences."""

# Catalan-source pages (the Catalan classics): the Catalan wording is the original, already
# paraphrased by Gemini under the publishing rule; DeepSeek translates it into English or Spanish.
SYSTEM_CA = """You are a professional translator for Pub.Cat Books, a small publisher in Barcelona.
Translate the HTML you are given from Catalan into {lang}.

ABSOLUTE RULES, breaking any of these fails the job:
- Translate the visible text, and the values of the alt, aria-label, title, placeholder,
  data-caption and data-download-label attributes. Translate nothing else.
- Keep every tag, every attribute and the order of elements exactly as given. Never
  change an href, src, id, class, style, width, height or any URL or email address.
- These books are Catalan translations of classic novels and stories, published in Catalan.
  Keep the Catalan titles of these editions exactly as written (for example Dràcula, El monjo,
  La llegenda de Sleepy Hollow, La casa defugida); you may add nothing to them. Keep every
  personal name and place name as written, and the names Pub.Cat, Pub.Cat Books, Marçal
  Fontanet, Kindle, Amazon, Whop, EPUB, PDF.
- Keep every number. Prices stay exactly as written, with the € sign where it appears.
- Where the text explains a Catalan form of address (vostè, vós), keep the Catalan word in italics
  or as written and explain it as the source does.
- NEVER use an em dash. Use a comma, a colon, brackets or a full stop instead.
- Do not add, drop or summarise sentences, links or list items.
- Return ONLY the translated HTML. No preamble, no explanation, no code fences."""

SOURCE = {"en": SYSTEM, "ca": SYSTEM_CA}

AR = "āīūḥṣṭḍẓʿʾĀĪŪḤṢṬḌẒ"
AR_WORD = re.compile(r"[\w%sʿʾ'-]*[%s][\w%sʿʾ-]*" % (AR, AR, AR))


def call(text, lang, temperature, src="en"):
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        sys.exit("DEEPSEEK_API_KEY not set. Source /opt/pubcat/secrets/.env first.")
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SOURCE[src].format(lang=LANGS[lang])},
                     {"role": "user", "content": text}],
        "temperature": temperature,
        "max_tokens": 8000,
    }
    req = urllib.request.Request(
        API, data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (Macintosh) Chrome/126"})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    ch = d["choices"][0]
    if ch.get("finish_reason") not in (None, "stop"):
        raise ValueError("stopped early: %s" % ch.get("finish_reason"))
    return ch["message"]["content"].strip()


def tags(s):
    return re.findall(r"</?([a-zA-Z0-9]+)", s)


TRANSLATABLE = {"alt", "aria-label", "title", "placeholder", "data-caption", "data-download-label"}


def fixed_attrs(s):
    """Every attribute except the translatable ones, in document order."""
    out = []
    for tag in re.findall(r"<[a-zA-Z][^>]*>", s):
        for name, val in re.findall(r'\s([a-zA-Z-]+)(?:="([^"]*)")?', tag):
            if name not in TRANSLATABLE:
                out.append((name, val))
    return out


def numbers(s):
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"(?<=\d)[.,   ](?=\d{3}\b)", "", s)
    return sorted(re.findall(r"\d+", s))


def ar_words(s):
    s = re.sub(r"<[^>]+>", " ", s)
    out = set()
    for w in AR_WORD.findall(s):
        w = re.sub(r"'s$", "", w).strip("-'")
        if w:
            out.add(w)
    return out


def guard(src, out):
    fails = []
    if tags(src) != tags(out):
        fails.append("tag sequence changed")
    a, b = fixed_attrs(src), fixed_attrs(out)
    if a != b:
        diff = [x for x in a if x not in b][:3]
        fails.append("attributes changed: %s" % diff)
    if numbers(src) != numbers(out):
        a, b = numbers(src), numbers(out)
        fails.append("numbers changed: lost %s, gained %s"
                     % (sorted(set(a) - set(b)), sorted(set(b) - set(a))))
    low = out.lower()
    missing = [w for w in ar_words(src) if w.lower() not in low]
    if missing:
        fails.append("transliterations lost: %s" % missing[:8])
    if "—" in out:
        fails.append("em dash")
    if re.search(r"(?<!\d)–|–(?!\d)", re.sub(r"<[^>]+>", " ", out)):
        fails.append("en dash outside a number range")
    if "```" in out:
        fails.append("code fence")
    return fails


def chunks(s):
    parts = re.split(r'(?=\n\s*<(?:section|div class="hero|header|footer|article)\b)', s)
    out, cur = [], ""
    for p in parts:
        if cur and len(cur) + len(p) > CHUNK:
            out.append(cur)
            cur = ""
        cur += p
    if cur:
        out.append(cur)
    return out


def translate(text, lang, retries, src="en"):
    done = []
    for i, c in enumerate(chunks(text)):
        if not c.strip():
            done.append(c)
            continue
        lead = c[: len(c) - len(c.lstrip())]
        trail = c[len(c.rstrip()):]
        last = None
        for attempt in range(retries + 1):
            try:
                out = call(c.strip(), lang, 0.3 + 0.15 * attempt, src)
                out = re.sub(r"^```[a-z]*\n|\n```$", "", out).strip()
                fails = guard(c, out)
            except Exception as e:  # network or truncation: retry like a guard failure
                out, fails = None, ["api: %s" % e]
            if not fails:
                done.append(lead + out + trail)
                break
            last = fails
            print("  chunk %d attempt %d: %s" % (i + 1, attempt + 1, "; ".join(fails)),
                  file=sys.stderr)
            time.sleep(2)
        else:
            sys.exit("REFUSED: chunk %d failed every attempt (%s). Nothing written."
                     % (i + 1, "; ".join(last)))
    return "".join(done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=sorted(LANGS))
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--src", default="en", choices=sorted(SOURCE),
                    help="source language: en (the site pages) or ca (the Catalan books)")
    a = ap.parse_args()
    src = open(a.inp, encoding="utf-8").read()
    if a.src == a.lang:
        sys.exit("source and target are the same language")
    out = translate(src, a.lang, a.retries, a.src)
    open(a.out, "w", encoding="utf-8").write(out)
    print("wrote %s (%d chars)" % (a.out, len(out)), file=sys.stderr)


if __name__ == "__main__":
    main()
