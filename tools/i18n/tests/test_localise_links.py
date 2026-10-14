import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import build


class LocaliseLinks(unittest.TestCase):
    def test_plain_link_gets_prefix(self):
        self.assertEqual(build.localise_links('<a href="/books/">', "es"), '<a href="/es/books/">')

    def test_already_prefixed_link_is_left_alone(self):
        for lang in ("es", "ca"):
            s = f'<a href="/{lang}/dracula/">'
            self.assertEqual(build.localise_links(s, lang), s)

    def test_assets_and_protocol_relative_untouched(self):
        s = '<a href="/assets/x.css"><a href="//cdn/x">'
        self.assertEqual(build.localise_links(s, "ca"), s)

    def test_utm_and_form_ids_not_suffixed_twice(self):
        s = 'x?utm_medium=books-es&y <form id="signup-es">'
        self.assertEqual(build.localise_links(s, "es"), s)
        self.assertIn("utm_medium=books-ca&", build.localise_links("x?utm_medium=books&y", "ca"))

    def test_idempotent(self):
        once = build.localise_links('<a href="/faq/"><a href="/ca/faq/">', "ca")
        self.assertEqual(build.localise_links(once, "ca"), once)
        self.assertNotIn("/ca/ca/", once)


if __name__ == "__main__":
    unittest.main()
