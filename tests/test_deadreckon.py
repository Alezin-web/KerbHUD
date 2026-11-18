"""iRacing sem Lat/Lon: posição estimada por velocidade x rumo e traçado gravado a partir dela."""
from __future__ import annotations

import math
import unittest

from kerbhud.core.deadreckon import DeadReckoner
from kerbhud.core.model import (CAP_PLAYER_XY, CAP_PLAYER_XY_ESTIMATED, CarState, CarStatus, Inputs, SessionState, Sim,
                                Snapshot)
from kerbhud.core.trackmap import BINS, TrackRecorder, map_cars
from kerbhud.providers.iracing import IRacingProvider

from test_providers import BytesMapping, ir_values, make_iracing_memory


class TestDeadReckoner(unittest.TestCase):
    def test_straight_line_north_and_east(self):
        d = DeadReckoner()
        d.update(0.0, 20.0, 0.0)
        for i in range(1, 11):
            xy = d.update(i * 0.1, 20.0, 0.0)
        self.assertAlmostEqual(xy[0], 0.0, places=6)
        self.assertAlmostEqual(xy[1], 20.0, places=6)  # yaw 0 = norte
        d = DeadReckoner()
        d.update(0.0, 10.0, -math.pi / 2)  # giro à esquerda é positivo: -90° = virado para o leste
        for i in range(1, 11):
            xy = d.update(i * 0.1, 10.0, -math.pi / 2)
        self.assertAlmostEqual(xy[0], 10.0, places=6)
        self.assertAlmostEqual(xy[1], 0.0, places=6)

    def test_full_circle_closes(self):
        d = DeadReckoner()
        v, omega, dt = 40.0, 0.2, 1 / 60
        t, xy = 0.0, None
        while t <= 2 * math.pi / omega:
            xy = d.update(t, v, omega * t)
            t += dt
        self.assertLess(math.hypot(*xy), 3.0)  # volta o ao ponto de partida (erro de integração pequeno)

    def test_gaps_and_garbage_are_not_integrated(self):
        d = DeadReckoner()
        d.update(0.0, 30.0, 0.0)
        d.update(5.0, 30.0, 0.0)  # buraco de 5 s (pausa/replay): não inventa 150 m
        xy = d.update(5.1, 30.0, 0.0)
        self.assertAlmostEqual(xy[1], 3.0, places=6)
        self.assertIsNone(d.update(None, 30.0, 0.0))
        self.assertIsNone(d.update(6.0, None, 0.0))
        self.assertIsNone(d.update(6.0, 30.0, float("nan")))
        d.update(4.0, 30.0, 0.0)  # tempo voltou (replay): sem avanço
        self.assertAlmostEqual(d.z, 3.0, places=6)


def lap_snaps(laps=2.5, start_pct=0.37, drift=0.0004, speed_scale=1.02, status=CarStatus.RUNNING, driving=True):
    """Volta circular de raio ~250 m, percorrida como o iRacing: só speed, yaw e pct; a estimativa vem do DeadReckoner."""
    radius, v, dt = 250.0, 45.0, 1 / 30
    omega = v / radius
    circ = 2 * math.pi * radius
    dr = DeadReckoner()
    t = 0.0
    while t * v < laps * circ:
        pct = (start_pct + t * v / circ) % 1.0
        x, z = dr.update(t, v * speed_scale, omega * t + drift * t)  # erro de escala e de rumo = a deriva real
        me = CarState(idx=0, driver_name="eu", is_player=True, lap_dist_pct=pct, status=status, world_x=x, world_z=z, position=1)
        other = CarState(idx=1, driver_name="outro", lap_dist_pct=(pct + 0.25) % 1.0, status=CarStatus.RUNNING, position=2)
        yield Snapshot(sim=Sim.IRACING, connected=True, cars=[me, other], player_idx=0, driving=driving,
                       capabilities=frozenset({CAP_PLAYER_XY_ESTIMATED}), inputs=Inputs(speed_ms=v),
                       session=SessionState(active=True, track_name="Navarra", track_length_m=circ))
        t += dt


