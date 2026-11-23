import unittest

from kerbhud.core.digflag import GREEN_SHOW_S, DigFlagTracker
from kerbhud.core.model import (CarState, CarStatus, PlayerPose, SessionState, Sim, Snapshot, TireSet,
                                   TireWheel)
from kerbhud.core.radar import radar_view
from kerbhud.core.spotter import SpotterTracker, side_traffic
from kerbhud.core.tireview import format_pressure, tire_view


def snap(others, pose=True, side=None, flags=(), track=5000.0):
    me = CarState(0, is_player=True, world_x=0.0, world_z=0.0, lap_dist_pct=0.5)
    cars = [me] + [CarState(i + 1, world_x=o.get("x"), world_z=o.get("z"), lap_dist_pct=o.get("pct"),
                            status=o.get("status", CarStatus.RUNNING)) for i, o in enumerate(others)]
    # pose: o carro anda para +z (frente = (0,1)); a esquerda dele é -x
    return Snapshot(sim=Sim.LMU, connected=True, cars=cars, player_idx=0,
                    session=SessionState(track_length_m=track, flags=list(flags)),
                    pose=PlayerPose((0.0, 1.0), (-1.0, 0.0)) if pose else None, side_traffic=side)


class TestSpotter(unittest.TestCase):
    def test_geometry_left_right_and_clear(self):
        s = snap([{"x": -3.0, "z": 1.0}, {"x": 3.0, "z": -2.0}, {"x": 3.0, "z": 20.0}, {"x": 0.5, "z": 0.0}])
        self.assertEqual(side_traffic(s), (1, 1))  # 3ª: longe à frente; 4ª: dentro do mesmo carro (<1.2 m)
        self.assertEqual(side_traffic(snap([{"x": 20.0, "z": 0.0}])), (0, 0))

    def test_sim_provided_value_wins_and_missing_data_is_none(self):
        self.assertEqual(side_traffic(snap([], pose=False, side=(2, 0))), (2, 0))
        self.assertIsNone(side_traffic(snap([], pose=False)))
        self.assertIsNone(side_traffic(Snapshot()))

    def test_hold_prevents_flicker(self):
        t = [0.0]
        tr = SpotterTracker(clock=lambda: t[0])
        self.assertEqual(tr.update(snap([{"x": -3.0, "z": 0.0}])), (1, 0))
        t[0] = 0.1
        self.assertEqual(tr.update(snap([])), (1, 0))  # ainda dentro do tempo de espera
        t[0] = 0.6
        self.assertEqual(tr.update(snap([])), (0, 0))


class TestRadar(unittest.TestCase):
    def test_lmu_uses_real_positions(self):
        v = radar_view(snap([{"x": -3.0, "z": 5.0}, {"x": 2.0, "z": -10.0}, {"x": 0.0, "z": 80.0}]), 30.0)
        self.assertTrue(v.lateral_real)
        pts = sorted((round(c.x, 1), round(c.y, 1)) for c in v.cars)
        self.assertEqual(pts, [(-3.0, 5.0), (2.0, -10.0)])  # x>0 = direita; a esquerda do carro é o -x do mundo

    def test_iracing_places_close_cars_on_the_indicated_side(self):
        s = snap([{"pct": 0.5 + 4 / 5000, "x": None, "z": None}, {"pct": 0.5 - 20 / 5000, "x": None, "z": None}],
                 pose=False, side=(1, 0))
        s.cars[0].world_x = None
        v = radar_view(s, 30.0)
        self.assertFalse(v.lateral_real)
        by_y = {round(c.y): c.x for c in v.cars}
        self.assertLess(by_y[4], 0)  # o carro colado vai para a esquerda
        self.assertEqual(by_y[-20], 0.0)  # o distante fica no eixo central

    def test_pit_cars_and_no_data(self):
        self.assertEqual(radar_view(snap([{"x": 3.0, "z": 0.0, "status": CarStatus.GARAGE}])).cars, [])
        self.assertFalse(radar_view(None).available)


