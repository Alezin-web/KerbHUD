import json
import os
import tempfile
import unittest
from pathlib import Path

from kerbhud.core.engine import DEFAULT_SETTINGS, Engine, load_settings
from kerbhud.core.layout import (
    FIXED_SCALE_MODULES, LEGIBLE_WIDTH, MODULES, PRESETS, SCHEMA_VERSION, design_size, fit_height, migrate_layout,
    natural_scale, Layout, LayoutStore, ModuleState, ScreenInfo, compute_drag, hit_test,
    pixels_to_rect, rect_to_pixels, scale_about_topleft, slug, snap,
)
from kerbhud.core.winapi import HotkeyRegistry, MOD_ALT, MOD_CONTROL, MOD_SHIFT, parse_hotkey
from kerbhud.providers.demo import DemoProvider

FHD = ScreenInfo("DP-1", 0, 0, 1920, 1080)
SIDE = ScreenInfo("DP-2", 1920, 0, 2560, 1440)


class TestGeometry(unittest.TestCase):
    def test_roundtrip_fraction_pixels(self):
        st = ModuleState(rect=(0.25, 0.5, 0.2, 0.1), screen="DP-1")
        px = rect_to_pixels(st, MODULES["inputs"], [FHD, SIDE], "DP-1")
        self.assertEqual(px, (480, 540, 384, 108))
        rect, scr = pixels_to_rect(px, [FHD, SIDE])
        self.assertEqual(scr, "DP-1")
        for a, b in zip(rect, st.rect):
            self.assertAlmostEqual(a, b, places=3)

    def test_second_monitor_offset(self):
        st = ModuleState(rect=(0.5, 0.5, 0.25, 0.25), screen="DP-2")
        x, y, w, h = rect_to_pixels(st, MODULES["trackmap"], [FHD, SIDE], "DP-1")
        self.assertEqual((x, y, w, h), (1920 + 1280, 720, 640, 360))
        _, scr = pixels_to_rect((x, y, w, h), [FHD, SIDE])
        self.assertEqual(scr, "DP-2")

    def test_missing_screen_falls_back_to_primary_and_stays_visible(self):
        st = ModuleState(rect=(0.9, 0.9, 0.3, 0.3), screen="GONE")
        x, y, w, h = rect_to_pixels(st, MODULES["standings"], [FHD], "DP-1")
        self.assertTrue(0 <= x and x + w <= 1920 and 0 <= y and y + h <= 1080)

    def test_min_size_enforced(self):
        st = ModuleState(rect=(0.0, 0.0, 0.001, 0.001))
        _, _, w, h = rect_to_pixels(st, MODULES["standings"], [FHD], None)
        self.assertEqual((w, h), (MODULES["standings"].min_w, MODULES["standings"].min_h))

    def test_snap_and_drag(self):
        self.assertEqual(snap(13), 16)
        self.assertEqual(snap(11), 8)
        # mover
        self.assertEqual(compute_drag("move", (100, 100, 200, 100), 13, 5, (50, 50), 8), (112, 104, 200, 100))
        self.assertEqual(compute_drag("move", (100, 100, 200, 100), 13, 5, (50, 50), None), (113, 105, 200, 100))
        # redimensionar canto inferior direito
        self.assertEqual(compute_drag("br", (100, 100, 200, 100), 50, 30, (50, 50), None), (100, 100, 250, 130))
        # borda esquerda respeita tamanho mínimo e mantém a borda direita fixa
        x, y, w, h = compute_drag("l", (100, 100, 200, 100), 190, 0, (120, 50), None)
        self.assertEqual((x + w, w), (300, 120))
        # borda superior
        x, y, w, h = compute_drag("t", (100, 100, 200, 100), 0, 500, (50, 40), None)
        self.assertEqual((y + h, h), (200, 40))

    def test_wheel_scale_keeps_aspect_and_min(self):
        x, y, w, h = scale_about_topleft((10, 20, 200, 100), 1.1, (50, 50))
        self.assertEqual((x, y, w, h), (10, 20, 220, 110))
        _, _, w, h = scale_about_topleft((0, 0, 200, 100), 0.1, (150, 80))
        self.assertGreaterEqual(w, 150)
        self.assertGreaterEqual(h, 80)
        self.assertAlmostEqual(w / h, 2.0, places=1)

    def test_hit_test(self):
        self.assertEqual(hit_test(50, 50, 200, 100), "move")
        self.assertEqual(hit_test(2, 50, 200, 100), "l")
        self.assertEqual(hit_test(198, 98, 200, 100), "br")
        self.assertEqual(hit_test(100, 1, 200, 100), "t")


