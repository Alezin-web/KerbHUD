import math
import tempfile
import unittest
from pathlib import Path

from kerbhud.core.damage import damage_view, format_seconds
from kerbhud.core.fuel import FuelTracker, format_amount, get_reserve
from kerbhud.core.model import (CarDamage, CarState, CarStatus, FuelState, Inputs, SessionState, Sim,
                                   Snapshot)
from kerbhud.core.trackmap import BINS, TrackRecorder, TrackShape, TrackStore, map_cars, track_key


def circle(pct, r=500.0):
    t = 2 * math.pi * pct
    return r * math.cos(t), r * math.sin(t)


def snap(pct=0.0, lap=0, fuel=None, energy=None, status=CarStatus.RUNNING, speed=40.0, track="Spa", sim=Sim.LMU,
         laps_total=None, remaining=None, xy=True, last_lap=100.0, damage=None, others=()):
    x, z = circle(pct) if xy else (None, None)
    me = CarState(idx=0, driver_name="me", is_player=True, lap_dist_pct=pct, laps_completed=lap, status=status,
                  world_x=x, world_z=z, energy_pct=energy, last_lap=last_lap, position=1)
    return Snapshot(sim=sim, connected=True, cars=[me, *others], player_idx=0,
                    session=SessionState(active=True, track_name=track, track_length_m=7000.0,
                                         session_type="Race", laps_total=laps_total, time_remaining_s=remaining),
                    inputs=Inputs(speed_ms=speed), fuel=fuel, damage=damage)


class TestTrackRecording(unittest.TestCase):
    def lap(self, rec, **kw):
        for i in range(0, 1601):  # amostragem fina, como a 60 Hz numa volta real
            rec.update(snap(pct=(i / 1600) % 1.0, lap=0, **kw))

    def test_records_a_full_lap_and_saves_it(self):
        with tempfile.TemporaryDirectory() as d:
            rec = TrackRecorder(TrackStore(Path(d)))
            self.assertIsNone(rec.update(snap(pct=0.0)))
            self.lap(rec)
            self.assertIsNotNone(rec.shape)
            self.assertEqual(len(rec.shape.points), BINS)
            x, y = rec.shape.xy_at(0.25)  # norte para cima: y = -z
            self.assertAlmostEqual(x, 0.0, delta=5)
            self.assertAlmostEqual(y, -500.0, delta=5)
            # nova sessão (outro objeto) já recebe o traçado salvo, sem gravar
            rec2 = TrackRecorder(TrackStore(Path(d)))
            self.assertIsNotNone(rec2.update(snap(pct=0.5)))

    def test_does_not_record_in_pits_slow_or_without_xy(self):
        rec = TrackRecorder()
        for i in range(0, 1601):
            rec.update(snap(pct=(i / 1600) % 1.0, status=CarStatus.PITS))
            rec.update(snap(pct=(i / 1600) % 1.0, speed=1.0))
            rec.update(snap(pct=(i / 1600) % 1.0, xy=False))
        self.assertIsNone(rec.shape)
        self.assertEqual(rec.progress, 0.0)

    def test_pit_lane_over_the_start_straight_does_not_block_the_map(self):
        # box ao longo da reta de largada (ex.: Navarra): com 97% exigidos, o traçado nunca ficava pronto
        for pit_from, pit_to in ((0.97, 0.03), (0.94, 0.07), (0.90, 0.10)):
            rec = TrackRecorder()
            for i in range(0, 3001):
                pct = (i / 3000) % 1.0
                in_pit = pct >= pit_from or pct < pit_to
                rec.update(snap(pct=pct, status=CarStatus.PITS if in_pit else CarStatus.RUNNING, speed=20.0 if in_pit else 60.0))
            self.assertIsNotNone(rec.shape, (pit_from, pit_to))

    def test_unrecorded_pit_stretch_is_filled_by_the_next_lap_on_the_straight(self):
        rec = TrackRecorder()
        for i in range(0, 3001):  # volta 1: saiu dos boxes parado em 5%..6%; buraco de 11% sem nenhuma amostra
            pct = (i / 3000) % 1.0
            in_pit = pct >= 0.95 or pct < 0.06
            rec.update(snap(pct=pct, status=CarStatus.PITS if in_pit else CarStatus.RUNNING, speed=1.0 if in_pit else 60.0))
        self.assertIsNone(rec.shape)  # não aceita buraco: um mapa com 11% inventado seria pior que esperar
        self.assertAlmostEqual(rec.progress, 0.89, delta=0.01)
        for i in range(0, 3001):  # volta 2: passa pela reta de verdade
            rec.update(snap(pct=(i / 3000) % 1.0, speed=60.0))
        self.assertIsNotNone(rec.shape)

    def test_pit_lane_alone_never_makes_a_map(self):
        rec = TrackRecorder()
        for i in range(0, 3001):
            rec.update(snap(pct=(i / 3000) % 1.0, status=CarStatus.PITS, speed=20.0))
        self.assertIsNone(rec.shape)

    def test_too_big_a_gap_is_not_accepted(self):
        rec = TrackRecorder()
        for i in range(0, 3001):
            pct = (i / 3000) % 1.0
            rec.update(snap(pct=pct, status=CarStatus.RUNNING if 0.2 <= pct < 0.9 else CarStatus.OUT, speed=60.0))
        self.assertIsNone(rec.shape)  # só 70% da volta tem dado

    def test_discarded_laps_are_counted_so_the_module_can_say_so(self):
        rec = TrackRecorder()
        for i in range(0, 1601):
            pct = (i / 1600) % 1.0
            x, z = circle(pct)
            s = snap(pct=pct)
            s.cars[0].world_x, s.cars[0].world_z = x + i, z
            rec.update(s)
        self.assertGreaterEqual(rec.discards, 1)
        rec.reset(forget_saved=True)
        self.assertEqual(rec.discards, 0)

    def test_progress_and_reset_on_new_track(self):
        rec = TrackRecorder()
        for i in range(0, 100):
            rec.update(snap(pct=i / 400))
        self.assertGreater(rec.progress, 0.2)
        rec.update(snap(pct=0.1, track="Monza"))
        self.assertEqual(rec.progress, 0.0 + 1 / BINS)  # recomeçou na pista nova

    def test_dirty_lap_is_discarded(self):
        rec = TrackRecorder()
        for i in range(0, 1601):  # volta que não fecha: termina longe de onde começou
            pct = (i / 1600) % 1.0
            x, z = circle(pct)
            s = snap(pct=pct)
            s.cars[0].world_x, s.cars[0].world_z = x + (i * 1.0), z  # deriva de 1600 m
            rec.update(s)
        self.assertIsNone(rec.shape)

    def test_bad_saved_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            store = TrackStore(Path(d))
            (Path(d) / f"{track_key(snap())}.json").write_text("{lixo", encoding="utf-8")
            self.assertIsNone(store.load(track_key(snap())))

    def test_map_cars_uses_real_xy_else_percentage(self):
        shape = TrackShape("k", "n", [(circle(i / BINS)[0], -circle(i / BINS)[1]) for i in range(BINS)])
        gps = CarState(idx=1, driver_name="a", lap_dist_pct=0.25, world_x=1.0, world_z=2.0)
        pct_only = CarState(idx=2, driver_name="b", lap_dist_pct=0.5)
        pit = CarState(idx=3, driver_name="c", lap_dist_pct=0.1, status=CarStatus.PITS)
        out = CarState(idx=4, driver_name="d", lap_dist_pct=0.1, status=CarStatus.OUT)
        gone = CarState(idx=5, driver_name="e", lap_dist_pct=0.1, in_session=False)
        mc = {m.car.idx: m for m in map_cars(snap(others=[gps, pct_only, pit, out, gone]), shape)}
        self.assertEqual((mc[1].x, mc[1].y), (1.0, -2.0))
        self.assertAlmostEqual(mc[2].x, -500.0, delta=2)
        self.assertFalse(mc[3].on_track)
        self.assertNotIn(4, mc)
        self.assertNotIn(5, mc)


