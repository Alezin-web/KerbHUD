from kerbhud.core.layout import MODULES
from kerbhud.core.module_options import SPECS, has_options, specs_for
import unittest


class TestModuleOptions(unittest.TestCase):
    def test_every_spec_is_for_a_real_module_and_defaults_are_valid_choices(self):
        for mid, specs in SPECS.items():
            self.assertIn(mid, MODULES)
            for o in specs:
                cur = o.get({})
                if o.kind == "choice":
                    self.assertIn(cur, [v for v, _l in o.choices], f"{mid}.{o.key}: {cur!r}")
                elif o.kind == "int":
                    self.assertTrue(o.choices[0] <= cur <= o.choices[1], f"{mid}.{o.key}")
                elif o.kind == "font":
                    self.assertIsInstance(cur, str)
                elif o.kind == "multi":
                    self.assertTrue(set(cur) <= {k for k, _l in o.choices}, f"{mid}.{o.key}")
                    self.assertIn(o.apply, ("column", "channel"))
                else:
                    self.assertIsInstance(cur, bool, f"{mid}.{o.key}")

    def test_values_stored_by_the_user_are_read_back(self):
        g = {o.key: o for o in specs_for("radar")}
        self.assertEqual(g["range_m"].get({"range_m": 40.0}), 40.0)
        self.assertIs(g["auto_hide"].get({"auto_hide": False}), False)
        self.assertEqual({o.key: o for o in specs_for("standings")}["scope"].get({"scope": "class"}), "class")
        self.assertEqual({o.key: o for o in specs_for("standings")}["columns"].get({"columns": {"gap": False}}) & {"gap"}, set())
        self.assertTrue(has_options("tires") and not has_options("digflag"))


if __name__ == "__main__":
    unittest.main()
