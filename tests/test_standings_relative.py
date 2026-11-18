import random
import unittest
from pathlib import Path

from kerbhud.core.animation import MOVE_S, NEUTRAL, SlotAnimator
from kerbhud.core.brands import brand_for
from kerbhud.core.classes import class_style, license_color, text_on
from kerbhud.core.gridtracker import StartGridTracker
from kerbhud.core.irating import format_ir, projected_changes, sof
from kerbhud.core.layout import MODULES, PRESETS, design_size
from kerbhud.core.logos import BASE, CANDIDATES, INDEX_URL, PNG_SIGNATURE, _index, fetch_logos, installed_logos
from kerbhud.core.model import (CarState, CarStatus, DriverProfile, ProfileSource, SessionState, Sim,
                                   Snapshot)
from kerbhud.core import relative as rel_core
from kerbhud.core.standings import NAME_FONT_PX as ST_NAME_PX
from kerbhud.core.standings import NAME_W, NRG_TEXT_X, NUM2_FONT_PX, NUM_FONT_PX, WIDTHS
from kerbhud.core.relative import (STATE_ALERT, STATE_DANGER, STATE_FAVORABLE, STATE_NEUTRAL,
                                      RelativeEntry, RelativeOptions, RelativeTracker, get_relative_options,
                                      relative_design_size, wrap_delta)
from kerbhud.core.sessioninfo import build_session_bar, session_letter
from kerbhud.core.standings import (DROP_ORDER, FOOTER_H, HeaderLine, MAX_AUTO_ROWS, MIN_ROWS, PAD_BOTTOM,
                                       ROW_H, TOP_H, StandingsOptions, build_standings, column_layout,
                                       columns_width, fit_columns, fit_rows, get_standings_options, ir_deltas,
                                       select_lines, select_rows, standings_design_size)
from kerbhud.core.textfmt import (fit_font_px, format_clock, format_gap, format_laptime, format_remaining,
                                     format_total, is_race)
from kerbhud.core.tires import compound_color, normalize_compound


def car(idx, pos, cls="GT3", **kw):
    kw.setdefault("driver_name", f"Driver {idx}")
    kw.setdefault("car_number", str(idx))
    return CarState(idx=idx, position=pos, class_name=cls, **kw)


def snap(cars, session_type="Race", me=None, profile=None, sim=Sim.LMU, track=5000.0, **sk):
    for c in cars:
        c.is_player = (c.idx == me)
    return Snapshot(sim=sim, connected=True, cars=cars, player_idx=me,
                    session=SessionState(active=True, session_type=session_type, track_length_m=track, **sk),
                    profile=profile or DriverProfile())


# --------------------------------------------------------------------------- #
class TestClassesBrandsTires(unittest.TestCase):
    def test_known_classes_and_variants(self):
        self.assertEqual(class_style("LMP2_ELMS").label, "LMP2")
        self.assertEqual(class_style("LMGT3").label, "GT3")
        self.assertEqual(class_style("GT3 Class").label, "GT3")
        self.assertEqual(class_style("Hypercar").label, "HYPER")
        self.assertEqual(class_style("GTP").label, "GTP")
        self.assertEqual(class_style("LMP3").label, "LMP3")
        self.assertEqual(class_style("GTD PRO").label, "GTD")
        self.assertEqual(class_style("DP").label, "DP")

    def test_palette_per_simulator(self):
        lmu = lambda raw: class_style(raw, None, Sim.LMU).color  # noqa: E731
        ir = lambda raw: class_style(raw, None, Sim.IRACING).color  # noqa: E731
        self.assertEqual(lmu("LMP2_ELMS"), "#4cc9f0")  # azul claro
        self.assertEqual(ir("LMP2"), "#4cc9f0")
        self.assertEqual(lmu("Hypercar"), "#e10600")  # vermelho (LMU)
        self.assertEqual(ir("GTP"), "#f5c400")  # amarelo (iRacing)
        self.assertEqual(ir("DP"), "#f5c400")
        self.assertEqual(lmu("GT3"), "#14c05a")  # verde (LMU)
        self.assertEqual(lmu("LMGT3"), "#14c05a")
        self.assertEqual(ir("GT3 Class"), "#ec4b73")  # vermelho rosado (IMSA / iRacing)
        self.assertEqual(ir("GTD"), "#ec4b73")
        self.assertEqual(class_style("GT3").color, "#14c05a")  # sem simulador: padrão LMU
        self.assertEqual(class_style("GT3", None, "iracing").color, "#ec4b73")  # aceita o valor em texto
        self.assertEqual(class_style("GT3", None, Sim.DEMO).color, "#14c05a")
        colors = {lmu("Hypercar"), lmu("LMP2"), lmu("GT3"), ir("GT3"), ir("GTP")}
        self.assertEqual(len(colors), 5)  # todas distintas entre si

    def test_provided_color_only_for_unknown_classes_and_unknown_is_stable(self):
        self.assertEqual(class_style("GT3", "#123456", Sim.IRACING).color, "#ec4b73")  # paleta vence nas conhecidas
        self.assertEqual(class_style("Foo", "#abcdef").color, "#abcdef")  # desconhecida: vale a cor do simulador
        a, b = class_style("Formula Vee"), class_style("Formula Vee")
        self.assertEqual(a, b)
        self.assertEqual(a.label, "FVee")
        self.assertEqual(class_style(None).label, "")

    def test_text_contrast_and_license_colors(self):
        self.assertEqual(text_on("#e10600"), "#ffffff")
        self.assertEqual(text_on("#f5c400"), "#111111")
        self.assertEqual(text_on("lixo"), "#ffffff")
        self.assertEqual(license_color("a"), license_color("A"))
        self.assertNotEqual(license_color("A"), license_color("R"))

    def test_brands_from_model_or_file_and_never_guess(self):
        self.assertEqual(brand_for("BMW M4 GT3").label, "BMW")
        self.assertEqual(brand_for(None, "Team 5 #5 ferrari_499p.veh").label, "FER")
        self.assertEqual(brand_for("Aston Martin Vantage GT3").label, "AM")
        self.assertEqual(brand_for("Mercedes-AMG GT3 2020").label, "MB")
        self.assertEqual(brand_for("Porsche 963 GTP").key, "porsche")
        self.assertEqual(brand_for("Toyota GR010 Hybrid").label, "TOY")
        corvette = brand_for("Chevrolet Corvette Z06 GT3.R")
        self.assertEqual((corvette.key, corvette.fallback), ("corvette", "chevrolet"))  # sem logo própria: bowtie
        self.assertEqual(brand_for("Chevrolet Camaro GT4").key, "chevrolet")
        self.assertIsNone(brand_for("Toyota GR010").fallback)
        self.assertIsNone(brand_for("Team 51 #51:LM"))  # nome que não revela marca: não chuta
        self.assertIsNone(brand_for(None, None))
        self.assertIsNone(brand_for(""))

    def test_tires(self):
        self.assertEqual([normalize_compound(x) for x in ("Soft", "Medium", "Hard", "Wet", "Intermediate")],
                         ["S", "M", "H", "W", "I"])
        self.assertEqual(normalize_compound("Slick"), "D")
        self.assertEqual(normalize_compound("Xtreme"), "X")
        self.assertIsNone(normalize_compound(""))
        self.assertIsNone(normalize_compound(None))
        self.assertNotEqual(compound_color("S"), compound_color("H"))
        self.assertEqual(compound_color("?"), compound_color(None))


