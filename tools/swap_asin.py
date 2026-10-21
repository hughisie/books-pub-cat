#!/usr/bin/env python3
"""Prepare Chiromancy's Amazon links locally. Dry-run unless --apply is supplied.

    python3 tools/swap_asin.py --kindle ASIN --paperback ASIN [--apply]

Sets only Chiromancy's catalogue fields, releases its held article in the local
build, and replaces any identifiable older Chiromancy Amazon search URLs in
tracked text files. No network requests, staging, commits or deployment.
"""
import argparse
import difflib
import html
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PROTECTED = {'B0HNSCFGJZ', 'B0HNSKXK32'}
CATALOGUE = Path('tools/blog/articles.json')
TEXT_SUFFIXES = {'.html', '.json', '.md', '.txt', '.xml', '.py', '.js', '.csv', '.tsv'}
URL = re.compile(r'https?://(?:www\.)?amazon\.[a-z.]+/s(?:/|\?)[^\s<>"\'`]*')


def asin(value):
    if not re.fullmatch(r'[A-Z0-9]{10}', value):
        raise argparse.ArgumentTypeError('ASIN must contain exactly 10 upper-case letters or digits')
    if value in PROTECTED:
        raise argparse.ArgumentTypeError('that ASIN belongs to Possessed')
    return value


def tracked_files(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                            check=True, capture_output=True)
    return [Path(p) for p in result.stdout.decode().split('\0') if p]


def safe_text(path):
    # Never inspect secrets, hidden files or symlinks.
    return (not any(part.startswith('.') for part in path.parts)
            and path.suffix.lower() in TEXT_SUFFIXES
            and not any(word in path.name.lower() for word in ('credential', 'cookie', 'token', 'secret')))


def replace_searches(text, kindle, paperback):
    changes = []
    def replace(match):
        raw = match.group()
        decoded = unquote(html.unescape(raw)).lower()
        if not any(term in decoded for term in ('chiromancy', 'cureau', '9798164051235')):
            return raw
        parsed = urlsplit(html.unescape(raw))
        query = parse_qs(parsed.query)
        is_kindle = 'kindle' in decoded or query.get('i') == ['digital-text']
        is_paper = 'paperback' in decoded or '9798164051235' in decoded or query.get('i') == ['stripbooks']
        if is_kindle == is_paper:
            raise ValueError('cannot safely determine the format of search URL: ' + raw)
        target = kindle if is_kindle else paperback
        # Keep existing tracking and other non-search parameters verbatim.
        params = [p for p in parsed.query.split('&')
                  if p.split('=', 1)[0] not in ('k', 'i', 'field-keywords', 'keywords')]
        new = f'{parsed.scheme}://{parsed.netloc}/dp/{target}'
        if params:
            new += '?' + '&'.join(params)
        if parsed.fragment:
            new += '#' + parsed.fragment
        if '&amp;' in raw:
            new = new.replace('&', '&amp;')
        changes.append((raw, new))
        return new
    return URL.sub(replace, text), changes


def prepare(root, kindle, paperback):
    """Build in a disposable copy so a dry-run cannot alter the working tree."""
    if kindle == paperback:
        raise ValueError('Kindle and paperback ASINs must differ')
    paths = tracked_files(root)
    originals = {}
    for rel in paths:
        if safe_text(rel) and not (root / rel).is_symlink():
            try:
                originals[rel] = (root / rel).read_text(encoding='utf-8')
            except UnicodeDecodeError:
                pass
    cfg = json.loads(originals[CATALOGUE])
    books = [a['book'] for a in cfg['articles'] if a['book'].get('slug') == 'chiromancy']
    if len(books) != 1:
        raise ValueError('expected exactly one Chiromancy catalogue entry')
    book = books[0]
    for kind, value in [('kindle', kindle), ('paperback', paperback)]:
        existing = book.get('asin_' + kind)
        if existing and existing != value:
            raise ValueError(f'Chiromancy already has a different {kind} ASIN: {existing}')
        book['asin_' + kind] = value
    book['live'] = True
    replacements = []
    prepared = {}
    for rel, text in originals.items():
        prepared[rel], found = replace_searches(text, kindle, paperback)
        replacements.extend((str(rel), old, new) for old, new in found)
    prepared[CATALOGUE] = json.dumps(cfg, indent=1, ensure_ascii=False) + '\n'
    with tempfile.TemporaryDirectory(prefix='.swap-asins-', dir=root) as temporary:
        stage = Path(temporary)
        for rel, text in prepared.items():
            dest = stage / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding='utf-8')
        subprocess.run([sys.executable, str(stage / 'tools/blog/build.py')],
                       cwd=stage, check=True, capture_output=True, text=True)
        changes = {}
        for dest in sorted(stage.rglob('*')):
            if not dest.is_file():
                continue
            rel = dest.relative_to(stage)
            new = dest.read_text(encoding='utf-8')
            old = originals.get(rel, '')
            if new == old:
                continue
            actual = root / rel
            if actual.is_symlink():
                raise ValueError('refusing to replace a symlink: ' + str(rel))
            if rel not in originals and actual.exists():
                if actual.is_file() and actual.read_text(encoding='utf-8') == new:
                    continue
                raise ValueError('refusing to overwrite an untracked file: ' + str(rel))
            for protected in PROTECTED:
                if old.count(protected) != new.count(protected):
                    raise ValueError('build would change a Possessed ASIN occurrence: ' + str(rel))
            changes[rel] = (old, new)
    return changes, replacements


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--kindle', required=True, type=asin)
    parser.add_argument('--paperback', required=True, type=asin)
    parser.add_argument('--apply', action='store_true', help='write the reviewed changes locally')
    args = parser.parse_args(argv)
    try:
        changes, replacements = prepare(ROOT, args.kindle, args.paperback)
        print(f'{len(replacements)} Chiromancy search links; {len(changes)} files to change')
        for rel, old, new in replacements:
            print(f'{rel}: {old} -> {new}')
        for rel, (old, new) in changes.items():
            print(''.join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                             fromfile=str(rel), tofile=str(rel))), end='')
        if args.apply:
            for rel, (_, new) in changes.items():
                (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
                (ROOT / rel).write_text(new, encoding='utf-8')
            print(f'Applied {len(changes)} file changes locally. Review git diff before committing.')
        else:
            print('Dry-run only. Add --apply to write these changes locally.')
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