class TestFuel(unittest.TestCase):
    def run_laps(self, tracker, laps, start=60.0, per_lap=3.0, **kw):
        level, v = start, None
        for lap in range(laps + 1):
            for pct in (0.1, 0.5, 0.9):
                v = tracker.update(snap(pct=pct, lap=lap, fuel=FuelState(level - per_lap * pct, 80.0), **kw))
            level -= per_lap
        return v

    def test_measures_consumption_and_computes_laps_and_add(self):
        t = FuelTracker()
        v = self.run_laps(t, 4, laps_total=20)
        m = v.fuel
        self.assertAlmostEqual(m.per_lap, 3.0, places=1)
        self.assertEqual(m.state, "warn")  # 60 L não chegam para 20 voltas
        self.assertAlmostEqual(m.laps_left, m.level / 3.0, places=1)
        self.assertGreater(m.add, 0)
        self.assertAlmostEqual(v.laps_to_go, 20 - 4 - 0.9, places=2)
        self.assertAlmostEqual(m.need, (v.laps_to_go + 0.5) * 3.0, places=1)

    def test_no_value_before_the_first_clean_lap(self):
        v = FuelTracker().update(snap(fuel=FuelState(50.0, 80.0)))
        self.assertEqual(v.fuel.state, "nodata")
        self.assertIsNone(v.fuel.per_lap)

    def test_lap_with_pit_or_refuel_is_not_averaged(self):
        t = FuelTracker()
        self.run_laps(t, 3)
        before = t.update(snap(pct=0.2, lap=3, fuel=FuelState(30.0, 80.0))).fuel.per_lap
        t.update(snap(pct=0.5, lap=3, fuel=FuelState(30.0, 80.0), status=CarStatus.PITS))
        t.update(snap(pct=0.6, lap=3, fuel=FuelState(75.0, 80.0)))  # reabasteceu
        after = t.update(snap(pct=0.1, lap=4, fuel=FuelState(72.0, 80.0))).fuel
        self.assertAlmostEqual(after.per_lap, before, places=2)  # a volta do box ficou de fora

    def test_new_session_or_lap_reset_restarts(self):
        t = FuelTracker()
        self.run_laps(t, 3)
        self.assertEqual(t.update(snap(lap=0, fuel=FuelState(50, 80), track="Outra")).fuel.state, "nodata")

    def test_time_based_race_and_danger(self):
        t = FuelTracker()
        v = self.run_laps(t, 3, per_lap=3.0, remaining=1000.0, start=14.0)
        self.assertAlmostEqual(v.laps_to_go, 1000 / 100.0 + 0.5, places=2)
        self.assertEqual(v.fuel.state, "danger")  # menos de 1 volta de combustível

    def test_energy_is_measured_like_fuel(self):
        t = FuelTracker()
        level = 100.0
        v = None
        for lap in range(5):
            for pct in (0.1, 0.9):
                v = t.update(snap(pct=pct, lap=lap, energy=level - 8.0 * pct, laps_total=30))
            level -= 8.0
        self.assertAlmostEqual(v.energy.per_lap, 8.0, places=0)
        self.assertIsNone(v.fuel)  # sem FuelState: só a energia

    def test_no_data_and_options(self):
        self.assertEqual(FuelTracker().update(snap()).message, "Sem dados de combustível")
        self.assertEqual(get_reserve({"reserve_laps": 1.0}), 1.0)
        self.assertEqual(get_reserve({"reserve_laps": 7}), 0.5)
        self.assertEqual(format_amount(3.14159, "L"), "3.1 L")
        self.assertEqual(format_amount(42.4, "%"), "42%")
        self.assertEqual(format_amount(None, "L"), "—")