class TestDigFlag(unittest.TestCase):
    def test_priority_and_green_only_briefly(self):
        t = [0.0]
        tr = DigFlagTracker(clock=lambda: t[0])
        v = tr.update(snap([], flags=["green", "yellow", "blue"]))
        self.assertEqual((v.primary, v.others), ("blue", ["yellow", "green"]))
        t[0] = 1.0
        self.assertEqual(tr.update(snap([], flags=["green"])).primary, "green")
        t[0] = 1.0 + GREEN_SHOW_S + 1
        self.assertFalse(tr.update(snap([], flags=["green"])).active)  # a verde some depois de alguns segundos

    def test_nothing_without_flags_and_checkered_stays(self):
        tr = DigFlagTracker()
        self.assertFalse(tr.update(snap([])).active)
        self.assertFalse(tr.update(None).active)
        self.assertEqual(tr.update(snap([], flags=["checkered"])).primary, "checkered")


class TestTires(unittest.TestCase):
    def test_states_with_and_without_optimal_temperature(self):
        ts = TireSet({"fl": TireWheel(temp_c=70.0, optimal_c=90.0, pressure_kpa=180.0, wear_pct=80.0),
                      "fr": TireWheel(temp_c=92.0, optimal_c=90.0, wear_pct=40.0),
                      "rl": TireWheel(temp_c=120.0, wear_pct=10.0, flat=True),
                      "rr": TireWheel(temp_c=90.0)})
        v = tire_view(Snapshot(connected=True, tires=ts))
        c = v.cells
        self.assertEqual((c["fl"].temp_state, c["fr"].temp_state, c["rl"].temp_state, c["rr"].temp_state),
                         ("cold", "ok", "hot", "ok"))
        self.assertEqual((c["fl"].wear_state, c["fr"].wear_state, c["rl"].wear_state, c["rr"].wear_state),
                         ("ok", "warn", "danger", "nodata"))
        self.assertTrue(c["rl"].flat)

    def test_pressure_units_and_no_data(self):
        self.assertEqual(format_pressure(200.0, "kpa"), "200")
        self.assertEqual(format_pressure(200.0, "psi"), "29.0")
        self.assertEqual(format_pressure(None, "psi"), "-")
        self.assertFalse(tire_view(Snapshot(connected=True)).has_data)
        self.assertFalse(tire_view(None).has_data)


if __name__ == "__main__":
    unittest.main()


class TestRadarFluidityAndAlerts(unittest.TestCase):
    def test_smoother_extrapolates_between_game_updates(self):
        from kerbhud.core.radar import RadarCar, RadarSmoother, RadarView
        t = [0.0]
        sm = RadarSmoother(clock=lambda: t[0])
        car = CarState(1)
        for step in range(4):  # o jogo atualiza a cada 0,2 s: o carro anda 5 m/s para a frente
            t[0] = step * 0.2
            sm.update(RadarView([RadarCar(car, 0.0, 10.0 + step * 1.0)], True, True))
            sm.frame()
        t[0] = 0.6 + 0.1  # 0,1 s depois da última atualização (sem dado novo)
        for _ in range(8):  # vários quadros de desenho seguidos
            t[0] += 0.0
            y = sm.frame().cars[0].y
        self.assertGreater(y, 13.0)  # já passou da última posição conhecida (projeção)
        self.assertLess(y, 13.6)

    def test_proximity_levels_and_behind_line(self):
        from kerbhud.core.radar import RadarCar, approaching_from_behind, proximity
        c = CarState(1)
        self.assertEqual(proximity(RadarCar(c, 0.0, -20.0)), 0)
        self.assertEqual(proximity(RadarCar(c, 0.0, -10.0)), 1)
        self.assertEqual(proximity(RadarCar(c, 0.0, -4.0)), 2)
        closing = RadarCar(c, 0.0, -10.0, 0.0, 6.0)  # se aproxima (a distância diminui)
        self.assertTrue(approaching_from_behind(closing))
        self.assertFalse(approaching_from_behind(RadarCar(c, 0.0, -10.0, 0.0, -6.0)))  # se afastando
        self.assertFalse(approaching_from_behind(RadarCar(c, 0.0, 10.0, 0.0, -6.0)))  # à frente: sem linha
        self.assertFalse(approaching_from_behind(RadarCar(c, 9.0, -10.0, 0.0, 6.0)))  # outra faixa
        self.assertTrue(approaching_from_behind(RadarCar(c, 0.0, -4.0)))  # colado: alerta mesmo parado

    def test_led_pattern(self):
        from kerbhud.core.digflag import FLAG_CODE, led_pattern
        pat = led_pattern("SC")
        self.assertEqual((len(pat), len(pat[0])), (7, 11))  # 2 letras de 5 colunas + 1 de espaço
        self.assertEqual(FLAG_CODE, {"caution": "SC"})  # só o safety car leva sigla
        self.assertTrue(any(any(r) for r in led_pattern("SC")))