class TestFormatting(unittest.TestCase):
    def test_laptime_and_gap(self):
        self.assertEqual(format_laptime(83.456), "1:23.456")
        self.assertEqual(format_laptime(None), "—")
        self.assertEqual(format_laptime(-1), "—")
        self.assertEqual(format_gap(0.5), "+0.500")
        self.assertEqual(format_gap(12.34), "+12.3")
        self.assertEqual(format_gap(125.0), "+2:05.0")
        self.assertEqual(format_gap(None), "—")
        self.assertEqual(format_gap(3.0, laps=2), "+2L")
        self.assertEqual(format_gap(-0.2), "+0.000")

    def test_clock_total_remaining_and_race_detection(self):
        self.assertEqual(format_clock(1207), "00:20:07")
        self.assertEqual(format_clock(3725), "01:02:05")
        self.assertEqual(format_clock(None), "")
        self.assertEqual(format_total(2700), "00:45m")
        self.assertEqual(format_total(5400), "01:30m")
        self.assertEqual(format_total(None), "")
        self.assertEqual(format_remaining(2483), "41:23")
        self.assertEqual(format_remaining(7325), "2:02:05")
        self.assertTrue(is_race("Race (DEMO)"))
        self.assertFalse(is_race("Practice"))

    def test_fit_font_px_shrinks_instead_of_abbreviating(self):
        width = lambda px: len("Matthew Richard Beaumont") * 0.55 * px  # noqa: E731  (largura ~ proporcional)
        self.assertEqual(fit_font_px(18.0, 300.0, width), 18.0)  # cabe: tamanho cheio
        px = fit_font_px(18.0, 200.0, width)
        self.assertLess(px, 18.0)
        self.assertLessEqual(width(px), 200.0)  # e agora cabe
        self.assertGreater(width(px + 1.0), 200.0 - 1e-6 + 0.0) if px + 1 <= 18.0 else None
        self.assertEqual(fit_font_px(18.0, 50.0, width, min_px=11.0), 11.0)  # nunca abaixo do mínimo
        self.assertEqual(fit_font_px(18.0, 100.0, lambda px: 0.0), 18.0)  # texto vazio
        # largura NÃO proporcional (ajuste fino): termina e respeita o limite
        odd = lambda px: 40.0 + px * 9.0  # noqa: E731
        px = fit_font_px(20.0, 150.0, odd)
        self.assertLessEqual(odd(px), 150.0)


class TestIRating(unittest.TestCase):
    def test_sof(self):
        self.assertAlmostEqual(sof([2000] * 5), 2000.0, places=3)
        v = sof([1000, 3000])
        self.assertTrue(1780 < v < 1800, v)  # pondera mais os pilotos mais fracos que a média (2000)
        self.assertIsNone(sof([]))
        self.assertEqual(format_ir(1800), "1.8k")
        self.assertEqual(format_ir(950), "950")
        self.assertEqual(format_ir(None), "")

    def test_projection_properties(self):
        eq = projected_changes([(i, 2000.0, i + 1) for i in range(6)])
        vals = [eq[i] for i in range(6)]
        self.assertEqual(vals, sorted(vals, reverse=True))  # melhor posição, mais pontos
        self.assertGreater(vals[0], 0)
        self.assertLess(vals[-1], 0)
        self.assertLessEqual(abs(sum(vals)), 6)  # soma ~ zero (só arredondamento)
        # vencer de quem tem iRating maior rende mais que vencer de quem tem menor
        underdog = projected_changes([("a", 1000.0, 1), ("b", 3000.0, 2)])["a"]
        favorite = projected_changes([("a", 3000.0, 1), ("b", 1000.0, 2)])["a"]
        self.assertGreater(underdog, favorite)
        self.assertEqual(projected_changes([("a", 2000.0, 1)]), {})
        rnd = random.Random(7)
        entries = [(i, rnd.uniform(800, 4500), i + 1) for i in range(30)]
        res = projected_changes(entries)
        self.assertLessEqual(abs(sum(res.values())), 30)

    def test_deltas_per_class_only_for_rated_cars(self):
        cars = [car(1, 1, "GT3", irating=2000), car(2, 2, "GT3", irating=2000), car(3, 3, "LMP2", irating=1500),
                car(4, 4, "GT3", irating=None)]
        d = ir_deltas(cars)
        self.assertEqual(set(d), {1, 2})  # LMP2 tem 1 só (sem comparação); carro sem iRating fica de fora
        self.assertGreater(d[1], d[2])


class TestGridTracker(unittest.TestCase):
    def test_gain_loss_and_resets(self):
        g = StartGridTracker()
        s1 = snap([car(1, 1), car(2, 2), car(3, 3)], track="X")
        self.assertEqual(g.update(s1), {1: 0, 2: 0, 3: 0})
        s2 = snap([car(1, 2), car(2, 1), car(3, 3), car(4, 4)])
        out = g.update(s2)
        self.assertEqual((out[1], out[2], out[3]), (-1, 1, 0))
        self.assertEqual(out[4], 0)  # quem entrou depois: referência = 1ª vez visto
        # mudança de sessão reinicia
        s3 = snap([car(1, 3), car(2, 1)], session_type="Race")
        s3.session.track_name = "OUTRA"
        self.assertEqual(g.update(s3), {1: 0, 2: 0})
        # fora de corrida não há ganho/perda
        self.assertEqual(g.update(snap([car(1, 1)], session_type="Practice")), {})
        self.assertEqual(g.update(Snapshot(connected=False)), {})


