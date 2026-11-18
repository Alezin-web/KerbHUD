"""Publicação no GitHub: repositório padrão, notas do Release, workflow e imagens do README."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from kerbhud import __version__
from kerbhud.core import updater
from kerbhud.core.changelog import plain_release_notes, release_notes

ROOT = Path(__file__).resolve().parents[1]


class TestDefaultRepo(unittest.TestCase):
    def test_empty_setting_falls_back_to_the_official_repo(self):
        self.assertTrue(updater.valid_repo(updater.DEFAULT_REPO))
        for s in ({}, {"update_repo": ""}, {"update_repo": "   "}, None):
            self.assertEqual(updater.effective_repo(s), updater.DEFAULT_REPO)
        self.assertEqual(updater.effective_repo({"update_repo": "outro/fork"}), "outro/fork")


class TestReleaseNotes(unittest.TestCase):
    def test_current_version_has_notes_in_both_languages(self):
        text = release_notes(__version__, "Alezin-web/KerbHUD", ROOT)
        self.assertIn("## Português", text)
        self.assertIn("## English", text)
        self.assertIn("KerbHUD-windows.zip", text)

    def test_images_point_to_the_tag(self):
        text = release_notes("0.17.0", "Alezin-web/KerbHUD", ROOT)
        self.assertIn("https://raw.githubusercontent.com/Alezin-web/KerbHUD/v0.17.0/changelog/banner-0.17.0.png", text)

    def test_unknown_version_is_an_error(self):
        with self.assertRaises(ValueError):
            release_notes("99.0.0", "a/b", ROOT)

    def test_plain_notes_keep_only_the_interface_language(self):
        text = release_notes("0.17.0", "Alezin-web/KerbHUD", ROOT)
        pt, en = plain_release_notes(text, "pt-BR"), plain_release_notes(text, "en")
        self.assertIn("Agora é KerbHUD", pt)
        self.assertNotIn("Now it's KerbHUD", pt)
        self.assertIn("Now it's KerbHUD", en)
        for t in (pt, en):
            self.assertNotIn("**", t)
            self.assertNotIn("![", t)
            self.assertNotIn("KerbHUD-windows.zip", t)

    def test_plain_notes_handle_text_written_by_hand(self):
        self.assertEqual(plain_release_notes("* **Novo:** `x` e *y*"), "• Novo: x e y")
        self.assertEqual(plain_release_notes(""), "")


class TestWorkflowAndReadme(unittest.TestCase):
    def test_workflow_can_be_run_from_the_site_and_uses_the_changelog(self):
        wf = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch", wf)
        self.assertIn("tools/release_notes.py", wf)
        self.assertIn("body_path: release-notes.md", wf)
        self.assertTrue((ROOT / "tools/release_notes.py").is_file())

    def test_every_local_image_in_the_readme_exists(self):
        md = (ROOT / "README.md").read_text(encoding="utf-8")
        refs = re.findall(r'<img src="([^"]+)"', md) + re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", md)
        local = [r for r in refs if not r.startswith("http")]
        self.assertGreaterEqual(len(local), 6)
        for r in local:
            self.assertTrue((ROOT / r).is_file(), r)

    def test_readme_points_to_the_official_repo(self):
        md = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"github.com/{updater.DEFAULT_REPO}/releases/latest", md)
        self.assertLess(md.index("## Português"), md.index("## English"))  # português primeiro
        self.assertNotIn("PUBLICAR-NO-GITHUB", md)  # passo a passo de publicação não faz parte do projeto


if __name__ == "__main__":
    unittest.main()