class TestDebrisStripes(unittest.TestCase):
    def test_stripes_alternate_diagonally(self):
        from kerbhud.core.digflag import debris_stripe
        row = [debris_stripe(x, 0) for x in range(8)]
        self.assertEqual(row, [False, False, True, True, False, False, True, True])
        self.assertEqual(debris_stripe(0, 2), debris_stripe(2, 0))  # diagonal: mesma listra


class TestCheckeredAndBlink(unittest.TestCase):
    def test_all_flags_blink(self):
        from kerbhud.core.digflag import BLINK_FLAGS, FLAG_STYLE
        self.assertEqual(set(BLINK_FLAGS), set(FLAG_STYLE))

    def test_demo_shows_checkered_at_the_end_of_each_stage(self):
        import time
        from kerbhud.providers.demo import STAGES, DemoProvider
        d = DemoProvider()
        for key, st in STAGES.items():
            if st.lmu_style:
                continue
            d.scenario = key
            d._t0 = time.monotonic() - (st.duration - 2.0)
            self.assertEqual(d.poll().session.flags, ["checkered"], key)


class TestRadarSideGlowAndStrip(unittest.TestCase):
    def test_side_levels(self):
        from kerbhud.core.radar import RadarCar, side_levels
        c = CarState(1)
        self.assertEqual(side_levels([RadarCar(c, -3.2, 0.5)]), {"left": 1, "right": 0})
        self.assertEqual(side_levels([RadarCar(c, 2.0, -1.0)]), {"left": 0, "right": 2})  # quase encostando
        self.assertEqual(side_levels([RadarCar(c, -3.2, 9.0)]), {"left": 0, "right": 0})  # longe à frente
        self.assertEqual(side_levels([RadarCar(c, -9.0, 0.0)]), {"left": 0, "right": 0})  # outra faixa

    def test_strip_slope_follows_relative_motion_and_is_capped(self):
        from kerbhud.core.radar import MAX_STRIP_SLOPE, RadarCar, strip_slope
        c = CarState(1)
        self.assertEqual(strip_slope(RadarCar(c, 0.0, -10.0, 0.0, 6.0)), 0.0)
        self.assertAlmostEqual(strip_slope(RadarCar(c, 0.0, -10.0, 1.2, 6.0)), 0.2)
        self.assertEqual(strip_slope(RadarCar(c, 0.0, -10.0, 9.0, 6.0)), MAX_STRIP_SLOPE)


