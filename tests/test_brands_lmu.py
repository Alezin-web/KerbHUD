import unittest


class TestLmuBrandFallback(unittest.TestCase):
    def test_brand_rules_and_lmp2_single_make(self):
        from kerbhud.core.brands import brand_for, brand_for_lmu_class
        self.assertEqual(brand_for("AF Corse #51").key, "ferrari")
        self.assertEqual(brand_for("Manthey EMA #92").key, "porsche")
        self.assertIsNone(brand_for("Vector Sport #10"))
        self.assertEqual(brand_for_lmu_class("LMP2").key, "oreca")
        self.assertEqual(brand_for_lmu_class("LMP2_ELMS").key, "oreca")
        self.assertIsNone(brand_for_lmu_class("GT3"))
        self.assertIsNone(brand_for_lmu_class(None))

    def test_standings_uses_the_class_fallback_only_on_lmu(self):
        from kerbhud.core.model import CarState, SessionState, Sim, Snapshot
        from kerbhud.core.standings import StandingsOptions, build_standings
        def snap(sim):
            c = CarState(idx=0, driver_name="A", position=1, class_position=1, class_name="LMP2",
                         car_number="10", vehicle_raw="Vector Sport #10", laps_completed=2, is_player=True,
                         best_lap=100.0)
            return Snapshot(sim=sim, connected=True, cars=[c], player_idx=0,
                            session=SessionState(active=True, session_type="Race", track_name="X"))
        self.assertEqual(build_standings(snap(Sim.LMU), StandingsOptions()).rows[0].brand.key, "oreca")
        self.assertIsNone(build_standings(snap(Sim.IRACING), StandingsOptions()).rows[0].brand)


class TestAdessCar(unittest.TestCase):
    def test_adess_is_a_car_brand(self):
        from kerbhud.core.brands import brand_for
        for text in ("Adess AD25 #5", "ADESS-03 Evo", "Algarve Pro Racing Adess-03"):
            b = brand_for(text)
            self.assertEqual(b.key, "adess", text)
        self.assertNotEqual(getattr(brand_for("Ligier JS P320"), "key", None), "adess")


class TestLmuRealNames(unittest.TestCase):
    """Nomes reais lidos do LMU (diagnóstico de um treino em Silverstone)."""
    DKR3 = "DKR Engineering #3:ELMS26 3_26_DKR_E72469578"
    DKR4 = "DKR Engineering #4:ELMS25 4_25_DKR_E8E7FBE8C"

    def tearDown(self):
        from kerbhud.core.brands import set_overrides
        set_overrides([])

    def test_nothing_in_the_name_cites_a_maker_so_it_is_not_guessed(self):
        from kerbhud.core.brands import brand_for_car
        self.assertEqual(brand_for_car(None, self.DKR4, "Group22", "LMP3", "lmu").key, "ginetta")  # pela tabela de equipes
        self.assertIsNone(brand_for_car(None, "Equipe Fora da Tabela 2026 #7:WEC 7_X", "Group22", "LMP3", "lmu"))
        self.assertEqual(brand_for_car(None, "Iron Lynx 2026 #79:Spa 79_26_IRON66566848", "Group13", "GT3", "lmu").key,
                         "mercedes")  # pela tabela de equipes

    def test_lmp2_elms_is_oreca_by_class(self):
        from kerbhud.core.brands import brand_for_car
        self.assertEqual(brand_for_car(None, self.DKR3, "Group1", "LMP2_ELMS", "lmu").key, "oreca")

    def test_user_rules_by_team_and_class(self):
        from kerbhud.core.brands import brand_for_car, set_overrides
        n = set_overrides([{"match": "dkr engineering", "class": "LMP3", "brand": "adess"},
                           {"match": "Iron Lynx", "brand": "lamborghini"},
                           {"match": "x", "brand": "marca-que-nao-existe"}, "lixo", {"brand": "adess"}])
        self.assertEqual(n, 2)  # só as válidas
        self.assertEqual(brand_for_car(None, self.DKR4, None, "LMP3", "lmu").key, "adess")
        self.assertEqual(brand_for_car(None, self.DKR3, None, "LMP2_ELMS", "lmu").key, "oreca")  # outra classe: não vale
        self.assertEqual(brand_for_car(None, "Iron Lynx 2024 #60:LM", None, "GT3", "lmu").key, "lamborghini")

    def test_overrides_file_is_created_and_read(self):
        import json, tempfile
        from pathlib import Path
        from kerbhud.core.brands import brand_for_car, load_overrides_file
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "brand_overrides.json"
            self.assertEqual(load_overrides_file(f), 0)
            self.assertTrue(f.exists())
            data = json.loads(f.read_text(encoding="utf-8"))
            data["rules"].append({"match": "United Autosports", "class": "GT3", "brand": "mclaren"})
            f.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(load_overrides_file(f), 1)
            self.assertEqual(brand_for_car(None, "United Autosports 2026 #23:x", None, "GT3", "lmu").key, "mclaren")
            f.write_text("{quebrado", encoding="utf-8")
            self.assertEqual(load_overrides_file(f), 0)  # arquivo inválido não derruba o app

    def test_online_id_suffix_is_removed_from_names(self):
        from kerbhud.providers.lmu import _clean_name
        self.assertEqual(_clean_name("Denis Golubev#8275"), "Denis Golubev")
        self.assertEqual(_clean_name("youcef bacha"), "youcef bacha")
        self.assertEqual(_clean_name("Ana #12"), "Ana #12")  # número curto não é código online
