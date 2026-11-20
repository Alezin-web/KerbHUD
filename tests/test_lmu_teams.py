import unittest

from kerbhud.core import brands as B
from kerbhud.core.lmu_teams_data import BY_ENTRY


def brand(vehicle, cls, sim="lmu"):
    b = B.brand_for_car(None, vehicle, None, cls, sim)
    return b.key if b else None


class LmuTeamsTest(unittest.TestCase):
    def setUp(self):
        B.set_overrides([])

    def test_table_only_has_catalog_brands(self):
        for v in BY_ENTRY.values():
            self.assertIsNotNone(B.brand_by_key(v), v)

    def test_same_team_different_cars(self):
        self.assertEqual(brand("Proton Competition 2025 #99:WEC 99_25_PROTB2F22869", "Hypercar"), "porsche")
        self.assertEqual(brand("Proton Competition 2025 #11:WEC 11_25_X", "LMP2"), "oreca")

    def test_team_names_with_a_brand_inside_do_not_mislead(self):
        self.assertEqual(brand("AF Corse 2025 #83:ELMS 83_X", "LMP2"), "oreca")
        self.assertEqual(brand("Alpine Elf Team #35:LM 35_X", "LMP2"), "oreca")

    def test_unknown_team_stays_unknown(self):
        self.assertIsNone(brand("Equipe Inventada 2025 #1:WEC x", "Hypercar"))

    def test_user_override_wins(self):
        B.set_overrides([{"match": "Proton Competition", "class": "Hyper", "brand": "ferrari"}])
        self.assertEqual(brand("Proton Competition 2025 #99:WEC x", "Hypercar"), "ferrari")

    def test_not_applied_outside_lmu(self):
        self.assertIsNone(brand("Equipe Inventada 2025 #1:WEC x", "Hypercar", "iracing"))

    def test_diag_vehicles(self):
        for v, c, k in [("BMW M Team WRT 2026 #15:WEC a", "Hypercar", "bmw"),
                        ("Cadillac Hertz Team Jota 2026 #12:WEC a", "Hypercar", "cadillac"),
                        ("Lamborghini Iron Lynx 2024 #63:WEC a", "Hypercar", "lamborghini"),
                        ("United Autosports 2025 #22:WEC a", "LMP2", "oreca")]:
            self.assertEqual(brand(v, c), k, v)


if __name__ == "__main__":
    unittest.main()