class TestMotionHeadingAndFilters(unittest.TestCase):
    def test_heading_follows_movement_and_holds_when_stopped(self):
        from kerbhud.core.heading import MotionHeading
        t = [0.0]
        h = MotionHeading(clock=lambda: t[0])
        self.assertIsNone(h.update(0.0, 0.0))  # nunca andou
        for i in range(1, 8):
            t[0] = i * 0.1
            f = h.update(0.0, -i * 3.0)  # andando para -z
        self.assertAlmostEqual(f[0], 0.0)
        self.assertAlmostEqual(f[1], -1.0)
        for i in range(8, 30):  # parou: mantém a última direção
            t[0] = i * 0.1
            f = h.update(0.0, -21.0)
        self.assertAlmostEqual(f[1], -1.0)

    def test_point_smoother_projects_between_game_updates(self):
        from kerbhud.core.smooth import PointSmoother
        t = [0.0]
        sm = PointSmoother(clock=lambda: t[0])
        sm.update({1: (0.0, 0.0)})
        for i in range(1, 6):  # o jogo atualiza a cada 0,125 s, o carro anda 10 m/s
            t[0] = i * 0.125
            sm.update({1: (1.25 * i, 0.0)})
            for _ in range(4):  # 4 repinturas entre as atualizações
                t[0] += 0.03
                x = sm.frame()[1][0]
        self.assertGreater(x, 1.25 * 5)  # já passou da última posição conhecida (projeção)
        sm.update({})
        self.assertEqual(sm.frame(), {})  # carro sumiu

    def test_radar_ignores_cars_on_another_stretch_and_in_pits(self):
        from kerbhud.core.radar import radar_view
        from kerbhud.core.model import PlayerPose
        me = CarState(0, is_player=True, world_x=0.0, world_z=0.0, lap_dist_pct=0.10)
        near_ok = CarState(1, world_x=-3.0, world_z=-5.0, lap_dist_pct=0.1001)
        parallel = CarState(2, world_x=-4.0, world_z=2.0, lap_dist_pct=0.60)  # perto em linha reta, longe pela volta
        pits = CarState(3, world_x=3.0, world_z=-6.0, lap_dist_pct=0.1002, status=CarStatus.PITS)
        snap = Snapshot(sim=Sim.LMU, connected=True, cars=[me, near_ok, parallel, pits], player_idx=0,
                        pose=PlayerPose(forward=(0.0, -1.0), left=(1.0, 0.0)))
        snap.session.track_length_m = 5000.0
        idx = {rc.car.idx for rc in radar_view(snap, 30.0).cars}
        self.assertEqual(idx, {1})


