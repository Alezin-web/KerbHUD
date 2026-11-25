"""Revisão geral: o motor não pode morrer por um erro numa leitura; o log registra o que aconteceu."""
from __future__ import annotations

import logging
import tempfile
import time
import unittest
from pathlib import Path

from kerbhud.core import engine as engine_mod
from kerbhud.core.engine import Engine, load_settings
from kerbhud.core.log import RepeatLimiter, setup_logging
from kerbhud.core.model import Sim, Snapshot
from kerbhud.providers.base import Provider, ProviderDisconnected


class FlakyProvider(Provider):
    """Provedor de teste: levanta erros "inesperados" (não ProviderDisconnected) em certas leituras."""
    sim = Sim.LMU

    def __init__(self, fail_first=0, fail_forever=False, connect_fails=0):
        self.fail_first, self.fail_forever, self.connect_fails = fail_first, fail_forever, connect_fails
        self.polls = self.connects = self.closes = 0

    def connect(self):
        self.connects += 1
        if self.connects <= self.connect_fails:
            raise RuntimeError("connect quebrou")
        return True

    def poll(self):
        self.polls += 1
        if self.fail_forever or self.polls <= self.fail_first:
            raise ValueError("leitura quebrou")
        return Snapshot(sim=Sim.LMU, connected=True, status_text=f"ok {self.polls}")

    def close(self):
        self.closes += 1


def run_engine(prov, seconds=1.5, until=None, subs=()):
    cfg = load_settings()
    cfg["simulator"] = "lmu"
    cfg["update_hz"] = 200
    eng = Engine(cfg, providers={"lmu": prov, "iracing": FlakyProvider(connect_fails=10 ** 6), "demo": FlakyProvider(connect_fails=10 ** 6)})
    for s in subs:
        eng.subscribe(s)
    eng.start()
    t0 = time.time()
    while time.time() - t0 < seconds and not (until and until(eng)):
        time.sleep(0.01)
    thread_alive = eng._thread.is_alive()
    eng.stop()
    return eng, thread_alive


class TestEngineSurvivesErrors(unittest.TestCase):
    def setUp(self):
        logging.getLogger("kerbhud").addHandler(logging.NullHandler())

    def test_unexpected_poll_errors_do_not_kill_the_capture(self):
        prov = FlakyProvider(fail_first=5)
        eng, alive = run_engine(prov, until=lambda e: e.latest().connected)
        self.assertTrue(alive)
        self.assertTrue(eng.latest().connected)
        self.assertEqual(prov.connects, 1)  # poucos erros seguidos: segue lendo sem reconectar

    def test_persistent_errors_reconnect_instead_of_freezing(self):
        prov = FlakyProvider(fail_forever=True)
        eng, alive = run_engine(prov, seconds=2.0, until=lambda e: prov.connects >= 2)
        self.assertTrue(alive)
        self.assertGreaterEqual(prov.connects, 2)  # fechou e conectou de novo
        self.assertGreaterEqual(prov.closes, 1)
        self.assertGreaterEqual(prov.polls, engine_mod.MAX_POLL_ERRORS)

    def test_connect_error_is_not_fatal(self):
        prov = FlakyProvider(connect_fails=2)
        eng, alive = run_engine(prov, seconds=4.0, until=lambda e: e.latest().connected)
        self.assertTrue(alive)
        self.assertTrue(eng.latest().connected)

    def test_a_broken_subscriber_does_not_stop_the_others(self):
        got = []

        def bad(_s):
            raise RuntimeError("assinante com defeito")

        prov = FlakyProvider()
        eng, alive = run_engine(prov, subs=(bad, got.append), until=lambda e: len(got) >= 3)
        self.assertTrue(alive)
        self.assertGreaterEqual(len(got), 3)

    def test_disconnect_still_reconnects(self):
        class Drops(FlakyProvider):
            def poll(self):
                self.polls += 1
                if self.polls == 3:
                    raise ProviderDisconnected("fechou")
                return Snapshot(sim=Sim.LMU, connected=True)

        prov = Drops()
        run_engine(prov, until=lambda e: prov.connects >= 2)
        self.assertGreaterEqual(prov.connects, 2)


