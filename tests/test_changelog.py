import tempfile
import unittest
from pathlib import Path

from kerbhud import __version__
from kerbhud.core.changelog import (entries_to_html, entries_to_show, load_changelog, md_to_html, parse_changelog)

ROOT = Path(__file__).resolve().parents[1]
TEXT = """## 0.3.0 — Terceira

* **novo** `x`

## 0.2.0 — Segunda
* b
## v0.1.0
* a
"""


class TestChangelog(unittest.TestCase):
    def test_parse_sorted_newest_first(self):
        e = parse_changelog(TEXT)
        self.assertEqual([x.version for x in e], ["0.3.0", "0.2.0", "0.1.0"])
        self.assertEqual((e[0].title, e[2].title), ("Terceira", ""))

    def test_what_to_show(self):
        e = parse_changelog(TEXT)
        self.assertEqual([x.version for x in entries_to_show(e, None, "0.3.0")], ["0.3.0"])  # 1ª vez: só a mais recente
        self.assertEqual([x.version for x in entries_to_show(e, "0.1.0", "0.3.0")], ["0.3.0", "0.2.0"])
        self.assertEqual(entries_to_show(e, "0.3.0", "0.3.0"), [])
        self.assertEqual([x.version for x in entries_to_show(e, "0.1.0", "0.2.0")], ["0.2.0"])  # não mostra futuras
        self.assertEqual([x.version for x in entries_to_show(e, "lixo", "0.3.0")], ["0.3.0"])

    def test_html_is_escaped_and_images_are_restricted(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "ok.png").write_bytes(b"x")
            html = md_to_html("* <script>alert(1)</script> **b**\n![a](ok.png)\n![b](../ok.png)\n"
                              "![c](https://evil.com/x.png)\n![d](missing.png)\n### T", Path(d))
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<b>b</b>", html)
        self.assertEqual(html.count("<img"), 1)
        self.assertIn('src="ok.png"', html)
        self.assertIn("<h3>T</h3>", html)
        self.assertIn("<i>kerb</i>", md_to_html("* *kerb* e **negrito** e `x*y`"))
        self.assertNotIn("<i>", md_to_html("* 2*3*4 sem itálico"))

    def test_project_changelog_covers_the_current_version_and_its_images_exist(self):
        entries = load_changelog(ROOT)
        self.assertIn(__version__, [e.version for e in entries], "escreva as novidades desta versão em CHANGELOG.md")
        import re
        for name in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")):
            self.assertTrue((ROOT / "changelog" / name).is_file(), name)
        self.assertIn("<h2>Versão", entries_to_html(entries[:1], ROOT / "changelog"))


if __name__ == "__main__":
    unittest.main()


class TestGuideAndBrand(unittest.TestCase):
    def test_guides_have_the_same_sections_hotkey_placeholder_and_existing_images(self):
        import re
        from kerbhud.core.changelog import guide_html, hotkeys_md, load_guide
        pt, en = load_guide(ROOT, "pt-BR"), load_guide(ROOT, "en")
        self.assertTrue(pt and en and pt != en)
        self.assertEqual(len(re.findall(r"^## ", pt, re.M)), len(re.findall(r"^## ", en, re.M)))
        for text in (pt, en):
            self.assertIn("{{HOTKEYS}}", text)
            for name in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
                self.assertTrue((ROOT / "changelog" / name).is_file(), name)
        from kerbhud.core.settings_schema import DEFAULT_HOTKEYS, HOTKEY_LABELS
        md = hotkeys_md(DEFAULT_HOTKEYS, lambda a: HOTKEY_LABELS[a])
        html = guide_html(pt, md, ROOT / "changelog")
        self.assertIn("Ctrl+Alt+E", html)
        self.assertNotIn("{{HOTKEYS}}", html)
        self.assertIn("<h2>", html)
        self.assertEqual(html.count("<img"), 1)
        self.assertEqual(hotkeys_md({"a": "", "b": "Ctrl+Alt+X"}, lambda a: a).count("\n"), 0)  # desligados não aparecem

    def test_branded_page_has_logo_wordmark_and_kerb_stripes(self):
        from kerbhud.core.changelog import branded_page
        page = branded_page("<p>x</p>", "tag", ROOT / "changelog")
        self.assertIn("logo.png", page)
        self.assertIn("KERB", page)
        self.assertIn("HUD", page)
        self.assertGreater(page.count("bgcolor"), 50)
        self.assertNotIn("logo.png", branded_page("<p>x</p>", "tag", None))

    def test_brand_geometry_is_inside_the_unit_square_and_alternates(self):
        from kerbhud.core import brand
        for pts, _c in brand.k_parts():
            self.assertTrue(all(0 <= x <= 1 and 0 <= y <= 1 for x, y in pts))
        stripes = brand.kerb_stripes()
        self.assertEqual({c for _p, c in stripes}, {brand.RED, brand.WHITE})
        self.assertTrue(all(stripes[i][1] != stripes[i + 1][1] for i in range(len(stripes) - 1)))
        self.assertEqual(brand.NAME, "KerbHUD")
