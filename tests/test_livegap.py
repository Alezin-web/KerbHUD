"""Int/Gap ao vivo, LED do iRacing e picos de redução."""
import unittest

from kerbhud.core.history import TelemetryHistory
from kerbhud.core.livegap import live_gaps
from kerbhud.core.model import CarState, Inputs, Sim, Snapshot
from kerbhud.core.viewmodel import shift_lights


def car(idx, pos, laps, pct, cls="A", lap=100.0):
    return CarState(idx=idx, position=pos, class_name=cls, laps_completed=laps, lap_dist_pct=pct, est_lap_time=lap)


class LiveGapTest(unittest.TestCase):
    def test_gap_follows_track_position_each_read(self):
        est = {1: 50.0, 2: 45.0}
        a = [car(1, 1, 3, 0.50), car(2, 2, 3, 0.45)]
        g = live_gaps(a, est.get)
        self.assertAlmostEqual(g[2][1], 5.0)
        est = {1: 50.0, 2: 40.0}  # um instante depois o de trás ficou mais longe: o gap muda sem cruzar a linha
        a = [car(1, 1, 3, 0.50), car(2, 2, 3, 0.40)]
        self.assertAlmostEqual(live_gaps(a, est.get)[2][1], 10.0)

    def test_leader_zero_and_cumulative_and_class_relative(self):
        est = {1: 50.0, 2: 45.0, 3: 30.0, 9: 10.0}
        cars = [car(1, 1, 3, 0.5), car(2, 2, 3, 0.45), car(3, 3, 3, 0.3), car(9, 4, 3, 0.1, cls="B")]
        g = live_gaps(cars, est.get)
        self.assertEqual(g[1], (0.0, None))
        self.assertAlmostEqual(g[3][0], 20.0)
        self.assertEqual(g[9], (0.0, None))  # líder da outra classe

    def test_lapped_car_and_line_crossing(self):
        est = {1: 2.0, 2: 98.0}  # o líder acabou de cruzar a linha; o outro está para cruzar (uma volta atrás em contagem)
        g = live_gaps([car(1, 1, 4, 0.02), car(2, 2, 3, 0.98)], est.get)
        self.assertAlmostEqual(g[2][1], 4.0)

    def test_without_est_time_uses_lap_fraction_and_without_lap_time_nothing(self):
        g = live_gaps([car(1, 1, 3, 0.5), car(2, 2, 3, 0.4)], lambda i: None)
        self.assertAlmostEqual(g[2][1], 10.0)
        self.assertEqual(live_gaps([car(1, 1, 3, 0.5, lap=None), car(2, 2, 3, 0.4, lap=None)], lambda i: None), {})


class ShiftBlinkTest(unittest.TestCase):
    def test_game_blink_overrides_threshold(self):
        self.assertEqual(shift_lights(0.5, "sim", 12, blink=True), (6, True))
        self.assertEqual(shift_lights(1.0, "sim", 12, blink=False), (12, False))
        self.assertTrue(shift_lights(1.0, "sim", 12)[1])


class DownshiftTest(unittest.TestCase):
    def _snap(self, gear, thr):
        return Snapshot(sim=Sim.DEMO, connected=True, inputs=Inputs(throttle=thr, gear=gear))

    def test_blip_after_downshift_is_marked_and_expires(self):
        h = TelemetryHistory()
        h.on_snapshot(self._snap(4, 0.0), now=0.0)
        h.on_snapshot(self._snap(3, 0.6), now=0.1)
        h.on_snapshot(self._snap(3, 0.0), now=0.2)  # sem acelerador: não marca
        h.on_snapshot(self._snap(3, 0.7), now=2.0)  # fora da janela
        flags = [s.down for s in h.window(10.0)]
        self.assertEqual(flags, [False, True, False, False])

    def test_upshift_is_not_a_downshift(self):
        h = TelemetryHistory()
        h.on_snapshot(self._snap(3, 0.9), now=0.0)
        h.on_snapshot(self._snap(4, 0.9), now=0.1)
        self.assertFalse(any(s.down for s in h.window(10.0)))


if __name__ == "__main__":
    unittest.main()


class ShiftLearnTest(unittest.TestCase):
    def test_learns_from_full_throttle_upshifts(self):
        from kerbhud.core.shiftlearn import ShiftLearner
        s = ShiftLearner()
        self.assertEqual(s.reference(8000.0), 8000.0)  # ainda não aprendeu: RPM máximo
        t = 0.0
        for g in (2, 3, 4):  # sobe até 7200 com acelerador a fundo e troca
            for r in (6800, 7000, 7200):
                t += 0.1
                s.observe(g, r, 1.0, 8000.0, t)
            t += 0.1
            s.observe(g + 1, 5600, 1.0, 8000.0, t)
        self.assertEqual(s.reference(8000.0), 7200)
        s.observe(5, 8100, 1.0, 8000.0, t + 0.1)
        self.assertLessEqual(s.reference(8000.0), 8000.0)

    def test_ignores_early_or_part_throttle_shifts_and_resets_on_new_car(self):
        from kerbhud.core.shiftlearn import ShiftLearner
        s = ShiftLearner()
        s.observe(2, 5000, 1.0, 8000.0, 0.0); s.observe(3, 3500, 1.0, 8000.0, 0.1)  # troca precoce
        s.observe(3, 7500, 0.4, 8000.0, 1.0); s.observe(4, 6000, 0.4, 8000.0, 1.1)  # acelerador parcial
        self.assertEqual(s.reference(8000.0), 8000.0)
        for k, g in enumerate((2, 3, 4)):
            s.observe(g, 7000, 1.0, 8000.0, 2.0 + k); s.observe(g + 1, 5000, 1.0, 8000.0, 2.05 + k)
        self.assertEqual(s.reference(8000.0), 7000)
        s.observe(2, 9000, 1.0, 10000.0, 9.0)  # outro carro (RPM máximo muda)
        self.assertEqual(s.reference(10000.0), 10000.0)