class TestDamage(unittest.TestCase):
    def test_lmu_zones(self):
        v = damage_view(snap(damage=CarDamage(zones=[0, 1, 0, 0, 2, 0, 0, 0], overheating=True)))
        self.assertTrue(v.has_data)
        self.assertEqual((v.worst, v.headline, v.level), (2, "DANO FORTE", "danger"))
        self.assertTrue(v.overheating)

    def test_clean_car_and_detached_part(self):
        ok = damage_view(snap(damage=CarDamage(zones=[0] * 8)))
        self.assertEqual((ok.headline, ok.level), ("SEM DANOS", "ok"))
        det = damage_view(snap(damage=CarDamage(zones=[0] * 8, detached=True)))
        self.assertEqual((det.headline, det.level), ("PEÇA SOLTA", "danger"))

    def test_iracing_repair_times_only(self):
        v = damage_view(snap(damage=CarDamage(repair_required_s=75.0, repair_optional_s=20.0)))
        self.assertIsNone(v.zones)
        self.assertEqual([l for l, _ in v.repair_lines], ["Reparo obrigatório", "Reparo opcional"])
        self.assertEqual((v.headline, v.level), ("REPARO PENDENTE", "danger"))
        opt = damage_view(snap(damage=CarDamage(repair_optional_s=20.0)))
        self.assertEqual(opt.level, "warn")
        self.assertEqual(format_seconds(75), "1:15")

    def test_no_data(self):
        self.assertFalse(damage_view(snap()).has_data)
        self.assertEqual(damage_view(None).message, "Aguardando dados")


if __name__ == "__main__":
    unittest.main()


class TestStage5Layouts(unittest.TestCase):
    def test_fuel_table_has_avg_max_min_and_lap_history(self):
        import time
        from kerbhud.core.fuel import FuelTracker
        from kerbhud.providers.demo import DemoProvider
        d, tr, v = DemoProvider("box"), FuelTracker(), None
        for i in range(280):
            d._t0 = time.monotonic() - i * 0.1
            v = tr.update(d.poll())
        m = v.fuel
        self.assertGreaterEqual(m.max_per_lap, m.per_lap)
        self.assertLessEqual(m.min_per_lap, m.per_lap)
        self.assertTrue(m.history and m.history[0][0] is not None)
        laps, add, finish = m.scenario(m.max_per_lap)
        self.assertGreater(laps, 0)
        self.assertIsNone(m.scenario(None)[0])

    def test_damage_health_starts_at_100_and_drops(self):
        from kerbhud.core.damage import damage_view
        from kerbhud.providers.demo import DemoProvider
        import time
        d = DemoProvider("lmu")
        pct = []
        for t in (1, 8, 14, 20):
            d._t0 = time.monotonic() - t
            pct.append(damage_view(d.poll()).health_pct)
        self.assertEqual(pct[0], 100.0)
        self.assertTrue(pct[0] > pct[1] > pct[2] > pct[3])
        d._t0 = time.monotonic() - 20
        d2 = DemoProvider("box"); d2._t0 = time.monotonic() - 20
        self.assertIsNone(damage_view(d2.poll()).health_pct)  # iRacing: sem regiões, sem percentual inventado
