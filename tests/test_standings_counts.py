import unittest

from kerbhud.core.standings import (HeaderLine, StandingsRow, build_standings, get_standings_options,
                                    select_lines_by_counts, select_window)
from test_standings_relative import car, snap


def many(n_gt3=20, n_hyper=6, n_lmp2=6):
    cars, pos = [], 0
    for cls, n in (("Hypercar", n_hyper), ("LMP2", n_lmp2), ("GT3", n_gt3)):
        for _ in range(n):
            pos += 1
            cars.append(car(pos, pos, cls))
    return cars


def shown(view_cars, me, **opts):
    v = build_standings(snap(view_cars, me=me), get_standings_options({}))
    lines = select_lines_by_counts(v.groups, 40, get_standings_options(opts))
    return v, lines


class WindowTest(unittest.TestCase):
    def test_top_then_gap_then_around_me(self):
        rows = list(range(1, 21))  # eu = posição 8 (índice 7)
        self.assertEqual(select_window(rows, 7, 3, 7), [1, 2, 3, None, 5, 6, 7, 8, 9, 10, 11])  # igual ao print
    def test_contiguous_when_near_the_top(self):
        self.assertEqual(select_window(list(range(1, 21)), 2, 3, 7), list(range(1, 8)))

    def test_near_the_end_keeps_the_window_full(self):
        rows = list(range(1, 21))
        self.assertEqual(select_window(rows, 19, 3, 7), [1, 2, 3, None, 14, 15, 16, 17, 18, 19, 20])

    def test_short_class_shows_everyone(self):
        self.assertEqual(select_window([1, 2, 3, 4], 3, 3, 7), [1, 2, 3, 4])


class CountsTest(unittest.TestCase):
    def test_default_counts_and_other_classes(self):
        cars = many()
        me = next(c.idx for c in cars if c.class_name == "GT3" and c.position == 20)
        v, lines = shown(cars, me)
        heads = [ln.label for ln in lines if isinstance(ln, HeaderLine)]
        self.assertEqual(len(heads), 3)
        own = [ln for ln in lines if isinstance(ln, StandingsRow) and ln.class_label == "GT3"]
        self.assertEqual(len(own), 3 + 7)
        self.assertTrue(any(ln.is_player for ln in own))
        others = [ln for ln in lines if isinstance(ln, StandingsRow) and ln.class_label != "GT3"]
        self.assertEqual(len(others), 2 * (1 + 1))  # topo 1 + mais perto de mim 1, por classe

    def test_no_other_classes_with_zero_zero(self):
        cars = many()
        _v, lines = shown(cars, cars[-1].idx, other_top=0, other_around=0)
        self.assertEqual([ln.label for ln in lines if isinstance(ln, HeaderLine)], ["GT3"])
        self.assertTrue(all(ln.class_label == "GT3" for ln in lines if isinstance(ln, StandingsRow)))

    def test_nearest_other_class_car_is_the_one_just_ahead_of_me(self):
        cars = many()
        _v, lines = shown(cars, cars[-1].idx, other_top=1, other_around=1)
        lmp2 = [ln.car.position for ln in lines if isinstance(ln, StandingsRow) and ln.class_label == "LMP2"]
        self.assertEqual(lmp2, [7, 12])  # líder da classe + o carro mais perto de mim (o último da LMP2)

    def test_window_height_is_still_the_cap_and_the_player_survives(self):
        cars = many()
        me = cars[-1].idx
        v = build_standings(snap(cars, me=me), get_standings_options({}))
        lines = select_lines_by_counts(v.groups, 6, get_standings_options({"top_rows": 10, "around_rows": 20}))
        self.assertEqual(len(lines), 6)
        self.assertTrue(any(isinstance(ln, StandingsRow) and ln.is_player for ln in lines))

    def test_without_player_falls_back_to_automatic(self):
        cars = many()
        v = build_standings(snap(cars, me=None), get_standings_options({}))
        lines = select_lines_by_counts(v.groups, 12, get_standings_options({}))
        self.assertTrue(0 < len(lines) <= 12)


if __name__ == "__main__":
    unittest.main()
