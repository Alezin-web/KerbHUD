"""Os .bat da raiz do projeto devem sempre rodar o código DA PRÓPRIA PASTA (caminho absoluto)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATS = sorted(ROOT.glob("*.bat"))


class TestLaunchers(unittest.TestCase):
    def test_expected_launchers_exist(self):
        names = {b.name for b in BATS}
        for expected in ("KerbHUD.bat", "KerbHUD-DEMO.bat", "KerbHUD-Editar.bat", "Diagnostico-LMU.bat",
                         "Diagnostico-iRacing.bat", "Baixar-logos.bat", "Baixar-bandeiras.bat", "Logos-que-faltam.bat", "Instalar-dependencias.bat", "Gerar-exe.bat"):
            self.assertIn(expected, names)

    def test_each_launcher_pins_the_code_of_its_own_folder(self):
        for bat in BATS:
            raw = bat.read_bytes()
            text = raw.decode("utf-8")
            self.assertIn(b"\r\n", raw, bat.name)  # fim de linha do Windows
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), bat.name)  # sem LF solto
            self.assertIn('cd /d "%~dp0"', text, bat.name)  # trabalha na pasta do .bat
            self.assertIn('set "PYTHONPATH=%~dp0src"', text, bat.name)  # caminho ABSOLUTO desta cópia
            self.assertNotRegex(text, r"(?im)^set\s+\"?PYTHONPATH=src", bat.name)  # nunca o "src" relativo
            self.assertIn("-m kerbhud --version", text, bat.name)  # mostra qual versão vai rodar

    def test_launchers_call_the_right_commands(self):
        read = lambda n: (ROOT / n).read_text(encoding="utf-8")  # noqa: E731
        self.assertRegex(read("KerbHUD.bat"), r"-m kerbhud run %\*")
        self.assertIn("run --sim demo", read("KerbHUD-DEMO.bat"))
        self.assertIn("run --edit", read("KerbHUD-Editar.bat"))
        self.assertIn("diag --sim lmu", read("Diagnostico-LMU.bat"))
        self.assertIn("diag --sim iracing", read("Diagnostico-iRacing.bat"))
        self.assertIn("fetch-logos", read("Baixar-logos.bat"))
        self.assertIn("fetch-flags", read("Baixar-bandeiras.bat"))
        self.assertIn("logos-status", read("Logos-que-faltam.bat"))
        self.assertIn("pip install -r requirements.txt", read("Instalar-dependencias.bat"))

    def test_version_text_identifies_the_running_copy(self):
        from kerbhud import __version__
        from kerbhud.cli import version_text
        text = version_text()
        self.assertIn(__version__, text)
        self.assertIn(str(Path(__import__("kerbhud").__file__).resolve().parent), text)  # pasta do código
        for label in ("Python", "PySide6", "configuração"):
            self.assertIn(label, text)
        self.assertTrue(re.fullmatch(r"\d+\.\d+\.\d+(\.\d+)?", __version__))


if __name__ == "__main__":
    unittest.main()
