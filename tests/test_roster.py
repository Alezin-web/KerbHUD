import time
import unittest

from kerbhud.core.engine import Engine, load_settings
from kerbhud.core.model import CarState, CarStatus, SessionState, Sim, Snapshot
from kerbhud.core.roster import GHOST_IDX_BASE, Roster
from kerbhud.core.standings import StandingsOptions, build_standings
from kerbhud.providers.base import Provider


def mk(idx, name, pos, laps=5, cls="GT3", number=None, player=False, **kw):
    return CarState(idx=idx, driver_name=name, position=pos, class_position=pos, class_name=cls,
                    car_number=number or str(idx), laps_completed=laps, is_player=player, **kw)


def snap(cars, active=True, session_type="Race", track="Sarthe", player_idx=None, sim=Sim.LMU, connected=True):
    return Snapshot(sim=sim, connected=connected, cars=cars, player_idx=player_idx,
                    session=SessionState(active=active, session_type=session_type if active else None,
                                         track_name=track if active else None, time_remaining_s=100.0 if active else None))


class TestRoster(unittest.TestCase):
    def setUp(self):
        self.r = Roster()
        self.a, self.b, self.c = mk(0, "Ana", 1), mk(1, "Beto", 2, laps=4), mk(2, "Caco", 3, laps=3, player=True)

    def test_nothing_changes_while_everybody_is_present(self):
        s = snap([self.a, self.b, self.c], player_idx=2)
        self.assertIs(self.r.update(s), s)  # mesmo objeto: custo zero

    def test_driver_who_leaves_stays_as_dimmed_ghost_at_the_bottom(self):
        self.r.update(snap([self.a, self.b, self.c], player_idx=2))
        out = self.r.update(snap([self.a, self.c], player_idx=2))  # Beto saiu
        ghosts = [c for c in out.cars if not c.in_session]
        self.assertEqual([g.driver_name for g in ghosts], ["Beto"])
        g = ghosts[0]
        self.assertEqual((g.status, g.in_session), (CarStatus.OUT, False))
        self.assertGreaterEqual(g.idx, GHOST_IDX_BASE)  # não colide com índices ao vivo
        self.assertEqual(g.position, 4)  # depois do último carro ao vivo (posição 3)
        self.assertEqual(g.laps_completed, 4)  # dados da última vez visto
        self.assertEqual(len(out.cars), 3)
        self.assertEqual(self.b.in_session, True)  # o carro original não foi alterado
        # e continua lá nas próximas atualizações
        again = self.r.update(snap([self.a, self.c], player_idx=2))
        self.assertEqual([c.driver_name for c in again.cars if not c.in_session], ["Beto"])

    def test_returning_driver_replaces_the_ghost(self):
        self.r.update(snap([self.a, self.b, self.c], player_idx=2))
        self.r.update(snap([self.a, self.c], player_idx=2))
        back = self.r.update(snap([self.a, self.b, self.c], player_idx=2))
        self.assertTrue(all(c.in_session for c in back.cars))
        self.assertEqual(len(back.cars), 3)

    def test_ghosts_are_ordered_by_distance_driven_then_last_position(self):
        a, b, c, d = mk(0, "A", 1, laps=10), mk(1, "B", 2, laps=9), mk(2, "C", 3, laps=9), mk(3, "D", 4, laps=2)
        self.r.update(snap([d, c, b, a]))
        out = self.r.update(snap([a]))
        self.assertEqual([(g.driver_name, g.position) for g in out.cars if not g.in_session],
                         [("B", 2), ("C", 3), ("D", 4)])  # B antes de C (mesmas voltas, posição melhor)
        self.assertEqual([g.class_position for g in out.cars if not g.in_session], [2, 3, 4])

    def test_class_positions_continue_per_class(self):
        a, b = mk(0, "A", 1, cls="GT3"), mk(1, "B", 2, cls="LMP2")
        c = mk(2, "C", 3, cls="GT3")
        self.r.update(snap([a, b, c]))
        out = self.r.update(snap([a, b]))
        ghost = next(g for g in out.cars if not g.in_session)
        self.assertEqual((ghost.class_name, ghost.class_position, ghost.position), ("GT3", 2, 3))

    def test_local_player_leaving_points_player_to_the_ghost(self):
        self.r.update(snap([self.a, self.c], player_idx=2))
        out = self.r.update(snap([self.a], player_idx=2))
        self.assertGreaterEqual(out.player_idx, GHOST_IDX_BASE)
        me = out.player()
        self.assertEqual((me.driver_name, me.in_session), ("Caco", False))

    def test_everyone_leaves_at_the_end_keeps_the_final_classification(self):
        self.r.update(snap([self.a, self.b, self.c], player_idx=2))
        out = self.r.update(snap([], active=False, player_idx=2))  # sessão acabou: o jogo não publica mais nada
        self.assertEqual([c.driver_name for c in out.cars], ["Ana", "Beto", "Caco"])  # ordem final preservada
        self.assertTrue(all(not c.in_session for c in out.cars))
        self.assertEqual(out.session.session_type, "Race")  # lembra que era corrida: a lista continua de corrida
        self.assertTrue(out.session.active)
        v = build_standings(out, StandingsOptions())
        self.assertEqual(len(v.rows), 3)  # a classificação não fica vazia
        self.assertTrue(all(r.dim == "out" for r in v.rows))  # tudo apagado
        self.assertFalse(v.hidden)

    def test_new_session_or_disconnect_clears_the_memory(self):
        self.r.update(snap([self.a, self.b]))
        out = self.r.update(snap([self.a], track="Spa"))  # outra pista = sessão nova
        self.assertTrue(all(c.in_session for c in out.cars))
        self.r.update(snap([self.a, self.b], track="Spa"))
        out = self.r.update(snap([self.a], track="Spa", session_type="Qualifying"))  # outro tipo = sessão nova
        self.assertTrue(all(c.in_session for c in out.cars))
        self.r.update(snap([self.a, self.b], track="Spa", session_type="Qualifying"))
        self.r.update(Snapshot(connected=False))  # simulador fechou
        out = self.r.update(snap([self.a], track="Spa", session_type="Qualifying"))
        self.assertEqual(len(out.cars), 1)

    def test_lmu_indices_that_slide_do_not_create_false_ghosts(self):
        a, b, c = mk(0, "Ana", 1, number="10"), mk(1, "Beto", 2, number="11"), mk(2, "Caco", 3, number="12", player=True)
        self.r.update(snap([a, b, c]))
        shifted = [mk(0, "Beto", 2, number="11"), mk(1, "Caco", 3, number="12", player=True),
                   mk(2, "Ana", 1, number="10")]  # mesma gente, outros idx (alguém saiu e os índices deslizaram)
        out = self.r.update(snap(shifted))
        self.assertTrue(all(c.in_session for c in out.cars))
        self.assertEqual(len(out.cars), 3)

    def test_same_name_different_number_are_different_drivers(self):
        x1, x2 = mk(0, "Time", 1, number="10"), mk(1, "Time", 2, number="11")
        self.r.update(snap([x1, x2]))
        out = self.r.update(snap([x1]))
        self.assertEqual([c.car_number for c in out.cars if not c.in_session], ["11"])


class ScriptedProvider(Provider):
    sim = Sim.DEMO

    def __init__(self, frames):
        self.frames, self.i = frames, 0

    def connect(self):
        return True

    def poll(self):
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        return f


class TestEngineKeepsDepartedDrivers(unittest.TestCase):
    def test_engine_publishes_ghosts(self):
        a, b = mk(0, "Ana", 1), mk(1, "Beto", 2)
        frames = [snap([a, b], sim=Sim.DEMO), snap([a], sim=Sim.DEMO)]
        cfg = load_settings()
        cfg["simulator"] = "demo"
        cfg["update_hz"] = 100
        eng = Engine(cfg, providers={"demo": ScriptedProvider(frames), "iracing": ScriptedProvider(frames),
                                     "lmu": ScriptedProvider(frames)})
        eng.start()
        t0 = time.time()
        while time.time() - t0 < 3:
            latest = eng.latest()
            if any(not c.in_session for c in latest.cars):
                break
            time.sleep(0.01)
        eng.stop()
        latest = eng.latest()
        self.assertEqual(sorted((c.driver_name, c.in_session) for c in latest.cars),
                         [("Ana", True), ("Beto", False)])


if __name__ == "__main__":
    unittest.main()