class TestEstimatedRecording(unittest.TestCase):
    def test_records_one_lap_between_two_start_lines_and_closes_the_drift(self):
        rec, shape = TrackRecorder(), None
        for s in lap_snaps():
            shape = rec.update(s) or shape
        self.assertIsNotNone(shape)
        self.assertEqual(len(shape.points), BINS)
        x0, y0 = shape.xy_at(0.0)
        x1, y1 = shape.xy_at(0.9975)
        self.assertLess(math.hypot(x1 - x0, y1 - y0), 60.0)  # o fim encontra o começo, apesar da deriva
        minx, miny, maxx, maxy = shape.bounds()
        self.assertAlmostEqual(maxx - minx, 500.0, delta=100.0)  # ainda parece o círculo de ~500 m
        self.assertAlmostEqual(maxy - miny, 500.0, delta=100.0)

    def test_progress_shows_the_current_lap_and_never_records_in_the_pits_or_replay(self):
        rec = TrackRecorder()
        for s in lap_snaps(laps=0.9, start_pct=0.5):
            rec.update(s)
        self.assertGreater(rec.progress, 0.0)
        for kw in ({"status": CarStatus.PITS}, {"driving": False}):
            rec2 = TrackRecorder()
            for s in lap_snaps(**kw):
                rec2.update(s)
            self.assertIsNone(rec2.shape, kw)
            self.assertEqual(rec2.progress, 0.0)

    def test_a_lap_that_jumps_is_discarded_and_counted(self):
        rec = TrackRecorder()
        for i, s in enumerate(lap_snaps(laps=2.2, start_pct=0.1)):
            if i >= 1200:  # no meio da volta que seria gravada, a posição na volta salta (teletransporte/reboque)
                s.cars[0].lap_dist_pct = (s.cars[0].lap_dist_pct + 0.3) % 1.0
            rec.update(s)
        self.assertIsNone(rec.shape)  # não grava um traçado torto

    def test_cars_are_placed_by_lap_percentage_not_by_the_estimated_position(self):
        rec, shape, last = TrackRecorder(), None, None
        for s in lap_snaps():
            shape, last = rec.update(s) or shape, s
        cars = {m.car.idx: m for m in map_cars(last, shape)}
        me = last.cars[0]
        self.assertEqual((round(cars[0].x, 3), round(cars[0].y, 3)), tuple(round(v, 3) for v in shape.xy_at(me.lap_dist_pct)))


class TestEstimatedSampling(unittest.TestCase):
    def test_sparse_samples_are_interpolated_but_a_big_hole_is_not_accepted(self):
        rec = TrackRecorder()
        for i, s in enumerate(lap_snaps()):
            if i % 4 == 0:  # 7,5 Hz em vez de 30 Hz: sem amostra em alguns trechos, mas o carro andou continuamente
                rec.update(s)
        self.assertIsNotNone(rec.shape)
        rec = TrackRecorder()
        for i, s in enumerate(lap_snaps(laps=2.2)):
            if 1000 < i < 1500:  # ~16 s sem nenhum dado no meio da única volta completa: não dá para inventar esse trecho
                continue
            rec.update(s)
        self.assertIsNone(rec.shape)


class TestIRacingProviderPosition(unittest.TestCase):
    def poll(self, skip=()):
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=ir_values(), skip=skip)))
        p.connect()
        return p.poll()

    def test_gps_when_the_game_publishes_it(self):
        s = self.poll()
        self.assertIn(CAP_PLAYER_XY, s.capabilities)
        self.assertNotIn(CAP_PLAYER_XY_ESTIMATED, s.capabilities)
        self.assertIn("GPS", s.debug["posicao_do_carro"])

    def test_estimated_when_there_is_no_lat_lon(self):
        s = self.poll(skip=("Lat", "Lon"))
        self.assertIn(CAP_PLAYER_XY_ESTIMATED, s.capabilities)
        self.assertNotIn(CAP_PLAYER_XY, s.capabilities)
        self.assertIsNotNone(s.player().world_x)
        self.assertTrue(all(c.world_x is None for c in s.cars if not c.is_player))

    def test_unavailable_says_so_in_the_debug(self):
        s = self.poll(skip=("Lat", "Lon", "YawNorth"))
        self.assertIsNone(s.player().world_x)
        self.assertIn("indisponível", s.debug["posicao_do_carro"])


if __name__ == "__main__":
    unittest.main()