class TestLayoutModel(unittest.TestCase):
    def test_four_presets_valid_and_distinct(self):
        names = [m().name for m in PRESETS]
        self.assertEqual(names, ["Corrida", "Treino", "Telemetria", "Broadcast"])
        for make in PRESETS:
            lay = make()
            self.assertEqual(set(lay.modules), set(MODULES))
            self.assertTrue(lay.modules["status"].visible)
            for st in lay.modules.values():
                fx, fy, fw, fh = st.rect
                self.assertTrue(0 <= fx and fx + fw <= 1.0001 and 0 <= fy and fy + fh <= 1.0001, (lay.name, st.rect))
        # presets realmente diferem na visibilidade
        vis = {m().name: tuple(s.visible for s in m().modules.values()) for m in PRESETS}
        self.assertEqual(len(set(vis.values())), 4)

    def test_dict_roundtrip(self):
        lay = PRESETS[2]()
        again = Layout.from_dict(json.loads(json.dumps(lay.to_dict())))
        self.assertEqual(again.to_dict(), lay.to_dict())

    def test_from_dict_sanitizes_garbage(self):
        bad = {"name": "X", "modules": {
            "inputs": {"visible": True, "rect": [5, -3, 9, "x"], "opacity": 99},
            "trackmap": {"rect": [float("nan"), 0, 0.2, 0.2]},
            "naoexiste": {"rect": [0, 0, 1, 1]},
        }}
        lay = Layout.from_dict(bad)
        self.assertEqual(set(lay.modules), set(MODULES))  # completa os faltantes
        self.assertNotIn("naoexiste", lay.modules)
        for st in lay.modules.values():
            fx, fy, fw, fh = st.rect
            self.assertTrue(0 <= fx <= 1 and 0 <= fy <= 1 and 0 < fw <= 1 and 0 < fh <= 1)
            self.assertTrue(0.1 <= st.opacity <= 1.0)
        with self.assertRaises(ValueError):
            Layout.from_dict({"modules": {}})


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = LayoutStore(Path(self.tmp.name) / "layouts")

    def tearDown(self):
        self.tmp.cleanup()

    def test_defaults_created_once_and_never_overwrite(self):
        self.store.ensure_defaults()
        self.assertEqual(self.store.list_names(), ["Corrida", "Treino", "Telemetria", "Broadcast"])
        lay = self.store.load("Corrida")
        lay.modules["inputs"].rect = (0.1, 0.1, 0.3, 0.2)
        self.store.save(lay)
        self.store.ensure_defaults()
        self.assertEqual(self.store.load("Corrida").modules["inputs"].rect, (0.1, 0.1, 0.3, 0.2))

    def test_save_load_duplicate_delete_and_order(self):
        self.store.ensure_defaults()
        self.store.duplicate("Treino", "Meu layout")
        self.assertEqual(self.store.list_names()[-1], "Meu layout")
        self.store.delete("Meu layout")
        self.assertNotIn("Meu layout", self.store.list_names())

    def test_reset_defaults_restores_presets_but_keeps_custom(self):
        self.store.ensure_defaults()
        lay = self.store.load("Corrida")
        lay.modules["inputs"].rect = (0.0, 0.0, 0.05, 0.05)
        self.store.save(lay)
        self.store.duplicate("Treino", "Meu")
        self.store.reset_defaults()
        self.assertEqual(self.store.load("Corrida").modules["inputs"].rect, PRESETS[0]().modules["inputs"].rect)
        self.assertIn("Meu", self.store.list_names())

    def test_inputs_presets_match_design_aspect(self):
        spec = MODULES["inputs"]
        design = spec.design_w / spec.design_h
        for make in PRESETS:
            fx, fy, fw, fh = make().modules["inputs"].rect
            aspect = (fw * 1920) / (fh * 1080)
            self.assertAlmostEqual(aspect / design, 1.0, delta=0.05, msg=make().name)

    def test_corrupt_file_is_ignored(self):
        self.store.ensure_defaults()
        (self.store.dir / "quebrado.json").write_text("{ nao e json", encoding="utf-8")
        self.assertEqual(len(self.store.list_names()), 4)

    def test_slug_blocks_path_traversal(self):
        self.assertNotIn("/", slug("../../etc/passwd"))
        self.assertNotIn("..", slug("..\\..\\x"))
        with self.assertRaises(ValueError):
            slug("...")
        with self.assertRaises(ValueError):
            slug("")
        lay = PRESETS[0]()
        lay.name = "../../fora"
        self.store.save(lay)
        self.assertTrue(all(p.parent == self.store.dir for p in self.store.dir.glob("*.json")))

    def test_active_layout_persisted(self):
        self.assertIsNone(self.store.get_active())
        self.store.set_active("Broadcast")
        self.assertEqual(self.store.get_active(), "Broadcast")


