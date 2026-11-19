"""Etapa 7 (sem Qt): validação das configurações, atalhos e gerenciamento de layouts."""
import json
import tempfile
import unittest
from pathlib import Path

from kerbhud.core.engine import DEFAULT_SETTINGS, load_settings
from kerbhud.core.layout import LayoutStore, preset_corrida
from kerbhud.core.settings_schema import (DEFAULT_HOTKEYS, HOTKEY_LABELS, apply_patch, normalize_hotkey,
                                             settings_to_patch, validate_patch)


class TestHotkeys(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize_hotkey("ctrl + alt + e"), "Ctrl+Alt+E")
        self.assertEqual(normalize_hotkey("Alt+Ctrl+Right"), "Ctrl+Alt+Right")
        self.assertEqual(normalize_hotkey("shift+f5"), "Shift+F5")
        for bad in ("E", "Ctrl+", "Ctrl+Alt+Ç", "Hyper+E"):
            with self.assertRaises(ValueError):
                normalize_hotkey(bad)

    def test_defaults_are_valid_and_unique(self):
        clean, errors = validate_patch({"hotkeys": dict(DEFAULT_HOTKEYS)}, {})
        self.assertEqual(errors, [])
        self.assertEqual(set(clean["hotkeys"]), set(HOTKEY_LABELS))
        self.assertEqual(set(DEFAULT_SETTINGS["hotkeys"]), set(HOTKEY_LABELS))

    def test_duplicate_hotkeys_are_rejected_even_against_the_current_ones(self):
        cur = {"hotkeys": dict(DEFAULT_HOTKEYS)}
        _c, errors = validate_patch({"hotkeys": {"toggle_overlay": "ctrl+alt+e"}}, cur)
        self.assertTrue(any("repetido" in e for e in errors))
        clean, errors = validate_patch({"hotkeys": {"toggle_overlay": ""}}, cur)  # vazio = desligado
        self.assertEqual((clean["hotkeys"]["toggle_overlay"], errors), ("", []))


class TestValidate(unittest.TestCase):
    def test_good_patch(self):
        clean, errors = validate_patch({
            "simulator": "lmu", "update_hz": "60", "ui_hz": 45, "units": "mph", "logo_wordmark": 0,
            "my_country": "Brazil", "visibility": "track",
            "iracing": {"invert_clutch": False},
            "lmu": {"driver_rank": "b2", "safety_rank": " s3 ", "contact_badge": "trusted"}})
        self.assertEqual(errors, [])
        self.assertEqual(clean["simulator"], "lmu")
        self.assertEqual((clean["update_hz"], clean["ui_hz"], clean["units"]), (60, 45, "mph"))
        self.assertIs(clean["logo_wordmark"], False)
        self.assertEqual(clean["my_country"], "br")
        self.assertEqual(clean["lmu"], {"driver_rank": "B2", "safety_rank": "S3", "contact_badge": "Trusted"})
        self.assertEqual(clean["iracing"], {"invert_clutch": False})
        clean2, _ = validate_patch({"iracing": {"live_positions": False}}, DEFAULT_SETTINGS)
        self.assertEqual(clean2["iracing"], {"live_positions": False})
        self.assertTrue(settings_to_patch(DEFAULT_SETTINGS)["iracing"]["live_positions"])

    def test_bad_values_are_reported_and_not_returned(self):
        clean, errors = validate_patch({"simulator": "rfactor", "update_hz": 7, "units": "furlong",
                                        "my_country": "Narnia", "visibility": "x",
                                        "lmu": {"driver_rank": "Z9", "contact_badge": "King"}})
        self.assertEqual(clean, {})
        self.assertEqual(len(errors), 7)

    def test_empty_clears_optional_fields_and_unknown_keys_are_ignored(self):
        clean, errors = validate_patch({"my_country": "", "lmu": {"driver_rank": "", "contact_badge": None},
                                        "senha": "x", "hotkeys": {"inexistente": "Ctrl+Alt+Z"}})
        self.assertEqual(errors, [])
        self.assertEqual(clean, {"my_country": None, "lmu": {"driver_rank": None, "contact_badge": None}})


class TestApply(unittest.TestCase):
    def test_apply_in_place_keeps_sub_dict_identity(self):
        s = load_settings()
        lmu_ref = s["lmu"]  # o provedor guarda esta referência
        changed = apply_patch(s, {"simulator": "demo", "lmu": {"driver_rank": "G1"}, "units": s["units"]})
        self.assertEqual(changed, {"simulator", "lmu"})  # units não mudou
        self.assertIs(s["lmu"], lmu_ref)
        self.assertEqual(lmu_ref["driver_rank"], "G1")

    def test_initial_patch_round_trips(self):
        s = load_settings()
        clean, errors = validate_patch(settings_to_patch(s), s)
        self.assertEqual(errors, [])
        self.assertEqual(apply_patch(s, clean), set())  # abrir e salvar sem mexer em nada não muda nada


