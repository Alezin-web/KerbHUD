"""Atualizador (sem rede: tudo injetado)."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from kerbhud.core import updater as U


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)


def src_files(version, extra=None):
    f = {"src/kerbhud/__init__.py": f'__version__ = "{version}"\n', "README.md": f"v{version}",
         "dados/logos/bmw.png": "DO-ZIP-NAO-DEVE-COPIAR"}
    f.update(extra or {})
    return f


class TestVersions(unittest.TestCase):
    def test_compare(self):
        self.assertTrue(U.is_newer("v0.13.1", "0.13.0"))
        self.assertTrue(U.is_newer("0.14", "0.13.9"))
        self.assertFalse(U.is_newer("0.13.0", "0.13"))
        self.assertFalse(U.is_newer("0.12.9", "0.13.0"))
        with self.assertRaises(ValueError):
            U.parse_version("beta")

    def test_repo_and_hosts(self):
        self.assertTrue(U.valid_repo("alex/KerbHUD"))
        for bad in ("", "alex", "a/b/c", "../x", "a b/c"):
            self.assertFalse(U.valid_repo(bad), bad)
        self.assertTrue(U.host_allowed("https://github.com/a/b/releases/download/v1/x.zip"))
        self.assertTrue(U.host_allowed("https://objects.githubusercontent.com/x"))
        for bad in ("http://github.com/x", "https://evil.com/github.com", "https://github.com.evil.com/x", "file:///etc/passwd"):
            self.assertFalse(U.host_allowed(bad), bad)


class TestCheck(unittest.TestCase):
    REL = {"tag_name": "v0.14.0", "body": "novidades", "assets": [
        {"name": "KerbHUD-windows.zip", "browser_download_url": "https://github.com/a/b/w.zip", "size": 5},
        {"name": "KerbHUD-source.zip", "browser_download_url": "https://github.com/a/b/s.zip", "size": 6},
        {"name": "KerbHUD-source.zip.sha256", "browser_download_url": "https://github.com/a/b/s.sha"}]}

    def test_newer_source_and_frozen(self):
        info = U.check_latest("a/b", "0.13.0", frozen=False, fetch_json=lambda url: self.REL)
        self.assertEqual((info.version, info.asset_name), ("0.14.0", "KerbHUD-source.zip"))
        self.assertTrue(info.sha256_url.endswith("s.sha"))
        self.assertEqual(U.check_latest("a/b", "0.13.0", frozen=True, fetch_json=lambda u: self.REL).asset_name,
                         "KerbHUD-windows.zip")

    def test_up_to_date_and_errors(self):
        self.assertIsNone(U.check_latest("a/b", "0.14.0", frozen=False, fetch_json=lambda u: self.REL))
        with self.assertRaises(U.UpdateError):
            U.check_latest("", "0.1", fetch_json=lambda u: self.REL)
        with self.assertRaises(U.UpdateError):
            U.check_latest("a/b", "0.1", frozen=False, fetch_json=lambda u: {"message": "Not Found"})
        with self.assertRaises(U.UpdateError):
            U.check_latest("a/b", "0.1", frozen=False, fetch_json=lambda u: {"tag_name": "v9", "assets": []})


class TestApply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_download_verify_extract_and_apply_keeps_user_data(self):
        app = self.root / "app"
        (app / "src/kerbhud").mkdir(parents=True)
        (app / "src/kerbhud/__init__.py").write_text('__version__ = "0.13.0"\n')
        (app / "README.md").write_text("v0.13.0")
        (app / "dados/logos").mkdir(parents=True)
        (app / "dados/logos/bmw.png").write_text("MEU-LOGO")
        zsrc = self.root / "release.zip"
        make_zip(zsrc, {"KerbHUD-main/" + k: v for k, v in src_files("0.14.0", {"src/kerbhud/novo.py": "x=1"}).items()})
        digest = hashlib.sha256(zsrc.read_bytes()).hexdigest()

        def fake_download(url, dest, progress=None):
            Path(dest).write_bytes(zsrc.read_bytes())

        info = U.ReleaseInfo("0.14.0", "", "s.zip", "https://github.com/a/b/s.zip", "https://github.com/a/b/s.sha")
        new = U.download_and_prepare(info, self.root / "work", download=fake_download,
                                     fetch_text=lambda u: f"{digest}  s.zip")
        changed = U.apply_source_update(new, app, "0.14.0")
        self.assertIn("src/kerbhud/novo.py", changed)
        self.assertIn('"0.14.0"', (app / "src/kerbhud/__init__.py").read_text())
        self.assertEqual((app / "dados/logos/bmw.png").read_text(), "MEU-LOGO")  # dados intactos
        self.assertEqual((app / ".backup/0.13.0/README.md").read_text(), "v0.13.0")  # backup do que foi trocado
        self.assertEqual(U.apply_source_update(new, app, "0.14.0"), [])  # idempotente

    def test_bad_hash_wrong_version_and_not_kerbhud_are_refused(self):
        z = self.root / "r.zip"
        make_zip(z, src_files("0.14.0"))
        info = U.ReleaseInfo("0.14.0", "", "s.zip", "https://github.com/a/b/s.zip", "https://github.com/a/b/s.sha")
        dl = lambda url, dest, progress=None: Path(dest).write_bytes(z.read_bytes())  # noqa: E731
        with self.assertRaises(U.UpdateError):
            U.download_and_prepare(info, self.root / "w1", download=dl, fetch_text=lambda u: "0" * 64)
        new = U.download_and_prepare(info, self.root / "w2", download=dl, fetch_text=lambda u: hashlib.sha256(z.read_bytes()).hexdigest())
        app = self.root / "app"
        app.mkdir()
        with self.assertRaises(U.UpdateError):
            U.apply_source_update(new, app, "0.15.0")  # release disse 0.15, o zip é 0.14
        other = self.root / "outro"
        other.mkdir()
        (other / "x.txt").write_text("x")
        with self.assertRaises(U.UpdateError):
            U.apply_source_update(other, app, "0.14.0")

    def test_zip_slip_and_symlinks_are_refused(self):
        for name in ("../evil.txt", "/abs.txt", "a/../../evil.txt", "C:/evil.txt"):
            z = self.root / "bad.zip"
            make_zip(z, {name: "x"})
            with self.assertRaises(U.UpdateError, msg=name):
                U.safe_extract(z, self.root / "out")
        self.assertFalse((self.root / "evil.txt").exists())
        z = self.root / "link.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zi = zipfile.ZipInfo("link")
            zi.external_attr = 0o120777 << 16
            zf.writestr(zi, "/etc/passwd")
        with self.assertRaises(U.UpdateError):
            U.safe_extract(z, self.root / "out2")
        (self.root / "notzip.zip").write_text("nada")
        with self.assertRaises(U.UpdateError):
            U.safe_extract(self.root / "notzip.zip", self.root / "out3")

    def test_release_json_with_null_assets_or_odd_size_does_not_crash(self):
        info = U.check_latest("a/b", "0.1.0", frozen=False, fetch_json=lambda u: {
            "tag_name": "v9.0.0", "assets": [{"name": "KerbHUD-source.zip", "size": "muito", "browser_download_url": "https://github.com/x"}]})
        self.assertEqual(info.size, 0)
        with self.assertRaises(U.UpdateError):
            U.check_latest("a/b", "0.1.0", frozen=False, fetch_json=lambda u: {"tag_name": "v9.0.0", "assets": None})

    def test_swap_script_never_touches_data(self):
        bat = U.write_swap_script(self.root / "novo", self.root, "KerbHUD.exe", 1234)
        text = bat.read_bytes().decode()
        self.assertIn("\r\n", text)
        self.assertIn("/XD dados", text)
        self.assertIn("PID eq 1234", text)
        self.assertIn('find ",""1234"","', text)  # PID exato (não confunde 123 com 1234)
        self.assertIn("GTR 60", text)  # a espera tem limite
        self.assertIn("if errorlevel 8", text)  # robocopy falhou: não apaga a pasta nem some com a versão antiga


if __name__ == "__main__":
    unittest.main()