class TestSessionBar(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(session_letter("Race"), ("R", "RACE"))
        self.assertEqual(session_letter("Qualifying"), ("Q", "QUALIFY"))
        self.assertEqual(session_letter("Open Qualify"), ("Q", "QUALIFY"))
        self.assertEqual(session_letter("Practice"), ("P", "PRACTICE"))
        self.assertEqual(session_letter("Warmup")[0], "W")
        self.assertEqual(session_letter("Test Day")[0], "T")
        self.assertEqual(session_letter(None)[0], "?")

    def test_race_bar_time_incidents_laps_cars_and_sof(self):
        me = car(0, 1, "GT3", laps_completed=11, lap_dist_pct=0.3, est_lap_time=100.0, irating=2000)
        other = car(1, 2, "GT3", laps_completed=11, lap_dist_pct=0.2, irating=2000)
        s = snap([me, other], me=0, elapsed_s=900.0, total_s=2700.0, time_remaining_s=1800.0,
                 incidents=6, incident_limit=25)
        bar = build_session_bar(s)
        self.assertEqual((bar.letter, bar.name), ("R", "RACE"))
        self.assertEqual(bar.time_text, "00:15:00 / 00:45m")
        self.assertEqual(bar.incidents_text, "6/25")
        self.assertEqual(bar.lap_text, "12/~29.3")  # 11,3 feitas + 1800 s / 100 s = 29,3
        self.assertEqual(bar.cars_count, 2)
        self.assertEqual(bar.sof_text, "2.0k")

    def test_lap_limited_unlimited_incidents_and_fallbacks(self):
        me = car(0, 1, laps_completed=11, lap_dist_pct=0.3)
        s = snap([me], me=0, laps_total=25, incidents=3)
        bar = build_session_bar(s)
        self.assertEqual((bar.lap_text, bar.incidents_text, bar.sof_text), ("12/25", "3", ""))
        s = snap([me], me=0, time_remaining_s=1800.0)
        self.assertEqual(build_session_bar(s).time_text, "-30:00")  # só o restante é conhecido
        s = snap([me], session_type="Practice", me=0, elapsed_s=61.0)
        b = build_session_bar(s)
        self.assertEqual((b.time_text, b.lap_text, b.incidents_text), ("00:01:01", "12", ""))
        # corrida por tempo sem tempo de volta de referência: só a volta atual, nada estimado
        s = snap([car(0, 1, laps_completed=2)], me=0, time_remaining_s=900.0)
        self.assertEqual(build_session_bar(s).lap_text, "3")


# --------------------------------------------------------------------------- #
class TestStandings(unittest.TestCase):
    OPTS = StandingsOptions()

    def race_cars(self):
        return [
            car(1, 1, "Hypercar", class_position=1, gap_leader=0.0, laps_behind_leader=0),
            car(2, 2, "GT3", class_position=1, gap_leader=30.0, laps_behind_leader=0, best_lap=230.0),
            car(3, 3, "Hypercar", class_position=2, gap_leader=40.0, laps_behind_leader=0, best_lap=200.5),
            car(4, 4, "GT3", class_position=2, gap_leader=45.0, laps_behind_leader=0, best_lap=231.0),
            car(5, 5, "GT3", class_position=3, gap_leader=80.0, laps_behind_leader=1),
        ]

    def test_groups_by_class_ordered_by_leader_with_class_relative_gaps(self):
        v = build_standings(snap(self.race_cars(), me=4), self.OPTS)
        self.assertEqual([g.label for g in v.groups], ["HYPER", "GT3"])
        self.assertEqual([g.count for g in v.groups], [2, 3])
        hyper, gt3 = v.groups
        self.assertEqual([(r.pos_text, r.int_text, r.gap_text) for r in hyper.rows],
                         [("1", "—", "—"), ("2", "+40.0", "+40.0")])
        self.assertEqual([(r.pos_text, r.int_text, r.gap_text) for r in gt3.rows],
                         [("1", "—", "—"), ("2", "+15.0", "+15.0"), ("3", "+1L", "+1L")])
        self.assertEqual(v.mode, "race")
        self.assertEqual(v.player.car.idx, 4)

    def test_race_gap_missing_shows_dash_not_zero(self):
        cars = self.race_cars()
        cars[3].gap_leader = None
        v = build_standings(snap(cars, me=2), self.OPTS)
        gt3 = v.groups[1]
        self.assertEqual((gt3.rows[1].gap_text, gt3.rows[1].int_text), ("—", "—"))

    def test_single_class_uses_published_gap_ahead_as_fallback(self):
        cars = [car(1, 1, gap_leader=0.0), car(2, 2, gap_leader=None, gap_ahead=3.2)]
        v = build_standings(snap(cars, me=1), self.OPTS)
        self.assertEqual(v.rows[1].int_text, "+3.200")

    def test_practice_lists_only_timed_drivers_and_uses_best_lap_deltas(self):
        cars = [
            car(1, 1, "Hypercar", best_lap=200.0, gap_leader=999.0),  # "gap" publicado é lixo em treino
            car(2, 2, "GT3", best_lap=230.0), car(3, 3, "GT3", best_lap=231.0),
            car(4, 4, "GT3", best_lap=None, gap_leader=7.0),  # sem tempo: não aparece
            car(5, 5, "Hypercar", best_lap=201.5),
        ]
        v = build_standings(snap(cars, session_type="Practice", me=3), self.OPTS)
        self.assertEqual(v.mode, "best")
        self.assertFalse(v.hidden)
        hyper, gt3 = v.groups
        self.assertEqual([r.car.idx for r in hyper.rows], [1, 5])
        self.assertEqual([r.car.idx for r in gt3.rows], [2, 3])  # o carro 4 não fez tempo
        self.assertEqual([(r.gap_text, r.int_text) for r in hyper.rows], [("—", "—"), ("+1.500", "+1.500")])
        self.assertEqual([(r.gap_text, r.int_text) for r in gt3.rows], [("—", "—"), ("+1.000", "+1.000")])
        self.assertEqual(gt3.rows[0].best_text, "3:50.000")
        self.assertEqual([r.best_flag for r in hyper.rows], ["class", ""])
        self.assertEqual([r.best_flag for r in gt3.rows], ["class", ""])
        # o cabeçalho conta TODOS os pilotos da classe na sessão, não só os que têm tempo
        self.assertEqual([(g.label, g.header_count, g.count) for g in v.groups], [("HYPER", 2, 2), ("GT3", 3, 2)])

    def test_practice_positions_are_recomputed_from_lap_times(self):
        cars = [car(1, 1, "GT3", best_lap=101.0), car(2, 2, "GT3", best_lap=99.5),  # o simulador diz P1 para o mais lento
                car(3, 3, "GT3", best_lap=None, last_lap=100.2), car(4, 4, "LMP2", best_lap=95.0)]
        v = build_standings(snap(cars, session_type="Qualifying", me=1), self.OPTS)
        order = [(r.car.idx, r.pos_text) for g in v.groups for r in g.rows]
        self.assertEqual(order, [(4, "1"), (2, "1"), (3, "2"), (1, "3")])  # LMP2 lidera o grupo; GT3 por tempo
        self.assertEqual(v.groups[0].label, "LMP2")  # grupos na ordem do carro mais rápido
        self.assertEqual(v.groups[1].rows[1].car.idx, 3)  # só a última volta também classifica

    def test_practice_is_hidden_until_somebody_sets_a_lap_time(self):
        cars = [car(i, i, "GT3") for i in range(1, 6)]  # ninguém tem tempo ainda
        for kind in ("Practice", "Qualifying", "Open Qualify", "Warmup"):
            v = build_standings(snap(cars, session_type=kind, me=2), self.OPTS)
            self.assertTrue(v.hidden, kind)
            self.assertEqual(v.groups, [], kind)
        cars[3].last_lap = 104.2  # alguém completou uma volta
        v = build_standings(snap(cars, session_type="Practice", me=2), self.OPTS)
        self.assertFalse(v.hidden)
        self.assertEqual([r.car.idx for r in v.rows], [4])
        # na corrida nunca fica oculto, mesmo sem tempos
        self.assertFalse(build_standings(snap([car(i, i, "GT3") for i in range(1, 4)], me=2), self.OPTS).hidden)

    def test_race_lists_everyone_including_unpositioned_and_departed_dimmed(self):
        cars = [car(1, 1, gap_leader=0.0), car(2, 2, gap_leader=4.0),
                car(3, None, status=CarStatus.OUT, laps_completed=0),  # registrado, ainda fora do mundo
                CarState(idx=1004, position=3, class_name="GT3", driver_name="Saiu", car_number="9",
                         status=CarStatus.OUT, in_session=False, gap_leader=20.0)]  # saiu da sessão
        v = build_standings(snap(cars, me=2), self.OPTS)
        rows = {r.car.driver_name: r for r in v.rows}
        self.assertEqual(len(v.rows), 4)  # todos aparecem
        self.assertEqual([r.car.driver_name for r in v.rows][:3], ["Driver 1", "Driver 2", "Saiu"])  # ordem por posição
        self.assertEqual(v.rows[-1].car.idx, 3)  # sem posição: por último
        self.assertEqual((rows["Saiu"].dim, rows["Saiu"].status_tag), ("out", "OUT"))  # apagado
        self.assertEqual((rows["Driver 3"].dim, rows["Driver 3"].pos_text), ("out", "—"))
        self.assertEqual(rows["Driver 2"].dim, "none")
        self.assertEqual(v.groups[0].header_count, 4)  # o cabeçalho conta todos
        self.assertEqual(v.bar.cars_count, 3)  # a barra conta só quem está na sessão (3 dos 4 carros)

    def test_in_session_flag_dims_a_row_even_if_status_is_running(self):
        gone = car(1, 1, status=CarStatus.RUNNING, in_session=False)
        v = build_standings(snap([gone, car(2, 2)], me=2), self.OPTS)
        self.assertEqual(v.rows[0].dim, "out")

    def test_row_data_brand_rating_license_tire_energy_and_pos_change(self):
        c = car(1, 1, "GT3", car_model="BMW M4 GT3", irating=1800, license_class="A", license_sr=3.46,
                tire="S", energy_pct=80.0, best_lap=100.0, last_lap=101.0, laps_completed=12,
                vehicle_raw="bmwm4gt3")
        v = build_standings(snap([c, car(2, 2)], me=1), self.OPTS, pos_changes={1: 2, 2: -1})
        r = v.rows[0]
        self.assertEqual((r.brand.label, r.irating_text, r.license_class, r.license_sr_text),
                         ("BMW", "1.8k", "A", "3.5"))
        self.assertEqual((r.tire, r.energy_pct, r.pos_change, r.laps_text), ("S", 80.0, 2, "12"))
        self.assertEqual((r.best_text, r.last_text, r.number_text), ("1:40.000", "1:41.000", "1"))
        self.assertEqual(v.rows[1].pos_change, -1)
        self.assertIsNone(v.rows[1].brand)  # sem pista sobre a marca: nada é desenhado
        self.assertEqual((v.rows[1].tire, v.rows[1].energy_pct, v.rows[1].license_class), (None, None, ""))

    def test_ir_deltas_only_in_races(self):
        cars = [car(1, 1, irating=2500), car(2, 2, irating=2500), car(3, 3, irating=2500)]
        race = build_standings(snap(cars, me=2), self.OPTS)
        self.assertIsNotNone(race.rows[0].ir_delta)
        self.assertGreater(race.rows[0].ir_delta, race.rows[2].ir_delta)
        self.assertEqual(race.chips[0].label if race.chips[0].label == "iR" else "iR", "iR")
        practice = build_standings(snap(cars, session_type="Practice", me=2), self.OPTS)
        self.assertTrue(all(r.ir_delta is None for r in practice.rows))

    def test_dim_status_and_player(self):
        cars = [car(1, 1, "GT3"), car(2, 2, "LMP2"), car(3, 3, "GT3", status=CarStatus.PITS),
                car(4, 4, "GT3", status=CarStatus.OUT), car(5, 5, "GT3", status=CarStatus.GARAGE),
                car(6, 6, "GT3", status=CarStatus.DISQUALIFIED)]
        v = build_standings(snap(cars, me=1), self.OPTS)
        d = {r.car.idx: (r.dim, r.status_tag) for r in v.rows}
        self.assertEqual(d[1], ("none", ""))  # o piloto nunca fica esmaecido
        self.assertEqual(d[2], ("other_class", ""))
        self.assertEqual(d[3], ("pit", "PIT"))
        self.assertEqual(d[4], ("out", "OUT"))
        self.assertEqual(d[5], ("out", "GAR"))
        self.assertEqual(d[6], ("out", "DSQ"))

    def test_scope_class_only_my_group(self):
        v = build_standings(snap(self.race_cars(), me=4), StandingsOptions(scope="class"))
        self.assertEqual([g.label for g in v.groups], ["GT3"])
        self.assertEqual(v.total, 5)  # total geral de pilotos segue valendo

    def test_empty_snapshots_are_safe(self):
        race = build_standings(snap([], me=None), self.OPTS)
        self.assertEqual((race.groups, race.total, race.hidden), ([], 0, False))  # corrida vazia: sem ocultar
        practice = build_standings(snap([], session_type="Practice", me=None), self.OPTS)
        self.assertTrue(practice.hidden)

    def test_profile_chips_iracing_lmu_and_unavailable(self):
        cars = [car(1, 1, irating=2710), car(2, 2, irating=2000)]
        ir = DriverProfile(license_class="A", license_sr=3.456, irating=2710, source=ProfileSource.LIVE)
        chips = build_standings(snap(cars, me=1, profile=ir, sim=Sim.IRACING), self.OPTS).chips
        self.assertEqual([(c.label, c.value) for c in chips], [("LIC", "A 3.46"), ("iR", "2710")])
        self.assertIsNotNone(chips[1].delta)  # iRating projetado (estimativa) do piloto
        prac = build_standings(snap(cars, session_type="Practice", me=1, profile=ir, sim=Sim.IRACING),
                               self.OPTS).chips
        self.assertIsNone(prac[1].delta)
        none = build_standings(snap(cars, me=1, sim=Sim.LMU), self.OPTS).chips
        self.assertEqual([(c.label, c.value, c.available) for c in none], [("RANK", "n/d", False)])
        man = DriverProfile(driver_rank="Gold", safety_rank="Silver", source=ProfileSource.MANUAL)
        chips = build_standings(snap(cars, me=1, profile=man, sim=Sim.LMU), self.OPTS).chips
        self.assertEqual([(c.label, c.value) for c in chips], [("DRIVER*", "Gold"), ("SAFETY*", "Silver")])
        demo = build_standings(snap(cars, me=1, profile=man, sim=Sim.DEMO), self.OPTS).chips
        self.assertEqual(demo[0].label, "DRIVER")  # DEMO não marca como "manual"


class TestSelection(unittest.TestCase):
    def test_select_rows_cases(self):
        self.assertEqual(select_rows(list(range(5)), 2, 8), [0, 1, 2, 3, 4])
        self.assertEqual(select_rows(list(range(30)), 4, 10), list(range(10)))
        out = select_rows(list(range(40)), 20, 10, top=3)
        self.assertEqual((len(out), out[:3], out[3]), (10, [0, 1, 2], None))
        self.assertIn(20, out)
        self.assertEqual(select_rows(list(range(40)), 39, 10)[-1], 39)
        self.assertEqual(select_rows(list(range(40)), 39, 3), [37, 38, 39])  # orçamento minúsculo
        self.assertEqual(select_rows(list(range(40)), 5, 0), [])

    def _groups(self, player_class="GT3", player_pos=12):
        def mk(label, n, cls, offset=0):
            from kerbhud.core.standings import Group
            cars = [car(offset + i, offset + i, cls, class_position=i) for i in range(1, n + 1)]
            return cars, label, cls
        cars = []
        c1, *_ = mk("DP", 1, "DP", 100)
        c2, *_ = mk("GTE", 20, "GTE", 200)
        c3, *_ = mk("GT3", 15, "GT3", 300)
        cars = c1 + c2 + c3
        me_idx = [c.idx for c in c3][player_pos - 1]
        v = build_standings(snap(cars, me=me_idx), StandingsOptions())
        return v

    def test_reference_layout_headers_top3_and_player_window(self):
        v = self._groups()
        self.assertEqual([g.label for g in v.groups], ["DP", "GTE", "GT3"])
        lines = select_lines(v.groups, 18)
        self.assertEqual(len(lines), 18)
        headers = [ln for ln in lines if isinstance(ln, HeaderLine)]
        self.assertEqual([(h.label, h.count) for h in headers], [("DP", 1), ("GTE", 20), ("GT3", 15)])
        rows = [ln for ln in lines if ln is not None and not isinstance(ln, HeaderLine)]
        self.assertTrue(any(r.is_player for r in rows))
        gte_rows = [r for r in rows if r.class_label == "GTE"]
        self.assertEqual([r.pos_text for r in gte_rows], ["1", "2", "3"])  # outras classes: só o topo
        gt3_pos = [r.pos_text for r in rows if r.class_label == "GT3"]
        self.assertEqual(gt3_pos[:3], ["1", "2", "3"])
        self.assertIn("12", gt3_pos)
        self.assertIn(None, lines)  # corte entre o topo e a janela do piloto

    def test_spare_budget_is_given_to_other_classes(self):
        v = self._groups()
        lines = select_lines(v.groups, 60)  # espaço de sobra: todos os carros aparecem
        rows = [ln for ln in lines if ln is not None and not isinstance(ln, HeaderLine)]
        self.assertEqual(len(rows), 36)
        self.assertNotIn(None, lines)
        mid = select_lines(v.groups, 26)  # sobra um pouco: cresce além do topo-3 das outras classes
        gte = [ln for ln in mid if ln is not None and not isinstance(ln, HeaderLine) and ln.class_label == "GTE"]
        self.assertGreater(len(gte), 3)
        self.assertLessEqual(len(mid), 26)

    def test_tight_budget_shrinks_other_classes_first(self):
        lines = select_lines(self._groups().groups, 9)
        self.assertLessEqual(len(lines), 9)
        rows = [ln for ln in lines if ln is not None and not isinstance(ln, HeaderLine)]
        self.assertTrue(any(r.is_player for r in rows))

    def test_single_class_also_gets_a_header_and_no_player_splits_evenly(self):
        v = build_standings(snap([car(i, i) for i in range(1, 6)], me=2), StandingsOptions())
        lines = select_lines(v.groups, 10)
        headers = [ln for ln in lines if isinstance(ln, HeaderLine)]
        self.assertEqual([(h.label, h.count) for h in headers], [("GT3", 5)])  # cabeçalho com a quantidade
        self.assertIsInstance(lines[0], HeaderLine)
        self.assertEqual(len(lines), 6)  # 1 cabeçalho + 5 carros
        # o cabeçalho consome uma linha do orçamento
        many = build_standings(snap([car(i, i) for i in range(1, 31)], me=2), StandingsOptions())
        self.assertEqual(len(select_lines(many.groups, 10)), 10)
        # escopo "só minha classe" também mostra o cabeçalho
        cls = build_standings(snap([car(1, 1, "Hypercar"), car(2, 2, "GT3"), car(3, 3, "GT3")], me=2),
                              StandingsOptions(scope="class"))
        only = select_lines(cls.groups, 10)
        self.assertEqual([(ln.label, ln.count) for ln in only if isinstance(ln, HeaderLine)], [("GT3", 2)])
        multi = self._groups().groups
        for g in multi:
            for r in g.rows:
                r.is_player = False
        lines = select_lines(multi, 12)
        self.assertLessEqual(len(lines), 12)
        self.assertEqual(sum(isinstance(ln, HeaderLine) for ln in lines), 3)


class TestStandingsLayout(unittest.TestCase):
    def test_options_sanitized(self):
        o = get_standings_options({"scope": "xx", "rows": "abc", "columns": {"best": False, "tire": True, "zzz": True},
                                   "show_profile": False})
        self.assertEqual((o.scope, o.rows, o.show_profile), ("all", 18, False))
        self.assertNotIn("best", o.columns)
        self.assertIn("tire", o.columns)
        self.assertNotIn("zzz", o.columns)
        self.assertEqual(get_standings_options({"rows": 1}).rows, 6)
        self.assertEqual(get_standings_options({"rows": 99}).rows, 40)
        self.assertEqual(get_standings_options({}).columns, frozenset(
            {"flag", "license", "brand", "delta", "tire", "laps", "int", "gap", "best", "last", "nrg"}))
        self.assertEqual(get_standings_options({"rows": 0}).rows, 0)  # 0 = automático (preenche a janela)
        self.assertEqual(get_standings_options({"rows": -5}).rows, 0)

    def test_columns_never_overlap_and_grow_with_options(self):
        full = get_standings_options({})
        cols = column_layout(full)
        for a, b in zip(cols, cols[1:]):
            self.assertLessEqual(a.x + a.w, b.x + 1e-9)
        self.assertEqual([c.key for c in cols], ["pos", "num", "flag", "name", "license", "brand", "delta", "tire",
                                                "laps", "int", "gap", "best", "last", "nrg"])
        slim = get_standings_options({"columns": {k: False for k in ("flag", "license", "brand", "delta", "tire", "nrg", "laps")}})
        self.assertEqual([c.key for c in column_layout(slim)], ["pos", "num", "name", "int", "gap", "best", "last"])
        self.assertGreater(standings_design_size({})[0], standings_design_size({"columns": {"nrg": False}})[0])

    def test_responsive_columns_drop_least_important_first_and_never_shrink_text(self):
        opts = get_standings_options({})
        full = columns_width(column_layout(opts))
        self.assertEqual(full, standings_design_size({})[0])
        self.assertEqual([c.key for c in fit_columns(opts, full)], [c.key for c in column_layout(opts)])
        self.assertEqual([c.key for c in fit_columns(opts, 5000)], [c.key for c in column_layout(opts)])  # sobra
        # estreitando pouco a pouco: some uma coluna por vez, na ordem DROP_ORDER
        enabled = [k for k in DROP_ORDER if k in opts.columns]
        previous = {c.key for c in fit_columns(opts, full)}
        dropped = []
        for width in range(int(full), 300, -5):
            now = {c.key for c in fit_columns(opts, float(width))}
            self.assertTrue(now <= previous)  # nunca ganha coluna ao estreitar
            for gone in previous - now:
                dropped.append(gone)
            previous = now
            self.assertTrue({"pos", "num", "name"} <= now)  # as essenciais ficam sempre
        self.assertEqual(dropped, enabled[:len(dropped)])  # sempre a menos importante primeiro
        self.assertEqual(dropped[0], "nrg")
        self.assertEqual({c.key for c in fit_columns(opts, 10)}, {"pos", "num", "name"})
        for c in fit_columns(opts, 900):  # o que sobrou cabe na largura pedida
            self.assertLessEqual(c.x + c.w, 900)

    def test_design_width_never_grows_so_saved_windows_keep_every_column(self):
        """Janelas de layouts salvos são ajustadas à largura anterior (1124): o desenho não pode passar disso,
        senão a última coluna (NRG) sumiria sozinha para quem já tinha tudo visível."""
        self.assertLessEqual(standings_design_size({})[0], 1124.0)
        full = standings_design_size({})[0]
        self.assertEqual({c.key for c in fit_columns(get_standings_options({}), 1124.0)}, {
            "pos", "num", "flag", "name", "license", "brand", "delta", "tire", "laps", "int", "gap", "best", "last", "nrg"})
        self.assertLessEqual(full, 1124.0)

    def test_numeric_text_fills_most_of_each_column_without_overflowing(self):
        """Pedido do usuário: números maiores, sem ficar com muito espaço vago e sem colar. Modelo de largura de uma
        fonte tipo DIN/Bahnschrift (dígito ~0,5 em; ponto e dois-pontos ~0,25 em; sinal ~0,5 em; % ~0,8 em)."""
        def width(text, px):
            em = {".": 0.25, ":": 0.25, "+": 0.5, "%": 0.8, "L": 0.45}
            return sum(em.get(ch, 0.5) for ch in text) * px

        self.assertGreaterEqual(NUM_FONT_PX, 22.0)  # melhor/última: antes 19 (e 17): as colunas pareciam vazias
        self.assertGreaterEqual(NUM2_FONT_PX, 20.0)
        self.assertGreater(NUM_FONT_PX, NUM2_FONT_PX)
        for text, key, px, inner in (("1:42.089", "best", NUM_FONT_PX, 12), ("1:42.089", "last", NUM_FONT_PX, 8),
                                     ("+6.158", "int", NUM2_FONT_PX, 8), ("+12.3", "gap", NUM2_FONT_PX, 8),
                                     ("123", "laps", NUM2_FONT_PX, 8)):
            w = width(text, px)
            self.assertLessEqual(w, WIDTHS[key] - inner, f"{text} estoura {key}")  # cabe sem encolher
            if key in ("best", "last", "int"):
                self.assertGreaterEqual(w / WIDTHS[key], 0.70, f"{text} ficou pequeno em {key}")  # e preenche
            self.assertLessEqual(w / WIDTHS[key], 0.90, f"{text} ficou colado em {key}")  # sem encostar nas bordas
        # entre duas colunas vizinhas de números sobra um respiro de pelo menos 12 unidades
        self.assertGreaterEqual((WIDTHS["int"] - width("+6.158", NUM2_FONT_PX)) + 2, 12.0)
        self.assertLessEqual(width("99%", NUM2_FONT_PX), WIDTHS["nrg"] - NRG_TEXT_X - 4)  # NRG de 2 dígitos cabe
        self.assertLessEqual(width("100%", NUM2_FONT_PX), WIDTHS["nrg"] - NRG_TEXT_X - 4)  # e o de 3 também
        self.assertLessEqual(NAME_W - 4, 244)  # o nome não ganhou largura à custa dos números
        self.assertLessEqual(width("Matthew Richard Beaumont", ST_NAME_PX), NAME_W - 4)  # e ainda cabe inteiro

    def test_columns_hidden_by_the_user_stay_hidden_when_there_is_room(self):
        opts = get_standings_options({"columns": {"nrg": False, "tire": False}})
        keys = {c.key for c in fit_columns(opts, 5000)}
        self.assertNotIn("nrg", keys)
        self.assertNotIn("tire", keys)

    def test_responsive_rows(self):
        opts = get_standings_options({})
        self.assertEqual(fit_rows(opts, 9999), 18)  # teto = opção "rows"
        h_for = lambda n: TOP_H + n * ROW_H + FOOTER_H + PAD_BOTTOM  # noqa: E731
        self.assertEqual(fit_rows(opts, h_for(10)), 10)
        self.assertEqual(fit_rows(opts, h_for(10) - 1), 9)  # uma linha só entra inteira
        self.assertEqual(fit_rows(opts, 50), MIN_ROWS)  # nunca menos que o mínimo
        no_footer = get_standings_options({"show_profile": False})
        self.assertEqual(fit_rows(no_footer, h_for(10)), 11)  # sem rodapé, sobra espaço para mais uma
        auto = get_standings_options({"rows": 0})
        self.assertEqual(fit_rows(auto, 9999), MAX_AUTO_ROWS)  # automático: preenche a janela
        self.assertEqual(fit_rows(auto, h_for(25)), 25)
        fixed = get_standings_options({"rows": 12})
        self.assertEqual(fit_rows(fixed, 9999), 12)
        self.assertEqual(fit_rows(fixed, h_for(7)), 7)

    def test_design_size_rows_and_footer(self):
        w, h = standings_design_size({})
        self.assertEqual(h, TOP_H + 18 * ROW_H + FOOTER_H + 6.0)
        self.assertEqual(standings_design_size({"show_profile": False})[1], h - FOOTER_H)
        self.assertEqual(standings_design_size({"rows": 26})[1] - h, 8 * ROW_H)
        self.assertEqual((MODULES["standings"].design_w, MODULES["standings"].design_h), (round(w), round(h)))
        rel_h = rel_core.HEADER_H + 7 * rel_core.ROW_H + rel_core.FOOTER_H
        self.assertEqual(design_size("relative", {}), (rel_core.DESIGN_W, rel_h))
        self.assertEqual((MODULES["relative"].design_w, MODULES["relative"].design_h),
                         (round(rel_core.DESIGN_W), round(rel_h)))

    def test_text_is_legible_at_default_layouts(self):
        """Nos layouts padrão (1920x1080) o nome do piloto fica com tamanho real confortável."""
        for make in PRESETS:
            lay = make()
            for mid, name_px, floor in (("standings", ST_NAME_PX, 16.0), ("relative", rel_core.NAME_FONT_PX, 15.0)):
                st = lay.modules[mid]
                if not st.visible:
                    continue
                dw, dh = design_size(mid, st.options)
                fx, fy, fw, fh = st.rect
                scale = min(fw * 1920 / dw, fh * 1080 / dh)
                self.assertGreaterEqual(name_px * scale, floor, f"{lay.name}/{mid}: {name_px * scale:.1f}px")

    def test_presets_match_design_aspect_for_dynamic_modules(self):
        for make in PRESETS:
            lay = make()
            for mid in ("inputs", "standings", "relative", "status"):
                st = lay.modules[mid]
                dw, dh = design_size(mid, st.options)
                fx, fy, fw, fh = st.rect
                aspect = (fw * 1920) / (fh * 1080)
                self.assertAlmostEqual(aspect / (dw / dh), 1.0, delta=0.06, msg=f"{lay.name}/{mid}")


# --------------------------------------------------------------------------- #
LAP = 100.0


def rel_snap(me_pct=0.50, others=(), me_laps=5, track=5000.0, me_est=LAP, session_type="Race", **kw):
    cars = [car(0, 5, "GT3", lap_dist_pct=me_pct, laps_completed=me_laps, est_lap_time=me_est,
                driver_name="Eu", **kw)]
    for spec in others:
        spec = dict(spec)
        idx, pct = spec.pop("idx"), spec.pop("pct")
        spec.setdefault("laps", me_laps)
        spec.setdefault("est", LAP)
        cls = spec.pop("cls", "GT3")
        laps, est = spec.pop("laps"), spec.pop("est")
        cars.append(car(idx, idx, cls, lap_dist_pct=pct, laps_completed=laps, est_lap_time=est, **spec))
    return snap(cars, me=0, track=track, session_type=session_type)


class TestRelative(unittest.TestCase):
    def setUp(self):
        self.tr = RelativeTracker()
        self.opts = RelativeOptions()

    def test_wrap(self):
        self.assertAlmostEqual(wrap_delta(0.02), 0.02)
        self.assertAlmostEqual(wrap_delta(0.98), -0.02)
        self.assertAlmostEqual(wrap_delta(-0.98), 0.02)

    def test_ahead_behind_distance_and_time(self):
        s = rel_snap(others=[{"idx": 1, "pct": 0.52}, {"idx": 2, "pct": 0.47}])
        v = self.tr.update(s, self.opts, now=0.0)
        a, b = v.ahead[0], v.behind[0]
        self.assertEqual((a.car.idx, a.side), (1, "ahead"))
        self.assertAlmostEqual(a.distance_m, 100.0)
        self.assertAlmostEqual(a.gap_s, 2.0)
        self.assertEqual(a.gap_text, "-2.00")
        self.assertEqual((b.car.idx, b.side), (2, "behind"))
        self.assertAlmostEqual(b.gap_s, 3.0)
        self.assertEqual(b.gap_text, "+3.00")
        self.assertTrue(v.uses_time)

    def test_gap_text_large_and_distance_fallback_without_lap_times(self):
        s = rel_snap(me_est=None, others=[{"idx": 1, "pct": 0.52, "est": None}])
        e = self.tr.update(s, self.opts, now=0.0).ahead[0]
        self.assertIsNone(e.gap_s)
        self.assertEqual(e.gap_text, "-100 m")  # sem tempo de volta: só distância, nada inventado
        s2 = rel_snap(others=[{"idx": 1, "pct": 0.62}])
        self.assertEqual(self.tr.update(s2, self.opts, now=1.0).ahead[0].gap_text, "-12.0")
        s3 = rel_snap(me_est=None, others=[{"idx": 1, "pct": 0.52, "est": None}], track=None)
        self.assertEqual(RelativeTracker().update(s3, self.opts, now=0).ahead[0].gap_text, "—")

    def test_best_lap_used_when_no_estimate(self):
        s = rel_snap(me_est=None, others=[{"idx": 1, "pct": 0.52, "est": None}], best_lap=90.0)
        e = self.tr.update(s, self.opts, now=0.0).ahead[0]
        self.assertAlmostEqual(e.gap_s, 0.02 * 90.0)

    def test_ordering_and_limits(self):
        others = [{"idx": i, "pct": 0.50 + 0.01 * i} for i in range(1, 6)]
        others += [{"idx": 10 + i, "pct": 0.50 - 0.01 * i} for i in range(1, 6)]
        v = self.tr.update(rel_snap(others=others), RelativeOptions(ahead=3, behind=2), now=0.0)
        self.assertEqual([e.car.idx for e in v.ahead], [3, 2, 1])  # do mais distante ao mais próximo
        self.assertEqual([e.car.idx for e in v.behind], [11, 12])

    def test_wraparound_start_finish_line(self):
        v = self.tr.update(rel_snap(me_pct=0.99, others=[{"idx": 1, "pct": 0.01}]), self.opts, now=0)
        self.assertEqual((v.ahead[0].car.idx, round(v.ahead[0].delta_pct, 3)), (1, 0.02))
        v = RelativeTracker().update(rel_snap(me_pct=0.01, others=[{"idx": 1, "pct": 0.99}]), self.opts, now=0)
        self.assertEqual(v.behind[0].car.idx, 1)

    def test_off_track_cars_only_fill_free_slots_and_are_dimmed(self):
        s = rel_snap(others=[{"idx": 1, "pct": 0.51, "status": CarStatus.GARAGE},
                             {"idx": 2, "pct": 0.52, "status": CarStatus.OUT},
                             {"idx": 3, "pct": 0.53, "status": CarStatus.DISQUALIFIED},
                             {"idx": 4, "pct": 0.54, "status": CarStatus.PITS}])
        v = self.tr.update(s, self.opts, now=0)  # 3 vagas à frente: 1 carro na pista + 2 apagados
        self.assertEqual([(e.car.idx, e.present) for e in v.ahead], [(4, True), (2, False), (1, False)])
        self.assertTrue(v.ahead[0].in_pit)
        absent = v.ahead[1]
        self.assertEqual((absent.gap_text, absent.trend, absent.fight, absent.state), ("—", None, False, STATE_NEUTRAL))
        self.assertEqual(absent.box, STATE_NEUTRAL)
        # só um espaço à frente: ninguém apagado entra
        only = RelativeTracker().update(s, RelativeOptions(ahead=1), now=0)
        self.assertEqual([(e.car.idx, e.present) for e in only.ahead], [(4, True)])

    def test_on_track_cars_are_never_displaced_by_absent_ones(self):
        others = [{"idx": i, "pct": 0.50 + 0.01 * i} for i in range(1, 4)]  # 3 carros na pista à frente
        others += [{"idx": 10 + i, "pct": 0.50 + 0.005 * i, "status": CarStatus.OUT} for i in range(1, 4)]  # mais perto!
        v = self.tr.update(rel_snap(others=others), RelativeOptions(ahead=3, behind=0), now=0)
        self.assertTrue(all(e.present for e in v.ahead))  # os apagados, mesmo mais próximos, não tomam o lugar
        self.assertEqual(sorted(e.car.idx for e in v.ahead), [1, 2, 3])

    def test_departed_drivers_and_the_empty_list_at_the_end_of_a_session(self):
        # todos saíram da sessão: ninguém na pista, mas a lista não fica vazia (apagada, última posição conhecida)
        gone = [{"idx": 1, "pct": 0.52, "in_session": False, "status": CarStatus.OUT},
                {"idx": 2, "pct": 0.47, "in_session": False, "status": CarStatus.OUT}]
        v = self.tr.update(rel_snap(others=gone), self.opts, now=0)
        self.assertEqual([(e.car.idx, e.present) for e in v.ahead], [(1, False)])
        self.assertEqual([(e.car.idx, e.present) for e in v.behind], [(2, False)])
        self.assertEqual(v.message, "")  # não diz "sem outros carros": há carros, só que apagados
        # fantasma com status de corrida normal também conta como ausente (basta in_session=False)
        ghost_only = [{"idx": 1, "pct": 0.52, "in_session": False}]
        v = RelativeTracker().update(rel_snap(others=ghost_only), self.opts, now=0)
        self.assertFalse(v.ahead[0].present)

    def test_absent_cars_on_the_behind_side_are_ordered_closest_first(self):
        others = [{"idx": 1, "pct": 0.49, "status": CarStatus.OUT}, {"idx": 2, "pct": 0.45, "status": CarStatus.OUT},
                  {"idx": 3, "pct": 0.30, "status": CarStatus.OUT}]
        v = self.tr.update(rel_snap(others=others), RelativeOptions(ahead=0, behind=2), now=0)
        self.assertEqual([e.car.idx for e in v.behind], [1, 2])
        self.assertTrue(all(not e.present for e in v.behind))

    def test_lap_diff_and_box_color(self):
        s = rel_snap(others=[{"idx": 1, "pct": 0.52, "laps": 6}, {"idx": 2, "pct": 0.53, "laps": 5},
                             {"idx": 3, "pct": 0.54, "laps": 4}])
        v = self.tr.update(s, self.opts, now=0)
        e = {x.car.idx: x for x in v.ahead}
        self.assertEqual({k: x.lap_diff for k, x in e.items()}, {1: 1, 2: 0, 3: -1})
        self.assertEqual((e[1].box, e[3].box), ("lap_ahead", "lap_behind"))  # vermelho / azul, como no iRacing
        self.assertEqual(e[2].box, e[2].state)  # mesma volta: vale o estado da disputa

    def test_lap_diff_debounce_at_the_line(self):
        tr = RelativeTracker()
        diffs = []
        for k in range(6):  # contador de voltas "pisca" +1 por 2 quadros na linha de chegada
            laps = 6 if k in (2, 3) else 5
            v = tr.update(rel_snap(others=[{"idx": 1, "pct": 0.52, "laps": laps}]), self.opts, now=k * 0.1)
            diffs.append(v.ahead[0].lap_diff)
        self.assertEqual(diffs, [0] * 6)
        for k in range(4):  # mudança real e sustentada é aceita
            v = tr.update(rel_snap(others=[{"idx": 1, "pct": 0.52, "laps": 6}]), self.opts, now=1 + k * 0.1)
        self.assertEqual(v.ahead[0].lap_diff, 1)

    def run_gap_series(self, side, pcts, step=1.0):
        tr = RelativeTracker()
        v = None
        for k, pct in enumerate(pcts):
            v = tr.update(rel_snap(others=[{"idx": 1, "pct": pct}]), self.opts, now=k * step)
        return (v.ahead if side == "ahead" else v.behind)[0]

    def test_trend_and_colors_ahead(self):
        closing = self.run_gap_series("ahead", [0.53, 0.52, 0.51, 0.505])
        self.assertEqual((closing.trend, closing.state), ("closing", STATE_FAVORABLE))
        receding = self.run_gap_series("ahead", [0.51, 0.52, 0.53, 0.54])
        self.assertEqual((receding.trend, receding.state), ("receding", STATE_NEUTRAL))
        steady = self.run_gap_series("ahead", [0.52, 0.52, 0.52, 0.52])
        self.assertEqual((steady.trend, steady.state), ("steady", STATE_NEUTRAL))
        self.assertIsNone(self.run_gap_series("ahead", [0.52]).trend)  # sem histórico: não inventa tendência

    def test_trend_and_colors_behind(self):
        closing = self.run_gap_series("behind", [0.43, 0.45, 0.47, 0.485])
        self.assertEqual((closing.trend, closing.state), ("closing", STATE_DANGER))
        receding = self.run_gap_series("behind", [0.485, 0.47, 0.45, 0.43])
        self.assertEqual((receding.trend, receding.state), ("receding", STATE_FAVORABLE))

    def test_lapped_car_closing_from_behind_is_not_a_threat(self):
        tr = RelativeTracker()
        for k, pct in enumerate([0.43, 0.45, 0.47, 0.485]):
            v = tr.update(rel_snap(others=[{"idx": 1, "pct": pct, "laps": 4}]), self.opts, now=float(k))
        e = v.behind[0]
        self.assertEqual((e.lap_diff, e.trend, e.state), (-1, "closing", STATE_NEUTRAL))

    def test_overtake_resets_trend(self):
        tr = RelativeTracker()
        for k, pct in enumerate([0.53, 0.52, 0.51]):
            tr.update(rel_snap(others=[{"idx": 1, "pct": pct}]), self.opts, now=float(k))
        v = tr.update(rel_snap(others=[{"idx": 1, "pct": 0.49}]), self.opts, now=3.0)
        self.assertEqual(v.behind[0].car.idx, 1)
        self.assertIsNone(v.behind[0].trend)

    def test_direct_fight(self):
        near = self.tr.update(rel_snap(others=[{"idx": 1, "pct": 0.508}]), self.opts, now=0).ahead[0]
        self.assertTrue(near.fight)  # 0,8 s, mesma classe e mesma volta
        self.assertFalse(RelativeTracker().update(rel_snap(others=[{"idx": 1, "pct": 0.52}]),
                                                  self.opts, now=0).ahead[0].fight)  # 2 s
        self.assertTrue(RelativeTracker().update(rel_snap(others=[{"idx": 1, "pct": 0.52}]),
                                                 RelativeOptions(fight_s=2.5), now=0).ahead[0].fight)
        self.assertFalse(RelativeTracker().update(rel_snap(others=[{"idx": 1, "pct": 0.508, "cls": "LMP2"}]),
                                                  self.opts, now=0).ahead[0].fight)
        self.assertFalse(RelativeTracker().update(rel_snap(others=[{"idx": 1, "pct": 0.508, "laps": 4}]),
                                                  self.opts, now=0).ahead[0].fight)
        self.assertFalse(RelativeTracker().update(
            rel_snap(others=[{"idx": 1, "pct": 0.508, "status": CarStatus.PITS}]), self.opts, now=0).ahead[0].fight)

    def test_fight_by_distance_when_no_lap_time(self):
        s = rel_snap(me_est=None, others=[{"idx": 1, "pct": 0.504, "est": None}])  # 20 m
        self.assertTrue(self.tr.update(s, self.opts, now=0).ahead[0].fight)
        s = rel_snap(me_est=None, others=[{"idx": 1, "pct": 0.51, "est": None}])  # 50 m
        self.assertFalse(RelativeTracker().update(s, self.opts, now=0).ahead[0].fight)

    def faster_class_scenario(self, pcts):
        tr = RelativeTracker()
        for k, pct in enumerate(pcts):
            cars = [dict(idx=1, pct=pct, cls="LMP2", best_lap=95.0, est=95.0)]
            v = tr.update(rel_snap(others=cars, best_lap=110.0), self.opts, now=float(k))
        return v.behind[0]

    def test_faster_class_from_behind_is_alert(self):
        e = self.faster_class_scenario([0.46, 0.46, 0.46])
        self.assertTrue(e.faster_class)
        self.assertEqual(e.state, STATE_ALERT)
        e2 = self.faster_class_scenario([0.30, 0.31, 0.32, 0.33])  # ~16 s atrás (> 8 s) e fechando
        self.assertNotEqual(e2.state, STATE_ALERT)

    def test_slower_class_ahead_closing_is_alert(self):
        tr = RelativeTracker()
        for k, pct in enumerate([0.54, 0.53, 0.52, 0.515]):
            s = rel_snap(others=[dict(idx=1, pct=pct, cls="LMP3", best_lap=125.0, est=125.0)], best_lap=110.0)
            v = tr.update(s, self.opts, now=float(k))
        self.assertEqual(v.ahead[0].state, STATE_ALERT)

    def test_view_carries_session_bar_and_ir_deltas_only_in_race(self):
        others = [{"idx": 1, "pct": 0.52, "irating": 2600}, {"idx": 2, "pct": 0.47, "irating": 1800}]
        s = rel_snap(others=others, irating=2200, license_class="A", license_sr=3.4)
        s.session.incidents, s.session.incident_limit = 6, 25
        v = self.tr.update(s, self.opts, now=0)
        self.assertEqual((v.bar.name, v.bar.incidents_text), ("RACE", "6/25"))
        self.assertTrue(v.bar.sof_text)
        self.assertEqual(set(v.ir_deltas), {0, 1, 2})
        self.assertAlmostEqual(sum(v.ir_deltas.values()), 0, delta=3)
        p = rel_snap(others=others, irating=2200, session_type="Practice")
        self.assertEqual(RelativeTracker().update(p, self.opts, now=0).ir_deltas, {})

    def test_messages_when_empty(self):
        self.assertEqual(self.tr.update(Snapshot(connected=False), self.opts).message, "Aguardando dados")
        self.assertEqual(self.tr.update(rel_snap(others=[]), self.opts, now=0).message, "Sem outros carros na pista")
        s = rel_snap(others=[{"idx": 1, "pct": 0.5}])
        s.cars[0].lap_dist_pct = None
        v = self.tr.update(s, self.opts, now=0)
        self.assertEqual(v.message, "Sem posição na pista")
        self.assertEqual(v.bar.name, "RACE")  # o rodapé continua disponível

    def test_history_cleanup_for_cars_outside_window(self):
        tr = RelativeTracker()
        tr.update(rel_snap(others=[{"idx": 1, "pct": 0.52}, {"idx": 2, "pct": 0.60}]),
                  RelativeOptions(ahead=1, behind=0), now=0.0)
        self.assertEqual(set(tr._hist), {1})
        tr.update(rel_snap(others=[{"idx": 2, "pct": 0.51}]), RelativeOptions(ahead=1, behind=0), now=1.0)
        self.assertEqual(set(tr._hist), {2})

    def test_options_and_design_size(self):
        o = get_relative_options({"ahead": "x", "behind": 99, "fight_s": float("nan"), "show_irating": False})
        self.assertEqual((o.ahead, o.behind, o.fight_s, o.show_irating), (3, 6, 1.0, False))
        w, h = relative_design_size({})
        self.assertEqual((w, h), (rel_core.DESIGN_W,
                                  rel_core.HEADER_H + 7 * rel_core.ROW_H + rel_core.FOOTER_H))
        self.assertGreater(relative_design_size({"ahead": 5, "behind": 5})[1], h)


if __name__ == "__main__":
    unittest.main()
