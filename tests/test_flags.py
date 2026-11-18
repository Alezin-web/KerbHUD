import tempfile
import unittest
from pathlib import Path

from kerbhud.core.flags import (ALL_CODES, FLAG_URL, PNG_SIGNATURE, FlagResolver, country_code, fetch_flags,
                                   installed_flags)
from kerbhud.core.model import CarState, Sim
from kerbhud.core.standings import StandingsOptions, build_standings
from kerbhud.providers.iracing import IRacingProvider
import test_providers as TP
from kerbhud.core.memory import BytesMapping


class TestCountryCodes(unittest.TestCase):
    def test_names_aliases_codes_and_accents(self):
        for text, code in (("Brazil", "br"), ("brasil", "br"), ("BR", "br"), ("United States", "us"),
                           ("USA", "us"), ("United Kingdom", "gb"), ("Great Britain", "gb"), ("England", "gb-eng"),
                           ("Scotland", "gb-sct"), ("gb-wls", "gb-wls"), ("Netherlands", "nl"), ("Holland", "nl"),
                           ("Côte d'Ivoire", "ci"), ("Türkiye", "tr"), ("Curaçao", "cw"), ("  germany  ", "de"),
                           ("South Korea", "kr"), ("Czechia", "cz"), ("Bosnia and Herzegovina", "ba")):
            self.assertEqual(country_code(text), code, text)

    def test_unknown_is_none_never_guessed(self):
        for text in (None, "", "   ", "Narnia", "Atlantis", "xx", "12", "Pacific Northwest"):
            self.assertIsNone(country_code(text), text)

    def test_table_is_consistent(self):
        self.assertEqual(len(ALL_CODES), len(set(ALL_CODES)))  # sem duplicados
        self.assertGreater(len(ALL_CODES), 200)
        for code in ALL_CODES:
            self.assertRegex(code, r"^[a-z]{2}(-[a-z]{3})?$")
            self.assertEqual(country_code(code), code)  # o próprio código é aceito
        for code in ("br", "us", "gb", "pt", "ar", "it", "fr", "de", "jp", "mx", "ca", "au"):
            self.assertIn(code, ALL_CODES)


class TestFlagResolver(unittest.TestCase):
    def car(self, name="Fulano", country=None, player=False):
        return CarState(idx=1, driver_name=name, country=country, is_player=player)

    def test_priority_sim_then_driver_flags_then_my_country(self):
        r = FlagResolver({"my_country": "Brazil", "driver_flags": {"Beltrano Silva": "PT", "x": "Narnia"}})
        self.assertEqual(r.code_for(self.car(country="it")), "it")  # dado do simulador vence
        self.assertEqual(r.code_for(self.car("beltrano  silva")), "pt")  # nome sem diferenciar maiúsculas/espaços
        self.assertEqual(r.code_for(self.car(player=True)), "br")  # só o piloto local usa my_country
        self.assertIsNone(r.code_for(self.car()))  # outro piloto sem dado: nada
        self.assertIsNone(r.code_for(self.car("x")))  # país inválido no settings é ignorado
        self.assertEqual(r.code_for(self.car("Beltrano Silva", player=True)), "pt")  # mapeamento por nome > my_country

    def test_empty_or_garbage_settings(self):
        for st in (None, {}, {"driver_flags": "lixo", "my_country": 5}):
            r = FlagResolver(st)
            self.assertIsNone(r.code_for(self.car()))
            self.assertIsNone(r.code_for(self.car(player=True)))

    def test_standings_rows_carry_the_flag_code(self):
        cars = [CarState(idx=1, position=1, class_name="GT3", driver_name="A", country="br"),
                CarState(idx=2, position=2, class_name="GT3", driver_name="B", is_player=True),
                CarState(idx=3, position=3, class_name="GT3", driver_name="C")]
        from kerbhud.core.model import SessionState, Snapshot
        snap = Snapshot(sim=Sim.LMU, connected=True, cars=cars, player_idx=2,
                        session=SessionState(active=True, session_type="Race"))
        v = build_standings(snap, StandingsOptions(), flags=FlagResolver({"my_country": "pt"}))
        self.assertEqual([r.country for r in v.rows], ["br", "pt", None])
        v = build_standings(snap, StandingsOptions())  # sem resolvedor: só o dado do simulador
        self.assertEqual([r.country for r in v.rows], ["br", None, None])


class TestIRacingFlair(unittest.TestCase):
    def poll(self, yaml=None):
        mem = TP.make_iracing_memory(values=TP.ir_values(), yaml=yaml)
        p = IRacingProvider(opener=lambda: BytesMapping(mem))
        p.connect()
        return p.poll()

    def test_flair_name_becomes_country_code(self):
        snap = self.poll()
        self.assertEqual([c.country for c in snap.cars], ["br", "us"])

    def test_unknown_flair_is_none(self):
        snap = self.poll(TP.IR_YAML.replace("FlairName: Brazil", "FlairName: Narnia").replace(
            "FlairName: United States", "FlairName: "))
        self.assertEqual([c.country for c in snap.cars], [None, None])


class TestFlagDownload(unittest.TestCase):
    PNG = PNG_SIGNATURE + b"flag"

    def test_downloads_all_skips_existing_and_validates(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return b"<html>" if url.endswith("/pt.png") else self.PNG

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "br.png").write_bytes(self.PNG)  # já existe
            res = fetch_flags(Path(d), fetch)
            self.assertEqual(res.skipped, 1)
            self.assertNotIn("br", res.downloaded)
            self.assertIn("us", res.downloaded)
            self.assertTrue(any(e.startswith("pt:") for e in res.errors))  # arquivo inválido
            self.assertFalse((Path(d) / "pt.png").exists())
            self.assertIn(FLAG_URL.format(code="us"), calls)
            self.assertNotIn(FLAG_URL.format(code="br"), calls)
            self.assertEqual(len(installed_flags(Path(d))), len(ALL_CODES) - 1)
            self.assertIn("bandeiras baixadas", res.summary)

    def test_only_requested_codes_and_progress(self):
        seen = []
        with tempfile.TemporaryDirectory() as d:
            res = fetch_flags(Path(d), lambda u: self.PNG, codes=["br", "us", "gb-eng"],
                              progress=lambda i, n: seen.append((i, n)))
            self.assertEqual(sorted(res.downloaded), ["br", "gb-eng", "us"])
            self.assertEqual(seen, [(1, 3), (2, 3), (3, 3)])

    def test_no_internet_stops_early_with_a_clear_message(self):
        attempts = []

        def fetch(url):
            attempts.append(url)
            raise OSError("sem rede")

        with tempfile.TemporaryDirectory() as d:
            res = fetch_flags(Path(d), fetch)
            self.assertTrue(res.fatal)
            self.assertIn("internet", res.summary)
            self.assertLessEqual(len(attempts), 5)  # não insiste nos ~250 arquivos
            self.assertEqual(installed_flags(Path(d)), [])


if __name__ == "__main__":
    unittest.main()
