import tempfile
import unittest
from pathlib import Path

from kerbhud.core import badges
from kerbhud.core.model import DriverProfile, ProfileSource, SessionState, Sim, Snapshot
from kerbhud.core.standings import profile_chips


class TestBadges(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(badges.slug("Trusted"), "trusted")
        self.assertEqual(badges.slug("B 2"), "b2")
        self.assertIsNone(badges.slug(""))
        self.assertIsNone(badges.slug(None))

    def test_known_contact_badges_have_an_icon_without_files(self):
        for k in ("rookie", "good", "trusted", "warning", "probation", "creator", "driver", "staff"):
            self.assertTrue(badges.has_icon(None, k), k)
        self.assertFalse(badges.has_icon(None, "b2"))  # rank desconhecido: texto

    def test_user_file_wins_and_enables_any_key(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(badges.has_icon(Path(d), "b2"))
            (Path(d) / "b2.png").write_bytes(b"x")
            self.assertTrue(badges.has_icon(Path(d), "b2"))
            self.assertEqual(badges.badge_file(Path(d), "b2").name, "b2.png")

    def test_chips_show_the_rank_names_as_text_for_lmu(self):
        snap = Snapshot(sim=Sim.LMU, connected=True, session=SessionState(active=True),
                        profile=DriverProfile(driver_rank="B2", safety_rank="S3", contact_badge="Trusted",
                                              source=ProfileSource.MANUAL))
        chips = {c.label.rstrip("*"): c for c in profile_chips(snap, None)}
        self.assertEqual(chips["DRIVER"].value, "B2")  # DR e SR: texto
        self.assertEqual(chips["SAFETY"].value, "S3")
        self.assertEqual(chips["BADGE"].value, "Trusted")  # o nome do selo, num texto próprio


    def test_rank_chip_colors_follow_the_tier_letter(self):
        self.assertEqual(badges.tier_color("B2"), badges.tier_color("Bronze"))
        self.assertNotEqual(badges.tier_color("B2"), badges.tier_color("S3"))
        self.assertEqual(badges.tier_color(None), badges.TIER_NEUTRAL)
        self.assertEqual(badges.tier_color("???"), badges.TIER_NEUTRAL)


if __name__ == "__main__":
    unittest.main()
