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


class SubmitTest(unittest.TestCase):
    def test_fields_match_the_prefilled_link_of_the_form(self):
        from kerbhud.core import feedback as f
        self.assertEqual(f.FIELDS, {"idea": "entry.639367796", "why": "entry.201888621", "simulator": "entry.1443931871",
                                    "version": "entry.1972130337", "contact": "entry.280291273"})
        self.assertTrue(f.FORM_URL.startswith("https://docs.google.com/forms/d/e/") and f.FORM_URL.endswith("/formResponse"))

    def test_build_submission_cleans_limits_and_requires_an_idea(self):
        from kerbhud.core import feedback as f
        d = f.build_submission("  Mostrar o clima na pista\x00 ", "x" * 5000, "iRacing", "a@b.com", "0.17.13")
        self.assertEqual(d["idea"], "Mostrar o clima na pista")  # sem controle e sem espaços nas pontas
        self.assertEqual(len(d["why"]), f.LIMITS["why"])
        for short in ("", "curta", "   \x00  "):
            with self.assertRaises(f.FeedbackError):
                f.build_submission(short)

    def test_encoded_body_only_has_the_form_fields(self):
        from kerbhud.core import feedback as f
        body = f.encode_form(f.build_submission("Uma ideia legal & com símbolos=?", "", "iRacing", "", "1.2"))
        q = parse_qs(body.decode())
        self.assertEqual(set(q) - set(f.FIELDS.values()), set())
        self.assertEqual(q["entry.639367796"], ["Uma ideia legal & com símbolos=?"])  # &, = e acentos codificados
        self.assertEqual(q["entry.1972130337"], ["1.2"])

    @staticmethod
    def _opener(url="https://docs.google.com/forms/d/e/ID/formResponse", status=200, exc=None, sent=None):
        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def geturl(s): return url
            @property
            def status(s_): return status
        def op(req, timeout=None):
            if sent is not None:
                sent.append((req.full_url, req.data, req.get_method(), timeout))
            if exc:
                raise exc
            return R()
        return op

    def test_submit_posts_to_the_form_over_https(self):
        from kerbhud.core import feedback as f
        sent = []
        f.submit(f.build_submission("Uma ideia legal para o overlay"), "0.17.13", opener=self._opener(sent=sent))
        url, body, method, timeout = sent[0]
        self.assertEqual((url, method), (f.FORM_URL, "POST"))
        self.assertLessEqual(timeout, 30)
        self.assertIn(b"entry.639367796=", body)

    def test_submit_failures_become_friendly_errors(self):
        import urllib.error
        from kerbhud.core import feedback as f
        data = f.build_submission("Uma ideia legal para o overlay")
        cases = [self._opener(exc=urllib.error.URLError("sem rede")), self._opener(exc=TimeoutError()),
                 self._opener(exc=urllib.error.HTTPError(f.FORM_URL, 500, "x", {}, None)),
                 self._opener(url="https://accounts.google.com/login"),  # pediu login: formulário não é público
                 self._opener(url="http://docs.google.com/forms/d/e/ID/formResponse"),  # sem HTTPS
                 self._opener(url="https://evil.example/formResponse"), self._opener(status=500)]
        for op in cases:
            with self.assertRaises(f.FeedbackError):
                f.submit(data, opener=op)

    def test_cooldown_blocks_a_second_send_for_a_minute(self):
        from kerbhud.core import feedback as f
        now = [100.0]
        c = f.Cooldown(60, clock=lambda: now[0])
        self.assertEqual(c.remaining(), 0.0)
        c.mark()
        now[0] += 20
        self.assertAlmostEqual(c.remaining(), 40.0)
        now[0] += 41
        self.assertEqual(c.remaining(), 0.0)