class TestSettingsAreForgiving(unittest.TestCase):
    def load(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / "settings.json"
        p.write_text(text, encoding="utf-8")
        return load_settings(p), p

    def test_corrupted_file_opens_with_defaults_and_is_kept_as_bad(self):
        cfg, p = self.load("{ isto não é json")
        self.assertEqual(cfg["simulator"], "auto")
        self.assertFalse(p.exists())
        self.assertTrue(p.with_name("settings.json.bad").exists())

    def test_json_that_is_not_an_object_is_handled(self):
        cfg, _ = self.load("[1, 2, 3]")
        self.assertEqual(cfg["update_hz"], 60)

    def test_wrong_types_fall_back_to_defaults(self):
        cfg, _ = self.load('{"update_hz": "abc", "ui_hz": null, "simulator": "xbox", "visibility": 7, '
                           '"hotkeys": "nada", "iracing": [], "window_geometry": [1, 2], "lmu": {"driver_rank": "A"}}')
        self.assertEqual((cfg["update_hz"], cfg["ui_hz"], cfg["simulator"], cfg["visibility"]), (60, 60, "auto", "always"))
        self.assertEqual(cfg["hotkeys"]["toggle_edit"], "Ctrl+Alt+E")
        self.assertTrue(cfg["iracing"]["live_positions"])
        self.assertIsNone(cfg["window_geometry"])
        self.assertEqual(cfg["lmu"]["driver_rank"], "A")  # valor bom do usuário é mantido

    def test_out_of_range_rates_are_clamped_and_good_values_kept(self):
        cfg, _ = self.load('{"update_hz": 100000, "ui_hz": 0, "window_geometry": [10, 20, 800, 600], "my_country": "br"}')
        self.assertEqual((cfg["update_hz"], cfg["ui_hz"]), (240, 1))
        self.assertEqual(cfg["window_geometry"], [10, 20, 800, 600])
        self.assertEqual(cfg["my_country"], "br")

    def test_write_is_atomic_and_round_trips(self):
        from kerbhud.core.engine import update_settings_file, write_settings_file
        d = Path(tempfile.mkdtemp())
        p = d / "settings.json"
        write_settings_file(p, {"a": 1})
        update_settings_file(p, "b", 2)
        self.assertEqual(load_settings(p)["b"], 2)
        self.assertEqual([f.name for f in d.iterdir()], ["settings.json"])  # sem arquivo temporário sobrando


class TestLog(unittest.TestCase):
    def test_log_file_is_created_and_rotates_safely(self):
        import kerbhud.core.log as L
        saved_conf, saved_handlers = L._configured, list(L.get_logger().handlers)
        try:
            L._configured = False
            L.get_logger().handlers.clear()
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "sub" / "kerbhud.log"
                log = setup_logging(path)
                log.error("erro de teste")
                for h in log.handlers:
                    h.flush()
                    h.close()
                self.assertIn("erro de teste", path.read_text(encoding="utf-8"))
        finally:
            L.get_logger().handlers[:] = saved_handlers
            L._configured = saved_conf

    def test_unwritable_log_does_not_break_the_program(self):
        import kerbhud.core.log as L
        saved_conf, saved_handlers = L._configured, list(L.get_logger().handlers)
        try:
            L._configured = False
            L.get_logger().handlers.clear()
            with tempfile.TemporaryDirectory() as d:
                blocker = Path(d) / "arquivo"
                blocker.write_text("x")
                setup_logging(blocker / "dentro" / "kerbhud.log")  # "pasta" é um arquivo: mkdir falha
        finally:
            L.get_logger().handlers[:] = saved_handlers
            L._configured = saved_conf

    def test_repeat_limiter_logs_first_and_then_every_n(self):
        r = RepeatLimiter(every=5)
        got = [r.should_log("a") for _ in range(11)]
        self.assertEqual([i + 1 for i, g in enumerate(got) if g], [1, 5, 10])
        self.assertTrue(r.should_log("b"))
        r.clear()
        self.assertTrue(r.should_log("a"))


if __name__ == "__main__":
    unittest.main()


class PerfMigrationTest(unittest.TestCase):
    def test_old_default_ui_hz_moves_to_60_once_and_later_choice_is_kept(self):
        import json, tempfile
        from pathlib import Path
        from kerbhud.core.engine import load_settings
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "settings.json"
            p.write_text(json.dumps({"ui_hz": 30, "units": "mph"}), encoding="utf-8")
            self.assertEqual(load_settings(p)["ui_hz"], 60)
            saved = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual((saved["perf_rev"], saved["ui_hz"], saved["units"]), (1, 60, "mph"))
            p.write_text(json.dumps({"ui_hz": 30, "perf_rev": 1}), encoding="utf-8")  # escolheu 30 depois: respeita
            self.assertEqual(load_settings(p)["ui_hz"], 30)
            p.write_text(json.dumps({"ui_hz": 45}), encoding="utf-8")  # escolha manual diferente do padrão antigo
            self.assertEqual(load_settings(p)["ui_hz"], 45)
