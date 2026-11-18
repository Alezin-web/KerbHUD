"""Catálogo de carros reais (iRacing 2026 e Le Mans Ultimate) -> fabricante esperada.

A lista do iRacing vem da relação oficial publicada (mais de 170 carros). `None` = carro SEM fabricante identificável
(oval/dirt genéricos): nesses o app não inventa marca.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from kerbhud.core.brands import BRAND_KEYS, BRANDS, brand_by_key, brand_for
from kerbhud.core.logos import (BASE, CANDIDATES, INDEX_URL, PNG_SIGNATURE, SUPPORTED_EXT, fetch_logos,
                                   installed_logos, logo_file, logos_status)

IRACING = [
    # NASCAR / stock car
    ("Next Gen NASCAR Cup Series Chevrolet Camaro ZL1", "chevrolet"), ("Next Gen NASCAR Cup Series Ford Mustang", "ford"),
    ("Next Gen NASCAR Cup Series Toyota Camry", "toyota"), ("NASCAR Xfinity Series Chevrolet Camaro", "chevrolet"),
    ("NASCAR Xfinity Series Ford Mustang", "ford"), ("NASCAR Xfinity Series Toyota Supra", "toyota"),
    ("NASCAR Truck Series Chevrolet Silverado", "chevrolet"), ("NASCAR Truck Series Ram", "ram"),
    ("NASCAR Truck Series Toyota Tundra TRD", "toyota"), ("ARCA Chevrolet SS", "chevrolet"),
    ("ARCA Ford Mustang", "ford"), ("ARCA Toyota Camry", "toyota"), ("NASCAR Whelen Tour Modified", None),
    ("SK Modified Car", None), ("Gen 4 Chevrolet Monte Carlo – 2003", "chevrolet"), ("Gen 4 Ford Taurus – 2003", "ford"),
    ("NASCAR Legends Buick LeSabre – 1987", "buick"), ("NASCAR Legends Ford Thunderbird – 1987", "ford"),
    ("NASCAR Legends Pontiac Grand Prix – 1987", "pontiac"), ("NASCAR Legends Chevrolet Monte Carlo – 1987", "chevrolet"),
    ("Late Model Stock", None), ("Super Late Model", None), ("SRX", None), ("Street Stock – Panther (included)", None),
    ("Street Stock – Eagle", None), ("Street Stock – Casino", None), ("Mini Stock (included)", None),
    ("Legends Ford '34 Coupe (included)", "ford"), ("NASCAR Cup Series Ford Fusion", "ford"),
    ("NASCAR Chevrolet SS Cup Car", "chevrolet"), ("NASCAR Gen 4 Cup", None),
    ("NASCAR Chevrolet Impala SS COT circa 2013", "chevrolet"), ("NASCAR Truck Chevrolet Silverado – 2008", "chevrolet"),
    ("JR Motorsports Street Stock", None),
    # GT / turismo / road
    ("Porsche 911 Cup (992.2)", "porsche"), ("Aston Martin GT3 EVO", "astonmartin"), ("Ford Mustang GT4", "ford"),
    ("Acura NSX GT3 EVO 22", "acura"), ("Audi R8 LMS EVO II GT3", "audi"), ("BMW M4 GT3 EVO", "bmw"),
    ("Chevrolet Corvette Z06 GT3.R", "corvette"), ("Ferrari 296 GT3", "ferrari"), ("Ford Mustang GT3", "ford"),
    ("Lamborghini Huracán GT3 EVO", "lamborghini"), ("Lamborghini Huracan GT3 EVO2", "lamborghini"),
    ("McLaren 720S GT3 EVO", "mclaren"), ("Mercedes-AMG GT3 2020", "mercedes"), ("Porsche 911 GT3 R (992)", "porsche"),
    ("Ferrari 296 Challenge", "ferrari"), ("Porsche 911 Cup (992.1)", "porsche"),
    ("Supercars Chevrolet Camaro Gen 3", "chevrolet"), ("Supercars Ford Mustang Gen 3", "ford"),
    ("Aston Martin Vantage GT4", "astonmartin"), ("BMW M4 G82 GT4 Evo", "bmw"), ("McLaren 570S GT4", "mclaren"),
    ("Mercedes-AMG GT4", "mercedes"), ("Porsche 718 Cayman GT4 Clubsport", "porsche"), ("Audi RS 3 LMS TCR", "audi"),
    ("Audi RS 3 LMS Gen2 TCR", "audi"), ("Hyundai Elantra N TCR", "hyundai"), ("Hyundai Veloster N TCR", "hyundai"),
    ("Honda Civic Type R TCR", "honda"), ("BMW M2 CS Racing (included)", "bmw"), ("Renault Clio R.S. V", "renault"),
    ("Toyota GR86 (included)", "toyota"), ("Global Mazda MX-5 Cup (included)", "mazda"),
    ("Stockcar Brasil Chevrolet Cruze", "chevrolet"), ("Stockcar Brasil Toyota Corolla", "toyota"),
    ("BMW M8 GTE", "bmw"), ("Chevrolet Corvette C8.R", "corvette"), ("Ferrari 488 GTE", "ferrari"),
    ("Ford GT GTE", "ford"), ("Porsche 911 RSR", "porsche"), ("Porsche Mission R", "porsche"),
    ("Chevrolet Corvette C6.R", "corvette"), ("Aston Martin DBR9 GT1", "astonmartin"), ("Cadillac CTS-V (included)", "cadillac"),
    ("Kia Optima (included)", "kia"), ("Ford Mustang FR500S", "ford"), ("Audi 90 GTO", "audi"), ("Ferrari 488 GT3", "ferrari"),
    ("McLaren MP4-12C GT3", "mclaren"), ("BMW Z4 GT3", "bmw"), ("Ford GT-R", "ford"), ("Audi R8 LMS GT3", "audi"),
    ("Ferrari 488 GT3 Evo 2020", "ferrari"), ("Mercedes-AMG GT3", "mercedes"), ("Porsche 911 GT3 R", "porsche"),
    ("Supercars Ford Mustang GT", "ford"), ("Supercars Holden ZB Commodore", "holden"),
    ("V8 Supercar Holden VF Commodore – 2014", "holden"), ("V8 Supercar Ford FG Falcon – 2014", "ford"),
    ("V8 Supercar Ford Falcon – 2009", "ford"), ("Porsche 911 GT3 Cup", "porsche"), ("BMW M4 F82 GT4 – 2018", "bmw"),
    ("RUF Rt 12 R", "ruf"), ("Volkswagen Jetta TDi (included)", "volkswagen"), ("Pontiac Solstice Club Sport", "pontiac"),
    ("Pontiac Solstice Club Sport – Rookie", "pontiac"), ("Mazda MX-5 Cup – 2010", "mazda"),
    ("Mazda MX-5 Roadster – 2010", "mazda"), ("Toyota GR86 Cup Car", "toyota"),
    # protótipos
    ("Ferrari 499P", "ferrari"), ("Acura ARX-06 GTP", "acura"), ("Porsche 963 GTP", "porsche"),
    ("Cadillac V-Series.R GTP", "cadillac"), ("BMW M Hybrid V8", "bmw"), ("BMW M Hybrid V8 Evo", "bmw"),
    ("Ligier JS P320", "ligier"), ("Dallara P217 LMP2", "dallara"), ("Radical SR10", "radical"),
    ("Porsche 919 LMP1", "porsche"), ("Audi R18 LMP1", "audi"), ("Chevrolet Corvette C7 Daytona Prototype", "corvette"),
    ("HPD ARX 01c", "acura"), ("Riley Mk XX Daytona Prototype", "riley"), ("Nissan GTP ZX-T", "nissan"),
    ("Radical SR8 V8 (included)", "radical"), ("SCCA Spec Racer Ford (included)", "ford"),
    ("Aston Martin Valkyrie AMR-LMH", "astonmartin"),
    # monopostos
    ("Dallara IL-15", "dallara"), ("Super Formula Lights", "dallara"), ("Dallara 324 Super Formula Lights", "dallara"),
    ("Super Formula SF23 – Honda", "honda"), ("Super Formula SF23 – Toyota", "toyota"), ("Ray FF1600 (included)", "ray"),
    ("Ray Race Cars Formula Ford 1600", "ray"), ("Mercedes-AMG F1 W13 E Performance", "mercedes"),
    ("Mercedes-AMG F1 W12 E Performance", "mercedes"), ("Indy Pro 2000", None), ("FIA F3", None), ("FIA F4", None),
    ("Dallara iR-01", "dallara"), ("Formula Vee (included)", None), ("USF2000", None), ("McLaren Honda MP4-30", "mclaren"),
    ("Williams-Toyota FW31", "williams"), ("Dallara IR18 INDYCAR", "dallara"), ("Formula Renault 3.5", "renault"),
    ("Dallara F3", "dallara"), ("Formula Renault 2.0", "renault"), ("Pro Mazda", "mazda"),
    ("Skip Barber Formula 2000", "skipbarber"), ("Lotus 49", "lotus"), ("Lotus 79", "lotus"),
    ("C&R Racing Silver Crown Car", None), ("Sprint Car", None), ("Dallara DW12", "dallara"),
    ("Dallara IR05 – Circa 2009", "dallara"), ("Sabre Racing Cars Formula Vee - Cutlass", "sabre"),
    ("Sheane Formula Vee - Classic", "sheane"), ("iRacing Formula iR-04", None),
    # dirt / rallycross / off-road
    ("Mini Stock – Dirt (included)", None), ("DIRTcar 358 Small Block Modified", None),
    ("Super DIRTcar Big Block Modified", None), ("World of Outlaws 410 Sprint Car", None), ("DIRTcar 360 Sprint Car", None),
    ("DIRTcar 305 Sprint Car", None), ("Dirt Micro Sprint (included)", None), ("Dirt Outlaw Micro Sprint – Winged", None),
    ("Dirt Midget", None), ("World of Outlaws Super Late Model", None), ("DIRTcar Pro Late Model", None),
    ("DIRTcar Limited Late Model", None), ("USAC 410 Sprint Car", None), ("USAC 360 Sprint Car", None),
    ("UMP Modified (included)", None), ("NASCAR Truck Series Dirt Chevrolet Silverado", "chevrolet"),
    ("NASCAR Truck Series Dirt Toyota Tundra TRD", "toyota"), ("Dirt Legends Ford '34 Coupe (included)", "ford"),
    ("NASCAR Truck Series Dirt Ford F-150", "ford"), ("Dirt Street Stock (included)", None),
    ("FIA Cross Car (included)", "ligier"), ("Ligier FIA Cross Car", "ligier"), ("Subaru WRX STI", "subaru"),
    ("Ford Fiesta RS WRC", "ford"), ("VW Beetle (included)", "volkswagen"), ("VW Beetle Lite (included)", "volkswagen"),
    ("Lucas Oil Off Road Pro 2 Truck", None), ("Lucas Oil Off Road Pro 4 Truck", None),
    ("Lucas Oil Off-Road Pro 2 Lite Truck (included)", None),
]

LMU = [
    ("Toyota GR010 Hybrid", "toyota"), ("Ferrari 499P", "ferrari"), ("Porsche 963", "porsche"), ("Peugeot 9X8", "peugeot"),
    ("Cadillac V-Series.R", "cadillac"), ("Alpine A424", "alpine"), ("BMW M Hybrid V8", "bmw"),
    ("Lamborghini SC63", "lamborghini"), ("Glickenhaus SCG 007 LMH", "glickenhaus"),
    ("Vanwall Vandervell 680", "vanwall"), ("Isotta Fraschini Tipo6-C", "isotta"), ("Aston Martin Valkyrie AMR-LMH", "astonmartin"),
    ("Genesis GMR-001", "genesis"), ("Oreca 07 Gibson", "oreca"), ("Ligier JS P320", "ligier"),
    ("Ginetta G61-LT-P3 Evo", "ginetta"), ("Duqueine D08", "duqueine"),
    ("Aston Martin Vantage AMR GT3 Evo", "astonmartin"), ("BMW M4 GT3 Evo", "bmw"), ("Chevrolet Corvette Z06 GT3.R", "corvette"),
    ("Ferrari 296 GT3", "ferrari"), ("Ford Mustang GT3", "ford"), ("Lamborghini Huracan GT3 Evo2", "lamborghini"),
    ("Lexus RC F GT3", "lexus"), ("McLaren 720S GT3 Evo", "mclaren"), ("Mercedes-AMG GT3 Evo", "mercedes"),
    ("Porsche 911 GT3 R LMGT3", "porsche"), ("Chevrolet Corvette C8.R", "corvette"), ("Ferrari 488 GTE Evo", "ferrari"),
    ("Porsche 911 RSR-19", "porsche"), ("Aston Martin Vantage AMR", "astonmartin"),
    ("Team 51 #51:LM", None),  # só equipe e número: sem pista sobre a marca
]


class TestCarCatalog(unittest.TestCase):
    def test_every_iracing_car_resolves_to_the_expected_manufacturer(self):
        wrong = []
        for name, expected in IRACING:
            b = brand_for(name)
            got = b.key if b else None
            if got != expected:
                wrong.append((name, expected, got))
        self.assertEqual(wrong, [], "carros do iRacing com fabricante errada ou ausente")
        self.assertGreater(len(IRACING), 170)  # mais de 170 carros do catálogo oficial

    def test_every_lmu_car_resolves_to_the_expected_manufacturer(self):
        wrong = [(n, e, (brand_for(n).key if brand_for(n) else None)) for n, e in LMU
                 if (brand_for(n).key if brand_for(n) else None) != e]
        self.assertEqual(wrong, [])

    def test_user_reported_cars_now_have_a_brand(self):
        """LMP3 (Ligier JS P320) e Formula 1600 (Ray FF1600) não tinham marca."""
        self.assertEqual(brand_for("Ligier JS P320").key, "ligier")
        self.assertEqual(brand_for("Ligier JS P320 LMP3").key, "ligier")
        self.assertEqual(brand_for("Ray FF1600").key, "ray")
        self.assertEqual(brand_for("Ray Race Cars Formula Ford 1600").name, "Ray")
        # o iRacing manda "CarPath CarScreenName": a marca sai de qualquer um dos dois textos
        self.assertEqual(brand_for("ligierjsp320", "Ligier JS P320").key, "ligier")
        self.assertEqual(brand_for("formulaford", "Ray FF1600").key, "ray")

    def test_honda_and_acura_are_different_brands(self):
        self.assertEqual(brand_for("Honda Civic Type R TCR").key, "honda")
        self.assertEqual(brand_for("Acura NSX GT3 EVO 22").key, "acura")
        self.assertEqual(brand_for("McLaren Honda MP4-30").key, "mclaren")  # construtor, não o motor

    def test_whole_word_rules_avoid_false_positives_in_team_names(self):
        for text in ("Crawford Racing #7", "Claudio Silva #12", "Array Motorsport", "Rayo Team", "Rams Racing",
                     "Fordham Autosport", "Stafford Competition", "Kiara Team", "Programa Racing", "Miniature Cars"):
            self.assertIsNone(brand_for(text), text)
        self.assertEqual(brand_for("Crawford Racing #7 Porsche 963").key, "porsche")  # a marca real ainda aparece
        self.assertEqual(brand_for("Chevrolet Corvette Stingray").key, "corvette")

    def test_generic_oval_and_dirt_cars_never_get_an_invented_brand(self):
        for name, expected in IRACING:
            if expected is None:
                self.assertIsNone(brand_for(name), name)


class TestBrandCatalogIntegrity(unittest.TestCase):
    def test_keys_are_unique_and_lowercase_filenames(self):
        self.assertEqual(len(BRAND_KEYS), len(set(BRAND_KEYS)))
        for b in BRANDS:
            self.assertRegex(b.key, r"^[a-z0-9]+$", b.key)
            self.assertTrue(b.name, b.key)  # todo marca tem nome completo (usado quando não há arquivo de logo)
            self.assertRegex(b.color, r"^#[0-9a-f]{6}$")
            self.assertEqual(brand_by_key(b.key), b)
        self.assertGreaterEqual(len(BRANDS), 48)

    def test_every_brand_is_known_to_the_logo_downloader(self):
        self.assertEqual(set(BRAND_KEYS) - set(CANDIDATES), set())  # nenhuma marca fora do download
        self.assertEqual(set(CANDIDATES) - set(BRAND_KEYS), set())  # e nenhuma sobrando
        for key in ("ray", "sabre", "sheane", "skipbarber"):
            self.assertEqual(CANDIDATES[key], ())  # construtores de corrida: não esperamos achar no repositório

    def test_fallback_keys_exist(self):
        for b in BRANDS:
            if b.fallback:
                self.assertIn(b.fallback, BRAND_KEYS)
        self.assertEqual(brand_by_key("corvette").fallback, "chevrolet")


class TestLogoFiles(unittest.TestCase):
    PNG = PNG_SIGNATURE + b"x"

    def test_logo_file_accepts_several_formats_in_preference_order(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            self.assertIsNone(logo_file(d, "ray"))
            (d / "ray.svg").write_text("<svg/>")
            self.assertEqual(logo_file(d, "ray").name, "ray.svg")
            (d / "ray.jpg").write_bytes(b"jpg")
            self.assertEqual(logo_file(d, "ray").name, "ray.jpg")  # jpg antes de svg
            (d / "ray.png").write_bytes(self.PNG)
            self.assertEqual(logo_file(d, "ray").name, "ray.png")  # png tem preferência
            self.assertEqual(SUPPORTED_EXT[0], "png")
            (d / "ray.txt").write_text("não é imagem")
            self.assertEqual(installed_logos(d), ["ray"])

    def test_status_lists_installed_and_missing_with_download_hint(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bmw.png").write_bytes(self.PNG)
            (Path(d) / "ligier.webp").write_bytes(b"w")
            st = {s.key: s for s in logos_status(Path(d))}
            self.assertEqual(len(st), len(BRANDS))
            self.assertIsNotNone(st["bmw"].path)
            self.assertIsNotNone(st["ligier"].path)
            self.assertIsNone(st["ray"].path)
            self.assertFalse(st["ray"].in_dataset)  # sem chance de baixar: o usuário precisa colocar o arquivo
            self.assertTrue(st["ferrari"].in_dataset)

    def _fake_server(self, slugs):
        def fetch(url):
            if url == INDEX_URL:
                import json
                return json.dumps([{"name": s.title(), "slug": s, "image": {"optimized": f"{BASE}/optimized/{s}.png"}}
                                   for s in slugs]).encode()
            return self.PNG
        return fetch

    def test_download_covers_all_brands_found_and_reports_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            res = fetch_logos(Path(d), self._fake_server(["bmw", "honda", "kia", "volkswagen", "renault", "subaru",
                                                           "dallara", "ligier"]))
            self.assertEqual(sorted(res.downloaded), ["bmw", "dallara", "honda", "kia", "ligier", "renault", "subaru",
                                                      "volkswagen"])
            self.assertIn("ray", res.missing)  # não existe no repositório
            self.assertIn("skipbarber", res.missing)
            self.assertIn("Ray", res.summary)  # a mensagem usa o nome da fabricante
            self.assertIn("coloque", res.summary.lower())  # e diz o que fazer

    def test_download_never_overwrites_files_the_user_placed_in_any_format(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "bmw.svg").write_text("<svg>meu logo</svg>")  # o usuário colocou o seu (svg)
            (d / "honda.png").write_bytes(self.PNG + b"meu")
            res = fetch_logos(d, self._fake_server(["bmw", "honda", "kia"]))
            self.assertEqual(res.downloaded, ["kia"])  # só o que faltava
            self.assertEqual((d / "bmw.svg").read_text(), "<svg>meu logo</svg>")
            self.assertEqual((d / "honda.png").read_bytes(), self.PNG + b"meu")
            self.assertFalse((d / "bmw.png").exists())
            res = fetch_logos(d, self._fake_server(["bmw", "honda", "kia"]), overwrite=True)  # só se pedir
            self.assertIn("honda", res.downloaded)


if __name__ == "__main__":
    unittest.main()
