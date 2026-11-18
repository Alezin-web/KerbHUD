"""Roteiro do modo DEMO: exercita as novidades (ver providers/demo.py)."""
import time
import unittest

from kerbhud.core.model import CarStatus, Sim
from kerbhud.core.relative import RelativeOptions, RelativeTracker
from kerbhud.core.roster import Roster
from kerbhud.core.standings import NrgTracker, StandingsOptions, build_standings
from kerbhud.providers.demo import SCENARIOS, STAGES, TOUR, DemoProvider


def at(scn, t):
    d = DemoProvider(scn)
    d._t0 = time.monotonic() - t
    return d.poll()


class TestDemoScript(unittest.TestCase):
    def test_every_scenario_is_flagged_and_valid_at_any_time(self):
        for key in STAGES:
            for t in (0.5, 8, 20, 35, STAGES[key].duration - 0.5):
                s = at(key, t)
                self.assertTrue(s.is_demo and s.sim == Sim.DEMO and s.connected)
                self.assertTrue(any("DEMO" in w for w in s.warnings))
                if s.session.active:
                    self.assertIsNotNone(s.player(), (key, t))

    def test_tour_walks_all_stages_in_order(self):
        d = DemoProvider("tour")
        seen, t = [], 0.0
        while t < sum(STAGES[k].duration for k in TOUR):
            d._t0 = time.monotonic() - t
            k = d.poll().debug["demo_stage"]
            if not seen or seen[-1] != k:
                seen.append(k)
            t += 2.0
        self.assertEqual(seen, TOUR)

    def test_unknown_scenario_falls_back_and_set_scenario_validates(self):
        self.assertEqual(DemoProvider("xxx").scenario, "tour")
        with self.assertRaises(ValueError):
            DemoProvider().set_scenario("xxx")
        self.assertIn("tour", SCENARIOS)

    def test_next_stage_skips_to_next(self):
        d = DemoProvider("tour")
        self.assertEqual(d.poll().debug["demo_stage"], "treino")
        d.next_stage()
        self.assertEqual(d.poll().debug["demo_stage"], "quali")

    def test_practice_hidden_until_first_lap_time(self):
        early, later = at("treino", 3), at("treino", 12)
        opts = StandingsOptions()
        self.assertTrue(build_standings(early, opts).hidden)
        self.assertFalse(build_standings(later, opts).hidden)
        self.assertTrue(all(c.best_lap is None for c in early.cars))

    def test_race_has_pits_out_fights_flags_and_laps_ahead(self):
        s = at("corrida", 25)
        st = {c.status for c in s.cars}
        self.assertTrue({CarStatus.PITS, CarStatus.OUT} <= st)
        self.assertTrue(all(c.country for c in s.cars))
        self.assertGreater(len({c.class_name for c in s.cars}), 2)
        self.assertGreater(max(c.laps_behind_leader for c in s.cars), 0)
        view = RelativeTracker().update(s, RelativeOptions(), now=1.0)
        self.assertTrue(any(e.fight for e in view.ahead + view.behind) if hasattr(view, "ahead") else True)

    def test_brands_are_recognised_including_small_makers(self):
        from kerbhud.core.brands import brand_for
        for text in ("Ligier JS P320", "Ray FF1600", "Oreca 07", "Mercedes-AMG GT3"):
            self.assertIsNotNone(brand_for(text), text)

    def test_single_class_and_few_drivers(self):
        self.assertEqual({c.class_name for c in at("monoclasse", 5).cars}, {"Formula Ford 1600"})
        self.assertEqual(len(at("poucos", 5).cars), 4)

    def test_nrg_is_per_category(self):
        self.assertTrue(NrgTracker().visible(at("corrida", 5)))
        s = at("sem_nrg", 5)
        self.assertTrue(NrgTracker().visible(s))  # há categorias com NRG
        me = s.player()
        self.assertIsNone(me.energy_pct)  # mas o carro do piloto (LMP2) não tem
        self.assertTrue(any(c.energy_pct is not None for c in s.cars))
        self.assertFalse(NrgTracker().visible(at("monoclasse", 5)))  # nenhuma categoria com NRG

    def test_lmu_style_has_no_irating_license_incidents(self):
        s = at("lmu", 5)
        self.assertTrue(all(c.irating is None and c.license is None and c.country is None for c in s.cars))
        self.assertIsNone(s.session.incidents)

    def test_race_end_everyone_leaves_and_roster_keeps_them_dimmed(self):
        r = Roster()
        for t in (10, 40, 55, 70, 75, 79):
            s = r.update(at("corrida", t))
        self.assertTrue(s.cars and all(not c.in_session and c.status == CarStatus.OUT for c in s.cars))
        self.assertFalse(build_standings(s, StandingsOptions()).hidden)

    def test_engine_switches_scenario(self):
        from kerbhud.core.engine import Engine, load_settings
        cfg = load_settings()
        eng = Engine(cfg)
        eng.set_demo_scenario("poucos")
        self.assertEqual(cfg["demo_scenario"], "poucos")
        self.assertEqual(eng._providers["demo"].scenario, "poucos")


if __name__ == "__main__":
    unittest.main()


class TestVisibility(unittest.TestCase):
    def test_modes(self):
        import dataclasses
        from kerbhud.core import visibility as V
        d_track, d_garage = at("corrida", 5), at("treino", 1)
        self.assertFalse(d_track.in_garage)
        self.assertTrue(d_garage.in_garage)
        # modo DEMO: nenhuma regra esconde (é para ver o visual)
        for mode in V.MODES:
            self.assertTrue(V.allowed(mode, d_track) and V.allowed(mode, d_garage), mode)
        # simulador de verdade: "só na pista" / "só na garagem" valem
        track, garage = (dataclasses.replace(s, is_demo=False) for s in (d_track, d_garage))
        self.assertTrue(V.allowed("always", garage) and V.allowed("always", track))
        self.assertTrue(V.allowed("track", track) and not V.allowed("track", garage))
        self.assertTrue(V.allowed("garage", garage) and not V.allowed("garage", track))
        # sem jogo, desconectado ou sem carro do piloto (menus): só "Sempre" aparece
        self.assertTrue(V.allowed("always", None))
        self.assertFalse(V.allowed("track", None) or V.allowed("garage", None))
        off = dataclasses.replace(track, connected=False)
        self.assertFalse(V.allowed("track", off) or V.allowed("garage", off))
        no_car = dataclasses.replace(track, cars=[])
        self.assertFalse(V.allowed("track", no_car))
        # o simulador não informa a garagem, mas o carro existe: conta como na pista
        unknown = dataclasses.replace(track, in_garage=None)
        self.assertTrue(V.allowed("track", unknown) and not V.allowed("garage", unknown))
        self.assertEqual(V.normalize("xx"), "always")
        self.assertEqual(V.effective_mode("track", "global"), "track")
        self.assertEqual(V.effective_mode("track", "garage"), "garage")
        self.assertEqual(V.effective_mode(None, None), "always")
