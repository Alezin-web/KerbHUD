"""Posição ao vivo na corrida do iRacing: a oficial só muda ao cruzar a linha de chegada."""
from __future__ import annotations

import unittest

from kerbhud.core.liveorder import LiveOrder, progress
from kerbhud.core.model import CarState, CarStatus
from kerbhud.providers.iracing import IRacingProvider

from test_providers import BytesMapping, ir_values, make_iracing_memory


def car(idx, laps, pct, cls="GT3", status=CarStatus.RUNNING):
    return CarState(idx=idx, driver_name=f"p{idx}", laps_completed=laps, lap_dist_pct=pct, class_name=cls, status=status)


class TestLiveOrder(unittest.TestCase):
    def test_laps_then_fraction_decide(self):
        cars = [car(1, 5, 0.10), car(2, 5, 0.90), car(3, 6, 0.01), car(4, 4, 0.99)]
        self.assertTrue(LiveOrder().apply(cars))
        self.assertEqual({c.idx: c.position for c in cars}, {3: 1, 2: 2, 1: 3, 4: 4})  # 3 já virou a volta; 4 está uma volta atrás

    def test_class_positions_are_counted_per_class(self):
        cars = [car(1, 5, 0.9, "LMP2"), car(2, 5, 0.8, "GT3"), car(3, 5, 0.7, "LMP2"), car(4, 5, 0.6, "GT3")]
        LiveOrder().apply(cars)
        self.assertEqual({c.idx: c.class_position for c in cars}, {1: 1, 2: 1, 3: 2, 4: 2})
        self.assertEqual({c.idx: c.position for c in cars}, {1: 1, 2: 2, 3: 3, 4: 4})

    def test_overtake_is_seen_before_the_line(self):
        lo = LiveOrder()
        a, b = car(1, 3, 0.50), car(2, 3, 0.40)
        lo.apply([a, b])
        self.assertEqual((a.position, b.position), (1, 2))
        a2, b2 = car(1, 3, 0.60), car(2, 3, 0.65)  # o 2 passou o 1 no meio da volta
        for _ in range(2):
            lo.apply([a2, b2])
        self.assertEqual((a2.position, b2.position), (2, 1))

    def test_single_glitch_read_does_not_flip_the_order(self):
        lo = LiveOrder()
        cars = lambda a, b: [car(1, 3, a), car(2, 3, b)]  # noqa: E731
        for _ in range(3):
            lo.apply(cars(0.50, 0.40))
        glitch = cars(0.30, 0.40)  # 1 leitura isolada (ex.: contador de voltas e fração fora de sincronia)
        lo.apply(glitch)
        self.assertEqual(glitch[0].position, 1)
        back = cars(0.51, 0.40)
        lo.apply(back)
        self.assertEqual(back[0].position, 1)

    def test_cars_out_of_the_world_are_left_alone(self):
        cars = [car(1, 3, 0.5), car(2, 3, 0.4, status=CarStatus.OUT), CarState(idx=3, driver_name="x", position=9)]
        self.assertFalse(LiveOrder().apply(cars))  # só 1 carro com dados: não reordena
        self.assertEqual(cars[2].position, 9)
        self.assertIsNone(progress(cars[1]))
        self.assertIsNone(progress(cars[2]))

    def test_new_or_left_car_is_accepted_at_once(self):
        lo = LiveOrder()
        lo.apply([car(1, 3, 0.5), car(2, 3, 0.4)])
        cars = [car(1, 3, 0.5), car(2, 3, 0.4), car(3, 3, 0.45)]
        lo.apply(cars)
        self.assertEqual([c.position for c in cars], [1, 3, 2])


class TestIRacingLivePositions(unittest.TestCase):
    def snap(self, session_num=0, live=True):
        vals = ir_values()
        vals["SessionNum"] = session_num
        vals["CarIdxLapDistPct"][3] = 0.70  # o carro 3 passou o 4 na pista; a posição oficial ainda não mudou
        p = IRacingProvider(opener=lambda: BytesMapping(make_iracing_memory(values=vals)), live_positions=live)
        p.connect()
        return p.poll()

    def pos(self, s):
        return {c.idx: c.position for c in s.cars}

    def test_race_uses_the_order_on_track(self):
        s = self.snap()
        self.assertEqual((self.pos(s)[3], self.pos(s)[4]), (1, 2))

    def test_option_off_keeps_the_official_position(self):
        s = self.snap(live=False)
        self.assertEqual((self.pos(s)[3], self.pos(s)[4]), (2, 1))

    def test_practice_keeps_the_official_position(self):
        s = self.snap(session_num=1)
        self.assertEqual((self.pos(s)[3], self.pos(s)[4]), (2, 1))  # treino: ordem por melhor volta, não por pista


if __name__ == "__main__":
    unittest.main()