class TestLayoutManagement(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LayoutStore(Path(self.tmp.name) / "layouts")
        self.store.ensure_defaults()

    def tearDown(self):
        self.tmp.cleanup()

    def test_rename_moves_the_file_and_the_active_marker(self):
        self.store.set_active("Treino")
        self.store.rename("Treino", "Meu treino")
        names = self.store.list_names()
        self.assertIn("Meu treino", names)
        self.assertNotIn("Treino", names)
        self.assertEqual(self.store.get_active(), "Meu treino")
        self.assertEqual(self.store.load("Meu treino").name, "Meu treino")

    def test_rename_rejects_existing_and_invalid_names(self):
        with self.assertRaises(ValueError):
            self.store.rename("Treino", "corrida")  # já existe (sem diferenciar maiúsculas)
        with self.assertRaises(ValueError):
            self.store.rename("Treino", "///")
        self.assertIn("Treino", self.store.list_names())  # nada foi perdido

    def test_unique_name(self):
        self.assertEqual(self.store.unique_name("Corrida"), "Corrida (2)")
        self.store.duplicate("Corrida", "Corrida (2)")
        self.assertEqual(self.store.unique_name("Corrida"), "Corrida (3)")

    def test_export_and_import_round_trip_without_overwriting(self):
        out = Path(self.tmp.name) / "meu.json"
        self.store.export_layout("Corrida", out)
        lay = self.store.import_layout(out)
        self.assertEqual(lay.name, "Corrida (2)")  # nunca sobrescreve
        self.assertEqual(self.store.load("Corrida (2)").modules["radar"].rect, preset_corrida().modules["radar"].rect)

    def test_import_rejects_garbage(self):
        bad = Path(self.tmp.name) / "x.json"
        for content in ("não é json", "[1,2]", json.dumps({"name": "x"}), json.dumps({"modules": {}})):
            bad.write_text(content, encoding="utf-8")
            with self.assertRaises(ValueError):
                self.store.import_layout(bad)
        bad.write_text("{" + " " * 1_100_000 + "}", encoding="utf-8")  # grande demais
        with self.assertRaises(ValueError):
            self.store.import_layout(bad)

    def test_import_sanitizes_values(self):
        out = Path(self.tmp.name) / "evil.json"
        data = preset_corrida().to_dict()
        data["name"] = "../../Evil"
        data["modules"]["radar"]["rect"] = [9, "x", None, float("nan")]
        out.write_text(json.dumps(data), encoding="utf-8")
        lay = self.store.import_layout(out)
        self.assertNotIn("/", lay.name)
        self.assertTrue(all(0 <= v <= 1 for v in lay.modules["radar"].rect))
        self.assertTrue((self.store.dir / f"{lay.name.replace(' ', '_')}.json").exists())


if __name__ == "__main__":
    unittest.main()


class TestAssetFolders(unittest.TestCase):
    def test_everything_lives_in_dados_and_legacy_files_are_copied(self):
        import os
        from unittest import mock
        from kerbhud.core import paths
        with tempfile.TemporaryDirectory() as cfg, tempfile.TemporaryDirectory() as root:
            (Path(cfg) / "logos").mkdir()
            (Path(cfg) / "logos" / "bmw.png").write_bytes(b"1")
            (Path(cfg) / "logos" / "audi.png").write_bytes(b"2")
            (Path(cfg) / "layouts").mkdir()
            (Path(cfg) / "layouts" / "Corrida.json").write_text("{}")
            (Path(cfg) / "state.json").write_text('{"active_layout": "Corrida"}')
            (Path(root) / "flags").mkdir()  # 0.13.0: pastas na raiz
            (Path(root) / "flags" / "br.png").write_bytes(b"F")
            env = {k: v for k, v in os.environ.items() if k != "KERBHUD_HOME"}
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(paths, "app_root", lambda: Path(root)), \
                    mock.patch.object(paths, "config_dir", lambda: Path(cfg)), \
                    mock.patch.object(paths, "legacy_config_dir", lambda: None), \
                    mock.patch.object(paths, "legacy_app_dirs", lambda: []):  # isolado do PC de quem roda o teste
                (Path(root) / "dados" / "logos").mkdir(parents=True)
                (Path(root) / "dados" / "logos" / "bmw.png").write_bytes(b"NOVO")  # já existe: não sobrescreve
                for n in ("logos", "flags", "badges", "layouts", "tracks"):
                    self.assertEqual(getattr(paths, n + "_dir")(), Path(root) / "dados" / n)
                self.assertEqual(paths.migrate_legacy_assets(), ["logos (1)", "flags (1)", "layouts (1)"])
                d = Path(root) / "dados"
                self.assertEqual((d / "logos" / "bmw.png").read_bytes(), b"NOVO")
                self.assertEqual((d / "logos" / "audi.png").read_bytes(), b"2")
                self.assertEqual((d / "flags" / "br.png").read_bytes(), b"F")
                self.assertTrue((d / "state.json").exists())
                self.assertTrue((Path(cfg) / "logos" / "audi.png").exists())  # nada é apagado
                self.assertEqual(paths.migrate_legacy_assets(), [])  # idempotente

    def test_kerbhud_home_keeps_everything_together(self):
        import os
        from unittest import mock
        from kerbhud.core import paths
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"KERBHUD_HOME": d}):
            self.assertEqual(paths.app_root(), Path(d))
            self.assertEqual(paths.layouts_dir(), Path(d) / "dados" / "layouts")
            self.assertEqual(paths.migrate_legacy_assets(), [])