class TestOriCalibrationAndSpotterBars(unittest.TestCase):
    def test_calibrator_finds_the_reading_that_matches_the_movement(self):
        import math
        from kerbhud.core.heading import OriCalibrator
        cal = OriCalibrator()
        self.assertIsNone(cal.best())
        ori = None
        for i in range(60):  # carro fazendo uma curva: a frente gira; a "linha2" é a traseira (frente = -linha2)
            yaw = i * 0.1
            fx, fz = math.cos(yaw), math.sin(yaw)
            lx, lz = -fz, fx
            ori = [(lx, 0.0, lz), (0.0, 1.0, 0.0), (-fx, 0.0, -fz)]
            cal.observe(ori, (fx, fz))
        name, score = cal.best()
        self.assertEqual(name, "-linha2")
        self.assertGreater(score, 0.99)
        f = cal.forward([(0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (0.0, 0.0, -1.0)])  # parado, outra direção
        self.assertAlmostEqual(f[1], 1.0)

    def test_motion_heading_reports_moving(self):
        from kerbhud.core.heading import MotionHeading
        t = [0.0]
        h = MotionHeading(clock=lambda: t[0])
        h.update(0.0, 0.0)
        t[0] = 0.3
        h.update(0.0, 0.0)
        self.assertFalse(h.moving)
        t[0] = 0.6
        h.update(5.0, 0.0)
        self.assertTrue(h.moving)

    def test_spotter_offsets_say_where_the_car_is(self):
        from kerbhud.core.spotter import SpotterTracker, side_offsets
        me = CarState(0, is_player=True, world_x=0.0, world_z=0.0, lap_dist_pct=0.1)
        other = CarState(1, world_x=-3.0, world_z=-2.0, lap_dist_pct=0.1)  # esquerda/direita conforme a pose
        snap = Snapshot(sim=Sim.LMU, connected=True, cars=[me, other], player_idx=0,
                        pose=PlayerPose(forward=(0.0, -1.0), left=(1.0, 0.0)))
        snap.session.track_length_m = 5000.0
        left, right = side_offsets(snap)
        self.assertIsNone(left)
        self.assertAlmostEqual(right, 2.0)  # x = -3 é à direita; z = -2 é 2 m à frente
        tr = SpotterTracker()
        tr.update(snap)
        self.assertAlmostEqual(tr.offsets[1], 2.0)
        self.assertIsNone(tr.offsets[0])


class TestTireZones(unittest.TestCase):
    def test_temp_color_ramp(self):
        from kerbhud.core.tireview import temp_color
        self.assertEqual(temp_color(None), "#3a3a44")
        self.assertEqual(temp_color(85.0), "#3ddc6b")            # na ideal: verde
        self.assertEqual(temp_color(50.0), "#5bc0ff")            # muito fria: azul
        self.assertEqual(temp_color(120.0), "#ff4d3a")           # muito quente: vermelho
        self.assertNotIn(temp_color(95.0), ("#3ddc6b", "#f5c400", "#ff8a1f"))  # entre os pontos: cor misturada
        self.assertEqual(temp_color(102.0, 90.0), "#f5c400")     # +12 da ideal informada: amarelo
    def test_cells_have_three_zones_and_lowest_wear_highlight(self):
        from kerbhud.core.model import TIRE_CORNERS, TireSet, TireWheel
        from kerbhud.core.tireview import tire_view
        wheels = {k: TireWheel(temp_c=80.0, temps_c=(61.0, 64.0, 67.0), wear_pct=90.0, wear_zones=(93.0, 92.0, 94.0))
                  for k in TIRE_CORNERS}
        wheels["fr"] = TireWheel(temp_c=88.0, temps_c=(88.0, 86.0, 84.0), wear_pct=90.0, wear_zones=(88.0, 89.0, 91.0))
        wheels["rl"] = TireWheel(temp_c=80.0, wear_pct=70.0)  # sem zonas: repete a média da roda
        me = CarState(0, is_player=True, laps_completed=11)
        snap = Snapshot(sim=Sim.IRACING, connected=True, cars=[me], player_idx=0, tires=TireSet(wheels=wheels))
        v = tire_view(snap)
        self.assertEqual(v.lap, 12)
        self.assertEqual(v.cells["fl"].temps, (61.0, 64.0, 67.0))
        self.assertIsNone(v.cells["fl"].low_wear)  # 92 >= 90: sem destaque
        self.assertEqual(v.cells["fr"].low_wear, 0)  # 88 é a zona mais gasta e < 90
        self.assertEqual(v.cells["rl"].wears, (70.0, 70.0, 70.0))
        self.assertEqual(v.cells["rl"].temps, (80.0, 80.0, 80.0))


class TestTurnSense(unittest.TestCase):
    def _drive(self, ts, steer, theta_sign, n=40):
        import math
        th = 0.0
        for _ in range(n):
            th += theta_sign * 0.05
            ts.observe((math.cos(th), math.sin(th)), steer, 30.0)

    def test_left_comes_from_the_steering_wheel(self):
        from kerbhud.core.heading import TurnSense
        ts = TurnSense()
        self.assertIsNone(ts.left_of((1.0, 0.0)))  # sem evidência
        self._drive(ts, 0.5, +1)  # volante à direita e o rumo gira no sentido +: esquerda = (fz, -fx)
        self.assertEqual(ts.left_of((1.0, 0.0)), (0.0, -1.0))
        ts2 = TurnSense()
        self._drive(ts2, 0.5, -1)  # volante à direita e o rumo gira no sentido -: esquerda = (-fz, fx)
        self.assertEqual(ts2.left_of((1.0, 0.0)), (-0.0, 1.0))

    def test_slow_driving_gives_no_evidence(self):
        from kerbhud.core.heading import TurnSense
        ts = TurnSense()
        for i in range(50):
            ts.observe((1.0, 0.0), 1.0, 2.0)
        self.assertEqual(ts.evidence, 0.0)
