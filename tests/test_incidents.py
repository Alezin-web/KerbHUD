import unittest

from kerbhud.core.incidents import IMPACT_MIN, IncidentCounter
from kerbhud.core.model import CAP_CONTACT, ContactState, SessionState, Sim, Snapshot


def snap(et, mag, off, track="T", conn=True):
    return Snapshot(sim=Sim.LMU, connected=conn, session=SessionState(active=True, track_name=track),
                    contact=ContactState(et, mag, off), capabilities=frozenset({CAP_CONTACT}))


class TestIncidentCounter(unittest.TestCase):
    def test_old_impact_is_a_baseline_not_a_hit(self):
        c = IncidentCounter()
        c.update(snap(500.0, 900.0, 0))
        self.assertEqual((c.hits, c.offs), (0, 0))

    def test_counts_real_hits_once_and_ignores_light_touches(self):
        c = IncidentCounter()
        c.update(snap(10.0, 0.0, 0))
        for _ in range(5):  # a mesma batida lida várias vezes conta UMA vez
            c.update(snap(20.0, IMPACT_MIN + 1, 0))
        c.update(snap(30.0, IMPACT_MIN - 1, 0))  # leve demais
        self.assertEqual(c.hits, 1)

    def test_off_track_counts_per_excursion_only_with_all_wheels_out(self):
        c = IncidentCounter()
        for w in (0, 2, 3, 4, 4, 4, 1, 0, 4, 0):  # 2 saídas completas (2 ou 3 rodas não contam)
            c.update(snap(1.0, 0.0, w))
        self.assertEqual(c.offs, 2)

    def test_new_session_resets_and_missing_data_is_unavailable(self):
        c = IncidentCounter()
        c.update(snap(1.0, 0.0, 0)); c.update(snap(2.0, 999.0, 4))
        self.assertEqual((c.hits, c.offs), (1, 1))
        c.update(snap(1.0, 0.0, 0, track="Outra"))
        self.assertEqual((c.hits, c.offs), (0, 0))
        c.update(Snapshot())
        self.assertFalse(c.available)


if __name__ == "__main__":
    unittest.main()
