import unittest

from kerbhud.core.history import TelemetryHistory, decimate_columns
from kerbhud.core.model import Inputs, Sim, Snapshot
from kerbhud.core import viewmodel as vm


def snap(thr=0.5, brk=0.0, sim=Sim.LMU, connected=True, with_inputs=True):
    inp = Inputs(throttle=thr, brake=brk, speed_ms=50.0, rpm=7000.0, rpm_max=8000.0,
                 steering=-0.25, steering_deg=-135.0, gear=4) if with_inputs else None
    return Snapshot(sim=sim, connected=connected, inputs=inp)


class TestHistory(unittest.TestCase):
    def test_append_and_window_anchored_to_last_sample(self):
        h = TelemetryHistory(max_seconds=60)
        for k in range(100):
            h.on_snapshot(snap(thr=k / 100), now=1000.0 + k * 0.1)  # 10 Hz por 10 s
        w = h.window(5.0)
        self.assertAlmostEqual(w[-1].t - w[0].t, 5.0, places=6)
        self.assertEqual(w[-1].throttle, 0.99)
        self.assertEqual(len(h.window(1000)), 100)

    def test_paused_game_freezes_window(self):
        h = TelemetryHistory()
        for k in range(20):
            h.on_snapshot(snap(), now=10.0 + k * 0.1)
        a = h.window(1.0)
        b = h.window(1.0)  # nenhum dado novo, mesmo "tempo" passando
        self.assertEqual(a, b)

    def test_prune_old_samples(self):
        h = TelemetryHistory(max_seconds=2.0)
        for k in range(100):
            h.on_snapshot(snap(), now=k * 0.1)
        self.assertLessEqual(h.window(1e9)[-1].t - h.window(1e9)[0].t, 2.0 + 1e-9)

    def test_disconnect_and_sim_change_clear(self):
        h = TelemetryHistory()
        h.on_snapshot(snap(), now=1.0)
        h.on_snapshot(snap(), now=1.1)
        self.assertEqual(len(h), 2)
        h.on_snapshot(snap(sim=Sim.IRACING), now=1.2)  # trocou de simulador
        self.assertEqual(len(h), 1)
        h.on_snapshot(Snapshot(connected=False), now=1.3)
        self.assertEqual(len(h), 0)

    def test_no_inputs_does_not_append_or_clear(self):
        h = TelemetryHistory()
        h.on_snapshot(snap(), now=1.0)
        h.on_snapshot(snap(with_inputs=False), now=1.1)
        self.assertEqual(len(h), 1)


class TestDecimate(unittest.TestCase):
    def test_small_series_untouched(self):
        ts, vs = [i * 0.1 for i in range(10)], [i / 10 for i in range(10)]
        self.assertEqual(decimate_columns(ts, vs, 100), (ts, vs))

    def test_spike_survives_decimation(self):
        ts = [i * 0.001 for i in range(5000)]  # 5 s a 1 kHz
        vs = [0.0] * 5000
        vs[2503] = 1.0  # toque rápido de freio
        dt, dv = decimate_columns(ts, vs, 100)
        self.assertLess(len(dt), 500)
        self.assertEqual(max(dv), 1.0)
        self.assertEqual(dt, sorted(dt))  # ordem temporal preservada
        self.assertEqual(len(dt), len(dv))
        self.assertAlmostEqual(dt[dv.index(1.0)], 2.503, places=6)  # no instante certo

    def test_keeps_first_and_last_and_valley(self):
        ts = [float(i) for i in range(1000)]
        vs = [1.0] * 1000
        vs[500] = -1.0
        dt, dv = decimate_columns(ts, vs, 50)
        self.assertEqual((dt[0], dt[-1]), (0.0, 999.0))
        self.assertEqual(min(dv), -1.0)


class TestViewModel(unittest.TestCase):
    def test_gear_labels(self):
        self.assertEqual([vm.gear_label(g) for g in (-1, 0, 1, 7)], ["R", "N", "1", "7"])

    def test_channels_defaults_and_garbage(self):
        self.assertTrue(all(vm.get_channels({}).values()))
        c = vm.get_channels({"channels": {"brake": False, "rpm": "no", "xyz": False}})
        self.assertFalse(c["brake"])
        self.assertTrue(c["rpm"])  # valor inválido -> padrão
        self.assertNotIn("xyz", c)

    def test_history_clamped(self):
        self.assertEqual(vm.get_history_s({}), 10.0)
        self.assertEqual(vm.get_history_s({"history_s": 1}), 3.0)
        self.assertEqual(vm.get_history_s({"history_s": 9999}), 120.0)
        self.assertEqual(vm.get_history_s({"history_s": "abc"}), 10.0)
        self.assertEqual(vm.get_history_s({"history_s": float("nan")}), 10.0)

    def test_trace_seconds_clamped(self):
        self.assertEqual(vm.get_trace_s({}), 6.0)
        self.assertEqual(vm.get_trace_s({"trace_s": 0}), 2.0)
        self.assertEqual(vm.get_trace_s({"trace_s": 500}), 60.0)
        self.assertEqual(vm.get_trace_s({"trace_s": "x"}), 6.0)

    def test_shift_lights_sim_vs_derived(self):
        self.assertEqual(vm.shift_lights(None, None), (0, False))
        self.assertEqual(vm.shift_lights(0.5, "sim"), (6, False))
        self.assertEqual(vm.shift_lights(1.0, "sim"), (12, True))
        # derivado: abaixo de 85% do RPM máx. nada acende
        self.assertEqual(vm.shift_lights(0.80, "derived"), (0, False))
        lit, flash = vm.shift_lights(0.925, "derived")
        self.assertEqual((lit, flash), (6, False))
        self.assertEqual(vm.shift_lights(0.999, "derived")[1], True)

    def test_steer_label(self):
        self.assertEqual(vm.steer_label(None), "")
        self.assertEqual(vm.steer_label(0.2), "0°")
        self.assertEqual(vm.steer_label(135.4), "R 135°")
        self.assertEqual(vm.steer_label(-90), "L 90°")

    def test_speed_units(self):
        self.assertAlmostEqual(vm.speed_value(50, "kmh"), 180.0)
        self.assertAlmostEqual(vm.speed_value(50, "mph"), 111.8468, places=3)
        self.assertEqual(vm.speed_unit("mph"), "mph")
        self.assertEqual(vm.nice_ceiling(187, 50), 200)
        self.assertEqual(vm.nice_ceiling(0, 50), 50)

    def test_lane_layout_fills_area_and_respects_weights(self):
        ch = {c: True for c in vm.CHANNELS}
        lanes = vm.enabled_lanes(ch)
        self.assertEqual([l[0] for l in lanes], ["pedals", "speed", "rpm", "steering"])
        rects = vm.lane_layout(lanes, 10, 10, 500, 190, gap=6)
        self.assertAlmostEqual(rects["pedals"][3], 2 * rects["speed"][3])
        bottom = rects["steering"][1] + rects["steering"][3]
        self.assertAlmostEqual(bottom, 200.0)
        # desligar canais remove faixas
        ch.update(speed=False, rpm=False)
        self.assertEqual([l[0] for l in vm.enabled_lanes(ch)], ["pedals", "steering"])
        ch.update(throttle=False, brake=False, clutch=False, steering=False)
        self.assertEqual(vm.enabled_lanes(ch), [])
        self.assertEqual(vm.lane_layout([], 0, 0, 10, 10), {})


if __name__ == "__main__":
    unittest.main()