class TestUpdateSettings(unittest.TestCase):
    def test_update_repo_is_validated_and_normalised(self):
        for raw, want in (("alex/KerbHUD", "alex/KerbHUD"), ("https://github.com/alex/KerbHUD.git", "alex/KerbHUD"),
                          ("https://github.com/alex/KerbHUD/", "alex/KerbHUD"), ("", "")):
            clean, errors = validate_patch({"update_repo": raw})
            self.assertEqual((errors, clean["update_repo"]), ([], want), raw)
        for bad in ("alex", "../x", "https://evil.com/a/b", "a/b/c"):
            clean, errors = validate_patch({"update_repo": bad})
            self.assertTrue(errors and "update_repo" not in clean, bad)
        clean, _ = validate_patch({"check_updates_on_start": 0})
        self.assertIs(clean["check_updates_on_start"], False)


class TestAppId(unittest.TestCase):
    def test_app_user_model_id_is_harmless_off_windows(self):
        from kerbhud.core import winapi
        self.assertIn(winapi.set_app_user_model_id("KerbHUD.App"), (True, False))


class TestShellDetection(unittest.TestCase):
    def test_shell_classes(self):
        from kerbhud.core import winapi
        for c in ("Shell_TrayWnd", "NotifyIconOverflowWindow", "#32768", "Windows.UI.Core.CoreWindow"):
            self.assertTrue(winapi.is_shell_class(c), c)
        for c in ("", "LMU_Window", "CabinetWClass", "SDL_app"):
            self.assertFalse(winapi.is_shell_class(c), c)
        self.assertFalse(winapi.shell_has_focus())  # fora do Windows


class TestRenameMigration(unittest.TestCase):
    def test_settings_and_data_of_the_old_name_are_carried_over(self):
        import os
        from unittest import mock
        from kerbhud.core import paths
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            old_cfg = home / "cfg" / "simoverlay"
            (old_cfg).mkdir(parents=True)
            (old_cfg / "settings.json").write_text('{"units": "mph"}')
            (old_cfg / "layouts").mkdir()
            (old_cfg / "layouts" / "Corrida.json").write_text("{}")
            old_app = home / "apps" / "simoverlay-0.16.0"
            (old_app / "dados" / "logos").mkdir(parents=True)
            (old_app / "dados" / "logos" / "bmw.png").write_bytes(b"1")
            new_app = home / "apps" / "kerbhud-0.17.0"
            (new_app / "src" / "kerbhud").mkdir(parents=True)
            new_cfg = home / "cfg" / "kerbhud"
            new_cfg.mkdir(parents=True)
            env = {k: v for k, v in os.environ.items() if k not in ("KERBHUD_HOME", "SIMOVERLAY_HOME")}
            # tudo apontado para a pasta temporária (no Windows o código usaria %APPDATA%; o teste não pode tocar nele)
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(paths, "app_root", lambda: new_app), \
                    mock.patch.object(paths, "config_dir", lambda: new_cfg), \
                    mock.patch.object(paths, "legacy_config_dir", lambda: old_cfg):
                self.assertEqual(paths.migrate_legacy_config(), ["settings.json"])
                self.assertEqual((home / "cfg" / "kerbhud" / "settings.json").read_text(), '{"units": "mph"}')
                moved = paths.migrate_legacy_assets()
                self.assertIn("logos (1)", moved)
                self.assertIn("layouts (1)", moved)
                self.assertTrue((new_app / "dados" / "logos" / "bmw.png").exists())
                self.assertEqual(paths.migrate_legacy_config(), [])  # não sobrescreve
                self.assertEqual(paths.migrate_legacy_assets(), [])
                self.assertTrue((old_app / "dados" / "logos" / "bmw.png").exists())  # a cópia antiga fica intacta
