import unittest

from kerbhud.core.classes import abbreviate_class, class_style


class TestClassLabels(unittest.TestCase):
    def test_long_class_names_are_abbreviated(self):
        cases = {"Formula Ford 1600": "F1600", "Ray FF1600": "F1600", "Ray": "F1600", "FF1600": "F1600",
                 "Formula Vee": "FVee", "Formula Renault 2.0": "FR2.0", "Formula Renault 3.5": "FR3.5",
                 "Super Formula": "SF", "Skip Barber Formula 2000": "Skip", "Mazda MX-5 Cup": "MX-5",
                 "Toyota GR86": "GR86", "Porsche 718 Cayman GT4": "GT4", "NASCAR Cup Series": "NASCAR"}
        for raw, want in cases.items():
            self.assertEqual(abbreviate_class(raw), want, raw)

    def test_short_names_unchanged_and_unknown_truncated(self):
        self.assertEqual(abbreviate_class("Pro"), "PRO")
        self.assertEqual(abbreviate_class("Radical SR10 Challenge"), "RADICA")
        self.assertEqual(abbreviate_class("Formula Zeta 900"), "F900")
        self.assertEqual(abbreviate_class("Formula Zeta"), "FZeta")
        self.assertEqual(abbreviate_class(""), "")
        self.assertEqual(abbreviate_class(None), "")

    def test_short_keys_match_whole_words_only(self):
        self.assertNotEqual(abbreviate_class("F35 Lightning"), "F3")
        self.assertEqual(abbreviate_class("F3"), "F3")

    def test_known_classes_keep_their_labels_and_colours(self):
        self.assertEqual(class_style("LMP2_ELMS").label, "LMP2")
        self.assertEqual(class_style("Hypercar").label, "HYPER")
        st = class_style("Formula Ford 1600", "#abcdef", "iracing")
        self.assertEqual(st.label, "F1600")
        self.assertEqual(st.color, "#abcdef")  # cor do simulador continua valendo para classe desconhecida


if __name__ == "__main__":
    unittest.main()
