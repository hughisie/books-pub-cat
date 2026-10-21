"""Offline integration tests. ASIN strings below are synthetic test inputs."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import swap_asin as swap

KINDLE = 'B012345678'
PAPER = 'B087654321'


class SwapTests(unittest.TestCase):
    def test_search_links_preserve_tracking_and_other_books(self):
        base = 'https://' + 'www.amazon.com/s?'
        other = base + 'k=another+book'
        source = base + 'k=Chiromancy+Kindle&amp;utm_source=books.pub.cat&amp;utm_medium=book-page ' + base + 'k=Chiromancy+paperback ' + other
        result, changes = swap.replace_searches(source, KINDLE, PAPER)
        self.assertEqual(len(changes), 2)
        self.assertIn('/dp/' + KINDLE + '?utm_source=books.pub.cat&amp;utm_medium=book-page', result)
        self.assertIn('/dp/' + PAPER, result)
        self.assertIn(other, result)
        with self.assertRaises(ValueError):
            swap.replace_searches(base + 'k=Chiromancy', KINDLE, PAPER)

    def test_invalid_inputs(self):
        import argparse
        for value in ('bad', 'b012345678', '../escape!', *swap.PROTECTED):
            with self.assertRaises(argparse.ArgumentTypeError):
                swap.asin(value)
        with self.assertRaises(ValueError):
            swap.prepare(swap.ROOT, KINDLE, KINDLE)

    def test_dry_run_apply_rebuild_and_idempotence(self):
        # Copy tracked files only. Never run the tool against the real catalogue.
        with tempfile.TemporaryDirectory(prefix='swap-test-', dir=swap.ROOT.parent) as temp:
            root = Path(temp)
            for rel in swap.tracked_files(swap.ROOT):
                src = swap.ROOT / rel
                if src.is_file() and not src.is_symlink():
                    dest = root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dest)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            def hashes():
                return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in root.rglob('*') if p.is_file() and '.git' not in p.parts}
            before = hashes()
            with patch.object(swap, 'ROOT', root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(swap.main(['--kindle', KINDLE, '--paperback', PAPER]), 0)
                self.assertEqual(before, hashes())
                self.assertEqual(swap.main(['--kindle', KINDLE, '--paperback', PAPER, '--apply']), 0)
            config = json.loads((root / swap.CATALOGUE).read_text())
            book = next(a['book'] for a in config['articles'] if a['book']['slug'] == 'chiromancy')
            self.assertEqual((book['asin_kindle'], book['asin_paperback'], book['live']), (KINDLE, PAPER, True))
            article = root / 'blog/palmistry-history-1658-physician-tried-to-prove-it/index.html'
            for rel in [Path('chiromancy/index.html'), Path('books/index.html'), article.relative_to(root)]:
                text = (root / rel).read_text()
                self.assertIn('/dp/' + KINDLE, text)
                self.assertIn('/dp/' + PAPER, text)
            self.assertNotIn('coming to Amazon', (root / 'chiromancy/index.html').read_text())
            self.assertIn(article.parent.name, (root / 'sitemap.xml').read_text())
            self.assertIn(article.parent.name, (root / 'blog/feed.xml').read_text())
            for rel in ('possessed/index.html', 'tools/blog/book-body/possessed.html'):
                self.assertEqual(before[rel], hashes()[rel])
            subprocess.run(['python3', str(root / 'tools/check_hreflang.py')], check=True, capture_output=True)
            changes, _ = swap.prepare(root, KINDLE, PAPER)
            self.assertEqual(changes, {})
            # New generated article is now tracked, as it will be in the reviewed commit.
            subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
            changes, _ = swap.prepare(root, KINDLE, PAPER)
            self.assertEqual(changes, {})
            with self.assertRaises(ValueError):
                swap.prepare(root, 'B000000000', PAPER)


if __name__ == '__main__':
    unittest.main()
