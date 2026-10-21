#!/usr/bin/env python3
"""Adds the Plausible tag (self-hosted, analytics.pub.cat) to every page of books.pub.cat.
Idempotent: skips pages that already carry it. Run from repo root: python3 tools/analytics/inject.py
Tag: page views plus outbound-link clicks (Amazon, Whop) plus file downloads."""
import os, glob
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TAG = '<script defer data-domain="books.pub.cat" src="https://analytics.pub.cat/js/script.outbound-links.file-downloads.js"></script>\n'
n = 0
for p in glob.glob(ROOT + '/**/*.html', recursive=True):
    rel = os.path.relpath(p, ROOT)
    if rel.startswith(('tools/', '.git/')): continue
    s = open(p, encoding='utf-8').read()
    if 'analytics.pub.cat' in s or '</head>' not in s: continue
    open(p, 'w', encoding='utf-8').write(s.replace('</head>', TAG + '</head>', 1)); n += 1
print('tagged', n, 'pages')