class TestLayoutMigration(unittest.TestCase):
    """Layouts salvos antes da Etapa 4e guardam janelas pequenas para módulos que ficaram maiores."""

    def old_layout(self, standings=(0.010, 0.07, 0.340, 0.402), relative=(0.010, 0.54, 0.250, 0.2205)):
        lay = PRESETS[0]()
        lay.modules["standings"].rect = standings
        lay.modules["relative"].rect = relative
        for mid in FIXED_SCALE_MODULES:  # arquivos antigos não têm escala de texto (foi criada na versão 4)
            lay.modules[mid].options.pop("scale", None)
        lay.version = 1
        return lay

    def aspect_ok(self, lay, mid):
        dw, dh = design_size(mid, lay.modules[mid].options)
        fx, fy, fw, fh = lay.modules[mid].rect
        return abs((fw * 1920) / (fh * 1080) / (dw / dh) - 1.0) < 0.01

    def test_small_windows_grow_to_the_legible_size_keeping_position(self):
        lay = self.old_layout(standings=(0.050, 0.100, 0.340, 0.402))
        self.assertTrue(migrate_layout(lay))
        fx, fy, fw, fh = lay.modules["standings"].rect
        self.assertEqual((fx, fy), (0.050, 0.100))  # canto superior esquerdo preservado
        self.assertAlmostEqual(fw, LEGIBLE_WIDTH["standings"])
        self.assertTrue(self.aspect_ok(lay, "standings"))
        self.assertTrue(self.aspect_ok(lay, "relative"))
        self.assertGreaterEqual(lay.modules["relative"].rect[2], LEGIBLE_WIDTH["relative"])
        self.assertEqual(lay.version, SCHEMA_VERSION)

    def test_user_sizes_larger_than_legible_are_kept_and_other_modules_untouched(self):
        lay = self.old_layout(standings=(0.01, 0.01, 0.60, 0.8))
        before_inputs = lay.modules["inputs"].rect
        migrate_layout(lay)
        self.assertAlmostEqual(lay.modules["standings"].rect[2], 0.60)  # não encolhe
        self.assertEqual(lay.modules["inputs"].rect, before_inputs)

    def test_stays_inside_the_screen(self):
        lay = self.old_layout(standings=(0.90, 0.80, 0.34, 0.402))  # perto do canto inferior direito
        migrate_layout(lay)
        fx, fy, fw, fh = lay.modules["standings"].rect
        self.assertLessEqual(fx + fw, 1.0 + 1e-9)
        self.assertLessEqual(fy + fh, 1.0 + 1e-9)
        self.assertGreaterEqual(min(fx, fy), 0.0)

    def test_relative_is_pushed_down_only_if_it_would_overlap(self):
        lay = self.old_layout()  # relative logo abaixo do standings antigo: vai sobrepor o novo
        migrate_layout(lay)
        sx, sy, sw, sh = lay.modules["standings"].rect
        rx, ry, rw, rh = lay.modules["relative"].rect
        self.assertGreaterEqual(ry, sy + sh)  # empurrado para baixo do Standings ampliado
        lay2 = self.old_layout(relative=(0.70, 0.54, 0.25, 0.2205))  # longe horizontalmente
        keep_y = lay2.modules["relative"].rect[1]
        migrate_layout(lay2)
        self.assertEqual(lay2.modules["relative"].rect[1], keep_y)  # sem sobreposição: posição intocada
        lay3 = self.old_layout()
        lay3.modules["relative"].visible = False
        keep = lay3.modules["relative"].rect[1]
        migrate_layout(lay3)
        self.assertEqual(lay3.modules["relative"].rect[1], keep)  # oculto: não mexe

    def test_layout_saved_by_the_previous_version_grows_again(self):
        """v2 (janela de 46%) ficou pequena depois que os nomes completos alargaram o desenho."""
        lay = self.old_layout(standings=(0.01, 0.07, 0.46, 0.5197), relative=(0.01, 0.62, 0.30, 0.2575))
        lay.version = 2
        self.assertTrue(migrate_layout(lay))
        self.assertAlmostEqual(lay.modules["standings"].rect[2], LEGIBLE_WIDTH["standings"])
        self.assertAlmostEqual(lay.modules["relative"].rect[2], LEGIBLE_WIDTH["relative"])
        self.assertTrue(self.aspect_ok(lay, "standings"))
        self.assertEqual(lay.version, SCHEMA_VERSION)

    # ---- versão 4: texto de tamanho fixo ----
    def test_migration_records_the_current_text_scale_so_nothing_changes(self):
        lay = self.old_layout(standings=(0.010, 0.07, 0.53, 0.5231))
        lay.modules["inputs"].rect = (0.36, 0.88, 0.28, 0.09)
        lay.version = 3
        self.assertTrue(migrate_layout(lay))
        for mid in FIXED_SCALE_MODULES:
            st = lay.modules[mid]
            self.assertAlmostEqual(st.options["scale"], natural_scale(mid, st.rect, st.options), places=8)
            # px reais por unidade de desenho (tela 1920x1080): igual ao do modo antigo "ajustar à janela"
            dw, dh = design_size(mid, st.options)
            fx, fy, fw, fh = st.rect
            old_fit = min(fw * 1920 / dw, fh * 1080 / dh)
            self.assertAlmostEqual(st.options["scale"] * 1920, old_fit, places=5, msg=mid)
        self.assertEqual(lay.version, SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION, 4)

    def test_existing_scale_is_never_overwritten_and_other_modules_get_none(self):
        lay = self.old_layout()
        lay.modules["standings"].options["scale"] = 0.0007  # escolhido pelo usuário
        migrate_layout(lay)
        self.assertEqual(lay.modules["standings"].options["scale"], 0.0007)
        for mid in ("relative", "telemetry", "trackmap", "status"):
            self.assertNotIn("scale", lay.modules[mid].options)  # só Standings e Inputs têm texto fixo

    def test_all_presets_carry_the_text_scale_that_matches_their_window(self):
        for make in PRESETS:
            lay = make()
            for mid in FIXED_SCALE_MODULES:
                st = lay.modules[mid]
                self.assertIn("scale", st.options, f"{lay.name}/{mid}")
                self.assertAlmostEqual(st.options["scale"], natural_scale(mid, st.rect, st.options), places=8)
                self.assertGreater(st.options["scale"], 0)

    def test_scale_survives_save_and_load(self):
        with tempfile.TemporaryDirectory() as d:
            store = LayoutStore(Path(d) / "layouts")
            store.ensure_defaults()
            lay = store.load("Corrida")
            lay.modules["standings"].options["scale"] = 0.00061
            store.save(lay)
            self.assertAlmostEqual(store.load("Corrida").modules["standings"].options["scale"], 0.00061)

    def test_runs_once_and_current_layouts_are_untouched(self):
        lay = self.old_layout()
        self.assertTrue(migrate_layout(lay))
        again = lay.to_dict()
        self.assertFalse(migrate_layout(lay))
        self.assertEqual(lay.to_dict(), again)
        fresh = PRESETS[0]()
        self.assertEqual(fresh.version, SCHEMA_VERSION)
        before = fresh.to_dict()
        self.assertFalse(migrate_layout(fresh))
        self.assertEqual(fresh.to_dict(), before)

    def test_store_load_migrates_old_file_and_persists(self):
        with tempfile.TemporaryDirectory() as d:
            store = LayoutStore(Path(d) / "layouts")
            old = self.old_layout()
            old.name = "Corrida"
            path = store.dir / "Corrida.json"
            path.write_text(json.dumps(old.to_dict()), encoding="utf-8")  # arquivo no formato antigo (version 1)
            self.assertEqual(json.loads(path.read_text())["version"], 1)
            lay = store.load("Corrida")
            self.assertEqual(lay.version, SCHEMA_VERSION)
            self.assertAlmostEqual(lay.modules["standings"].rect[2], LEGIBLE_WIDTH["standings"])
            self.assertEqual(json.loads(path.read_text())["version"], SCHEMA_VERSION)  # gravado migrado
            self.assertEqual(store.load("Corrida").to_dict(), lay.to_dict())  # segunda leitura não muda nada

    def test_effective_text_size_improves_for_old_layouts(self):
        """O motivo da migração: com a janela antiga o texto quase não crescia; agora cresce de verdade."""
        from kerbhud.core.standings import NAME_FONT_PX
        old = self.old_layout()
        fw_old = old.modules["standings"].rect[2]
        dw, dh = design_size("standings", {})
        scale_old = fw_old * 1920 / dw
        migrate_layout(old)
        scale_new = old.modules["standings"].rect[2] * 1920 / dw
        self.assertLess(NAME_FONT_PX * scale_old, 13.0)  # sem migrar: ~11 px (parecia "a mesma coisa")
        self.assertGreater(NAME_FONT_PX * scale_new, 15.5)  # migrado: texto bem maior

    def test_fit_height_matches_design_aspect(self):
        h = fit_height("standings", 0.46, {})
        dw, dh = design_size("standings", {})
        self.assertAlmostEqual((0.46 * 1920) / (h * 1080), dw / dh, places=6)


