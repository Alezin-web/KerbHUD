import unittest
from urllib.parse import parse_qs, urlparse

from kerbhud.core.feedback import suggestion_url
from kerbhud.core.updatenotice import UpdateNotice


class SuggestionUrlTest(unittest.TestCase):
    def test_opens_the_new_issue_page_of_the_repo_with_a_template(self):
        u = urlparse(suggestion_url("Alezin-web/KerbHUD", "0.17.14", "pt"))
        self.assertEqual((u.scheme, u.netloc, u.path), ("https", "github.com", "/Alezin-web/KerbHUD/issues/new"))
        q = parse_qs(u.query)
        self.assertTrue(q["title"][0].startswith("Sugestão"))
        self.assertIn("0.17.14", q["body"][0])

    def test_english_and_unknown_language(self):
        self.assertTrue(parse_qs(urlparse(suggestion_url("a/b", "1", "en")).query)["title"][0].startswith("Suggestion"))
        self.assertTrue(parse_qs(urlparse(suggestion_url("a/b", "1", "xx")).query)["title"][0].startswith("Sugestão"))

    def test_invalid_repo_falls_back_to_the_official_one_and_never_to_other_hosts(self):
        for bad in ("", "evil.com/x/y", "a b/c", "../x", "javascript:alert(1)"):
            u = urlparse(suggestion_url(bad, "1"))
            self.assertEqual(u.netloc, "github.com", bad)
            self.assertTrue(u.path.startswith("/Alezin-web/KerbHUD/"), bad)

    def test_special_characters_in_version_are_encoded(self):
        self.assertNotIn(" ", suggestion_url("a/b", "1 &x=y"))


class UpdateNoticeTest(unittest.TestCase):
    def test_banner_only_when_there_is_a_version_and_it_was_not_dismissed(self):
        n = UpdateNotice()
        self.assertFalse(n.banner_visible(None))
        self.assertTrue(n.banner_visible("0.18.0"))
        n.dismiss("0.18.0")
        self.assertFalse(n.banner_visible("0.18.0"))
        self.assertTrue(n.banner_visible("0.18.1"))  # versão mais nova: volta a avisar
        self.assertFalse(n.banner_visible("0.17.9"))

    def test_balloon_once_per_version(self):
        n = UpdateNotice()
        self.assertTrue(n.should_balloon("0.18.0"))
        self.assertFalse(n.should_balloon("0.18.0"))
        self.assertTrue(n.should_balloon("0.18.1"))

    def test_garbage_dismissed_value_does_not_crash(self):
        self.assertTrue(UpdateNotice("lixo").banner_visible("0.18.0"))  # valor salvo ilegível: avisa, sem erro


if __name__ == "__main__":
    unittest.main()
