import ast
import re
import unittest
from pathlib import Path

from kerbhud.core import i18n
from kerbhud.core.i18n_en import TRANSLATIONS

SRC = Path(__file__).resolve().parents[1] / "src" / "kerbhud"
_PH = re.compile(r"\{[^{}]*\}")


def _ui_keys():
    keys = set()
    for p in (SRC / "ui").glob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tr" and n.args \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                keys.add(n.args[0].value)
    return keys


class TestI18n(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("pt-BR")

    def test_resolve_language(self):
        self.assertEqual(i18n.resolve_language("en", "pt_BR"), "en")
        self.assertEqual(i18n.resolve_language("pt-BR", "en_US"), "pt-BR")
        self.assertEqual(i18n.resolve_language("auto", "pt_BR"), "pt-BR")
        self.assertEqual(i18n.resolve_language("auto", "pt_PT"), "pt-BR")
        self.assertEqual(i18n.resolve_language("auto", "de_DE"), "en")
        self.assertEqual(i18n.resolve_language(None, ""), "en")

    def test_tr_translates_only_in_english_and_never_loses_text(self):
        self.assertEqual(i18n.tr("Sair"), "Sair")
        i18n.set_language("en")
        self.assertEqual(i18n.tr("Sair"), "Quit")
        self.assertEqual(i18n.tr("texto sem tradução"), "texto sem tradução")
        self.assertEqual(i18n.module_title("fuel", "COMBUSTÍVEL"), "FUEL")
        i18n.set_language("pt-BR")
        self.assertEqual(i18n.module_title("fuel", "COMBUSTÍVEL"), "COMBUSTÍVEL")

    def test_placeholders_match_in_every_translation(self):
        for pt, en in TRANSLATIONS.items():
            self.assertEqual(sorted(_PH.findall(pt)), sorted(_PH.findall(en)), pt)

    def test_every_ui_text_and_label_has_an_english_version(self):
        from kerbhud.core import settings_schema as S, visibility as V
        from kerbhud.core.module_options import SPECS
        from kerbhud.core.standings import COLUMN_LABELS
        from kerbhud.core.viewmodel import CHANNEL_LABELS
        from kerbhud.providers.demo import SCENARIOS
        need = set(_ui_keys())
        for d in (V.MODE_LABELS, S.SIMULATOR_LABELS, S.HOTKEY_LABELS, SCENARIOS, CHANNEL_LABELS, COLUMN_LABELS):
            need.update(d.values())
        for specs in SPECS.values():
            for o in specs:
                need.add(o.label)
                need.update(l for _v, l in o.choices)
        same_in_both = {"KerbHUD", "OK", "Layout", "Layout 1", "Layout 2", "Layout 3", "Layout 4", "RPM", "iRacing",
                        "Config", "Overlay", "Standings", "Relative", "Inputs", "Radar", "Track Map", "Widgets", "Layouts",
                        "Le Mans Ultimate", "Idioma / Language", "Config: {}", "Combustível", "PSI", "kPa"}
        missing = sorted(k for k in need if k not in TRANSLATIONS and k not in same_in_both
                         and not re.fullmatch(r"[\d.]+( s| m)?", k))
        self.assertEqual(missing, [], "textos sem tradução em core/i18n_en.py")

    def test_language_setting_is_validated(self):
        from kerbhud.core.settings_schema import validate_patch
        self.assertEqual(validate_patch({"language": "en"})[0], {"language": "en"})
        clean, errors = validate_patch({"language": "klingon"})
        self.assertTrue(errors and "language" not in clean)

    def test_english_changelog_is_used_when_present(self):
        from kerbhud.core.changelog import load_changelog
        root = SRC.parents[1]
        pt, en = load_changelog(root), load_changelog(root, "en")
        self.assertEqual([e.version for e in pt], [e.version for e in en], "CHANGELOG.en.md deve ter as mesmas versões")
        self.assertNotEqual(pt[0].body, en[0].body)


if __name__ == "__main__":
    unittest.main()