class TestHotkeysAndSettings(unittest.TestCase):
    def test_parse_hotkey(self):
        self.assertEqual(parse_hotkey("Ctrl+Alt+E"), (MOD_CONTROL | MOD_ALT, ord("E")))
        self.assertEqual(parse_hotkey("ctrl+shift+F5"), (MOD_CONTROL | MOD_SHIFT, 0x74))
        self.assertEqual(parse_hotkey("Ctrl+Alt+1"), (MOD_CONTROL | MOD_ALT, ord("1")))
        self.assertEqual(parse_hotkey("Alt+Space")[1], 0x20)
        for bad in ("E", "Ctrl+", "Foo+E", "Ctrl+Alt+Banana", "Ctrl+F99"):
            with self.assertRaises(ValueError, msg=bad):
                parse_hotkey(bad)

    def test_default_hotkeys_all_parse(self):
        for action, text in DEFAULT_SETTINGS["hotkeys"].items():
            parse_hotkey(text)

    def test_registry_reports_bad_hotkeys_without_crashing(self):
        reg = HotkeyRegistry()
        reg.register_all({"a": "Banana", "b": ""})
        self.assertEqual(len(reg.errors), 1)

    def test_settings_merge_keeps_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({"update_hz": 30, "hotkeys": {"toggle_edit": "Ctrl+Shift+E"}}), encoding="utf-8")
            cfg = load_settings(p)
        self.assertEqual(cfg["update_hz"], 30)
        self.assertEqual(cfg["hotkeys"]["toggle_edit"], "Ctrl+Shift+E")
        self.assertEqual(cfg["hotkeys"]["toggle_overlay"], "Ctrl+Alt+H")  # preservado

    def test_engine_switch_simulator_at_runtime(self):
        import time
        cfg = load_settings()
        cfg["simulator"] = "demo"
        eng = Engine(cfg, providers={"demo": DemoProvider(), "iracing": DemoProvider(), "lmu": DemoProvider()})
        eng.start()
        t0 = time.time()
        while time.time() - t0 < 3 and not eng.latest().connected:
            time.sleep(0.02)
        self.assertTrue(eng.latest().is_demo)
        eng.set_simulator("lmu")  # ainda "demo" por trás, mas deve reconectar sem travar
        time.sleep(0.4)
        self.assertTrue(eng.latest().connected)
        eng.stop()
        with self.assertRaises(ValueError):
            eng.set_simulator("xyz")


if __name__ == "__main__":
    unittest.main()
