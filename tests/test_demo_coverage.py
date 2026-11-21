"""O DEMO precisa mostrar TODAS as novidades (regra do projeto). Cada item de DEMO_FEATURES é conferido aqui."""
import math
import time
import unittest

from kerbhud.core.classes import class_style
from kerbhud.core.digflag import FLAG_CODE, DigFlagTracker, led_pattern
from kerbhud.core.model import CarStatus
from kerbhud.core.module_options import specs_for
from kerbhud.core.radar import radar_view
from kerbhud.core.spotter import side_traffic
from kerbhud.core.tireview import tire_view
from kerbhud.core.standings import NrgTracker, StandingsOptions, build_standings, get_standings_options
from kerbhud.providers.demo import DEMO_FEATURES, STAGES, TOUR, DemoProvider


def at(stage, t):
    d = DemoProvider(stage)
    d._t0 = time.monotonic() - t
    return d.poll()


CHECKS = {
    "standings_visivel_em_treino_se_a_opcao_for_desligada": lambda: not build_standings(
        at("treino", 5), get_standings_options({"hide_until_timed": False})).hidden
    and len(build_standings(at("treino", 5), get_standings_options({"hide_until_timed": False})).rows) > 1,
    "standings_escondido_ate_1o_tempo": lambda: build_standings(at("treino", 5), StandingsOptions()).hidden
    and not build_standings(at("treino", 12), StandingsOptions()).hidden,
    "pilotos_saem_ficam_apagados": lambda: any(not c.in_session for c in _race_end()),
    "fim_de_corrida_todos_saem": lambda: all(not c.in_session for c in _race_end()),
    "varias_classes_e_cabecalhos": lambda: len({c.class_name for c in at("corrida", 5).cars}) >= 3,
    "uma_classe_so": lambda: len({c.class_name for c in at("monoclasse", 5).cars}) == 1,
    "poucos_pilotos": lambda: len(at("poucos", 5).cars) <= 4,
    "nrg_so_nas_categorias_que_tem": lambda: NrgTracker().visible(at("sem_nrg", 5))
    and at("sem_nrg", 5).player().energy_pct is None
    and any(c.energy_pct is not None for c in at("sem_nrg", 5).cars),
    "estilo_lmu_sem_ir_licenca_incidentes": lambda: all(c.irating is None for c in at("lmu", 5).cars)
    and at("lmu", 5).session.incidents is None,
    "etiquetas_curtas_de_categoria": lambda: {class_style(c.class_name).label for c in at("formulas", 5).cars}
    == {"F1600", "FVee", "MX-5"},
    "marcas_pequenas_adess_duqueine_ligier": lambda: {"adess", "duqueine"} <= {
        __import__("kerbhud.core.brands", fromlist=["x"]).brand_for(c.vehicle_raw).key
        for c in at("lmu", 5).cars if c.class_name == "LMP3"},
    "icones_de_rank_lmu": lambda: len({at("lmu", t).profile.contact_badge for t in range(0, 35, 5)}) >= 5
    and at("lmu", 5).profile.safety_rank == "S3"
    and len({at("lmu", t).profile.driver_rank for t in range(0, 35, 7)}) >= 4,
    "atalho_pula_para_a_proxima_etapa": lambda: _skip_changes_stage(),
    "piloto_dirigindo_ou_fora_do_carro": lambda: at("treino", 1).driving is False and at("corrida", 5).driving is True,
    "motor_e_configuracao_resilientes": lambda: _resilient_engine_and_settings(),
    "fabricante_pela_equipe_no_lmu": lambda: _lmu_team_brands(),
    "tempo_da_sessao_com_segundos": lambda: _session_time_has_seconds(),
    "escala_pelo_quadrado_vermelho": lambda: _corner_drag_scales_and_wheel_does_not(),
    "standings_linhas_topo_e_em_volta": lambda: _standings_top_and_around(),
    "standings_multiclasse_e_fonte": lambda: _standings_multiclass_and_font(),
    "standings_tamanho_do_cabecalho_e_dos_pilotos": lambda: _standings_sizes(),
    "posicao_ao_vivo_na_corrida": lambda: _live_order_matches_positions(),
    "mapa_por_posicao_estimada_iracing": lambda: _estimated_map_ok(),
    "mapa_grava_mesmo_com_box_na_reta": lambda: _map_with_pit_on_the_straight(),
    "piloto_na_garagem": lambda: at("treino", 1).in_garage is True and at("treino", 20).in_garage is False,
    "disputas_e_voltas_a_frente_atras": lambda: max(c.laps_behind_leader for c in at("corrida", 25).cars) > 0,
    "pits_e_abandono": lambda: {CarStatus.PITS, CarStatus.OUT} <= {c.status for c in at("corrida", 25).cars},
    "piloto_ieieu": lambda: all(at(k, 5).player() is not None and at(k, 5).player().driver_name == "ieieu"
                                for k in TOUR if k != "treino")
    and at("treino", 20).player().driver_name == "ieieu",
    "mapa_do_circuito": lambda: _map_done("corrida") and _map_done("lmu"),
    "combustivel_medido_e_abastecer": lambda: _fuel_view().fuel.per_lap and _fuel_view().fuel.add > 0,
    "reparo_iracing": lambda: at("box", 20).damage.repair_required_s > 0
    and at("box", 50).damage.repair_required_s == 0,
    "avarias_por_regiao": lambda: max(at("lmu", 20).damage.zones) == 2 and at("lmu", 20).damage.detached
    and max(at("lmu", 33).damage.zones) == 0,
    "contador_batidas_e_fora_de_pista_lmu": lambda: _incident_counts() == (2, 2),
    "selo_de_rank_no_lugar_da_bandeira": lambda: build_standings(at("lmu", 12), StandingsOptions()).player.badge
    in ("rookie", "good", "trusted", "warning", "probation", "creator", "driver", "staff")
    and build_standings(at("corrida", 5), StandingsOptions()).player.badge is None,
    "pneus_temperatura_pressao_desgaste": lambda: {c.temp_state for t in range(0, 35, 2)
                                                   for c in tire_view(at("lmu", t)).cells.values()} >= {"cold", "ok", "hot"}
    and tire_view(at("lmu", 26)).cells["rr"].flat
    and tire_view(at("lmu", 30)).cells["fl"].wear_pct < tire_view(at("lmu", 2)).cells["fl"].wear_pct,
    "bandeiras_digflag": lambda: _primary_flag("corrida", 14) == "yellow" and _primary_flag("corrida", 22) == "blue"
    and _primary_flag("corrida", 27) == "debris" and _primary_flag("corrida", 75) == "checkered"
    and _primary_flag("corrida", 10) is None,
    "spotter_iracing_carro_ao_lado": lambda: at("corrida", 5).side_traffic == (0, 0)
    and at("corrida", 15).side_traffic == (1, 0) and at("corrida", 17).side_traffic == (1, 1)
    and at("corrida", 17).pose is None,
    "spotter_lmu_por_geometria": lambda: side_traffic(at("lmu", 5)) == (0, 0) and side_traffic(at("lmu", 13)) == (1, 0)
    and side_traffic(at("lmu", 15)) == (1, 1),
    "radar_com_carros_ao_redor": lambda: any(abs(c.x) > 2.0 for c in radar_view(at("lmu", 15), 30.0).cars)
    and radar_view(at("lmu", 15)).lateral_real and not radar_view(at("corrida", 17)).lateral_real
    and len(radar_view(at("corrida", 5), 60.0).cars) >= 1,
    "radar_alerta_carro_vindo_de_tras": lambda: _behind_alert_levels("lmu") >= {0, 1, 2},
    "radar_meia_lua_lateral": lambda: _side_glow_sides("lmu") >= {"left", "right"},
    "radar_so_aparece_com_carro_perto": lambda: _radar_near_flags("lmu") == {True, False},
    "spotter_barras_com_posicao_do_carro": lambda: len({round(o, 1) for o in _spotter_offsets("lmu")}) >= 3,
    "pneus_tres_zonas_e_volta": lambda: len(set(tire_view(at("corrida", 20)).cells["fl"].temps)) == 3
    and tire_view(at("corrida", 20)).cells["fl"].low_wear is not None and tire_view(at("corrida", 20)).lap is not None,
    "spotter_animacao_carro_ao_lado": lambda: _spotter_active_sides("lmu") >= {0, 1},
    "trackmap_movimento_suave_lmu": lambda: _smoothing_helps("lmu"),
    "digflag_painel_de_leds": lambda: led_pattern(FLAG_CODE["caution"])[0] and _primary_flag("corrida", 34) == "caution",
    "bandeiras_e_pneus": lambda: all(c.country for c in at("corrida", 5).cars)
    and len({c.tire for c in at("corrida", 5).cars}) >= 3,
}


def _walk(stage, t0, t1, step):
    d = DemoProvider(stage)
    t = t0
    while t < t1:
        d._t0 = time.monotonic() - t
        yield d.poll()
        t += step


def _map_done(stage):
    from kerbhud.core.trackmap import TrackRecorder, map_cars
    rec = TrackRecorder(None)
    shape = None
    for snap in _walk(stage, 0, 35, 0.04):
        shape = rec.update(snap) or shape
    return shape is not None and len(map_cars(snap, shape)) >= 8


def _corner_drag_scales_and_wheel_does_not():
    """A escala muda arrastando o quadrado vermelho (modo de edição); a roda não faz mais isso."""
    from pathlib import Path
    import kerbhud
    src = (Path(kerbhud.__file__).parent / "ui" / "module_base.py").read_text(encoding="utf-8")
    return "_scale_by_drag" in src and "self.zoom(1.0 + 0.05 * steps)" not in src


def _standings_lines(options):
    from kerbhud.core.standings import StandingsRow, build_standings, get_standings_options, select_lines_by_counts
    opts = get_standings_options(options)
    view = build_standings(at("corrida", 12), opts)
    return [ln for ln in select_lines_by_counts(view.groups, 40, opts) if isinstance(ln, StandingsRow)]


def _standings_top_and_around():
    """Minha classe mostra o topo + a janela em volta de mim, e o que o usuário escolher vale."""
    me = at("corrida", 12).player()
    own = lambda opts: [r for r in _standings_lines(opts) if r.class_label and r.car.class_name == me.class_name]  # noqa: E731
    return any(r.is_player for r in own({})) and len(own({"top_rows": 1, "around_rows": 3})) < len(own({"top_rows": 5, "around_rows": 9}))


def _standings_sizes():
    """XS/S/M/L mudam a altura da barra do topo e a das linhas; "S" é o tamanho de sempre."""
    from kerbhud.core.standings import FOOTER_H, PAD_BOTTOM, ROW_H, TOP_H, get_standings_options, standings_design_size
    base = get_standings_options({})
    big = get_standings_options({"header_size": "L", "driver_size": "L"})
    small = get_standings_options({"header_size": "XS", "driver_size": "XS"})
    return (base.top_h == TOP_H and base.row_h == ROW_H and big.top_h > TOP_H > small.top_h and big.row_h > ROW_H > small.row_h
            and standings_design_size({"driver_size": "L"})[0] > standings_design_size({})[0])


def _standings_multiclass_and_font():
    """"Outras classes" 0 e 0 esconde as outras categorias; a fonte escolhida é guardada."""
    from kerbhud.core.standings import get_standings_options
    me = at("corrida", 12).player()
    both = {r.car.class_name for r in _standings_lines({})}
    mine = {r.car.class_name for r in _standings_lines({"other_top": 0, "other_around": 0})}
    return len(both) > 1 and mine == {me.class_name} and get_standings_options({"font": "Roboto"}).font == "Roboto"


def _session_time_has_seconds():
    """A barra da sessão mostra decorrido / total com segundos (00:10:00 / 02:00:00)."""
    import re
    from kerbhud.core.sessioninfo import build_session_bar
    t = build_session_bar(at("corrida", 5)).time_text
    return bool(re.fullmatch(r"\d\d:\d\d:\d\d / \d\d:\d\d:\d\d", t))


def _lmu_team_brands():
    """No LMU a fabricante vem da tabela equipe/número (o nome do carro só cita a equipe)."""
    from kerbhud.core.brands import brand_for_car, set_overrides
    set_overrides([])
    f = lambda v, c: getattr(brand_for_car(None, v, None, c, "lmu"), "key", None)
    return (f("Proton Competition 2025 #99:WEC 99_25_X", "Hypercar") == "porsche"
            and f("Proton Competition 2025 #11:WEC 11_25_X", "LMP2") == "oreca")


def _resilient_engine_and_settings():
    """O DEMO roda no mesmo motor: um erro numa leitura não o derruba, e um settings.json corrompido não impede de abrir."""
    import tempfile
    import time
    from pathlib import Path
    from kerbhud.core.engine import Engine, load_settings
    from kerbhud.providers.demo import DemoProvider
    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "settings.json"
        bad.write_text("{ isto não é json", encoding="utf-8")
        cfg = load_settings(bad)
        if cfg["simulator"] != "auto" or not (Path(d) / "settings.json.bad").exists():
            return False
    cfg["simulator"] = "demo"
    demo = DemoProvider()
    real_poll, state = demo.poll, {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] in (2, 3):
            raise RuntimeError("erro de leitura simulado")
        return real_poll()

    demo.poll = flaky
    eng = Engine(cfg, providers={"demo": demo, "iracing": DemoProvider(), "lmu": DemoProvider()})
    eng.start()
    t0 = time.time()
    while time.time() - t0 < 3 and state["n"] < 8:
        time.sleep(0.02)
    alive = eng._thread.is_alive()
    eng.stop()
    return alive and state["n"] >= 8 and eng.latest().is_demo


def _live_order_matches_positions():
    """A posição mostrada na corrida segue a ordem na pista (voltas + fração), como a "posição ao vivo" do iRacing."""
    from kerbhud.core.liveorder import LiveOrder
    for t in (6, 12, 18, 24, 30):
        s = at("corrida", t)
        live = LiveOrder().order(s.cars)
        shown = [c.idx for c in sorted((c for c in s.cars if c.position and c.idx in live), key=lambda c: c.position)]
        if len(live) < 5 or live != shown:
            return False
    return True


def _estimated_map_ok():
    """DEMO no estilo iRacing: só o piloto tem posição, e ela é estimada (origem deslocada + deriva); o mapa fecha mesmo assim."""
    import math
    from kerbhud.core.model import CAP_PLAYER_XY_ESTIMATED
    from kerbhud.core.trackmap import TrackRecorder
    first = at("corrida", 5)
    if CAP_PLAYER_XY_ESTIMATED not in first.capabilities or any(c.world_x is not None for c in first.cars if not c.is_player):
        return False
    rec, shape = TrackRecorder(None), None
    for s in _walk("corrida", 0, 35, 0.04):
        shape = rec.update(s) or shape
    if shape is None:
        return False
    (x0, y0), (x1, y1) = shape.xy_at(0.0), shape.xy_at(0.9975)
    return math.hypot(x1 - x0, y1 - y0) < 60.0


def _map_with_pit_on_the_straight():
    """Traçado volta pronto mesmo quando o box cobre a reta de largada (caso de pistas como Navarra)."""
    import dataclasses
    import math
    from kerbhud.core.model import CarState, CarStatus, Inputs, SessionState, Sim, Snapshot
    from kerbhud.core.trackmap import TrackRecorder
    rec, shape = TrackRecorder(None), None
    for i in range(0, 3001):
        pct = (i / 3000) % 1.0
        t = 2 * math.pi * pct
        pit = pct >= 0.94 or pct < 0.07
        me = CarState(idx=0, driver_name="me", is_player=True, lap_dist_pct=pct, world_x=500 * math.cos(t), world_z=500 * math.sin(t),
                      status=CarStatus.PITS if pit else CarStatus.RUNNING)
        s = Snapshot(sim=Sim.IRACING, connected=True, cars=[me], player_idx=0, inputs=Inputs(speed_ms=20.0 if pit else 60.0),
                     session=SessionState(active=True, track_name="Navarra", track_length_m=3900.0))
        shape = rec.update(s) or shape
    return shape is not None


def _fuel_view():
    from kerbhud.core.fuel import FuelTracker
    tr = FuelTracker()
    view = None
    for snap in _walk("box", 0, 28, 0.1):
        view = tr.update(snap)
    return view


def _spotter_active_sides(stage):
    """Lados do spotter que acendem (e portanto animam) durante a etapa: 0 = esquerda, 1 = direita."""
    from kerbhud.core.spotter import SpotterTracker
    tr = SpotterTracker()
    out = set()
    for snap in _walk(stage, 0, 35, 0.2):
        out |= {i for i, n in enumerate(tr.update(snap) or (0, 0)) if n}
    return out


def _spotter_offsets(stage):
    """Posições (m) em que o carro ao lado aparece na barra do spotter durante a etapa."""
    from kerbhud.core.spotter import SpotterTracker
    tr = SpotterTracker()
    out = []
    for snap in _walk(stage, 0, 35, 0.2):
        tr.update(snap)
        out += [o for o in tr.offsets if o is not None]
    return out


def _radar_near_flags(stage):
    """Durante a etapa há momentos COM carro perto (radar aparece) e SEM (radar some)."""
    from kerbhud.core.radar import SHOW_M_CORE
    return {any(rc.distance <= SHOW_M_CORE for rc in radar_view(s, 30.0).cars) for s in _walk(stage, 0, 35, 0.5)}


def _smoothing_helps(stage):
    """No estilo LMU (posição a ~8 Hz) a posição suavizada de algum carro tem passos menores que a posição crua."""
    from kerbhud.core.smooth import PointSmoother
    clock = [0.0]
    sm = PointSmoother(clock=lambda: clock[0])
    raw_max, sm_max, last_raw, last_sm = {}, {}, {}, {}
    for i, snap in enumerate(_walk(stage, 3, 8, 0.016)):
        clock[0] = i * 0.016
        raw = {c.idx: (c.world_x, c.world_z) for c in snap.cars if not c.is_player and c.world_x is not None}
        sm.update(raw)
        pos = sm.frame()
        for k, r in raw.items():
            if k in last_raw and i > 60:  # (o começo é aquecimento: a velocidade ainda não foi estimada)
                raw_max[k] = max(raw_max.get(k, 0.0), math.hypot(r[0] - last_raw[k][0], r[1] - last_raw[k][1]))
                sm_max[k] = max(sm_max.get(k, 0.0), math.hypot(pos[k][0] - last_sm[k][0], pos[k][1] - last_sm[k][1]))
            last_raw[k], last_sm[k] = r, pos[k]
    return any(sm_max[k] < raw_max[k] * 0.6 for k in raw_max if raw_max[k] > 1.0)


def _side_glow_sides(stage):
    """Lados em que a meia-lua lateral do radar acende durante a etapa."""
    from kerbhud.core.radar import side_levels
    sides = set()
    for snap in _walk(stage, 0, 35, 0.25):
        sides |= {k for k, v in side_levels(radar_view(snap, 30.0).cars).items() if v}
    return sides


def _behind_alert_levels(stage):
    """Níveis (0 sem alerta, 1 amarelo, 2 vermelho) da linha de alerta do carro que chega por trás."""
    from kerbhud.core.radar import RadarSmoother, approaching_from_behind, proximity
    clock = [0.0]
    sm = RadarSmoother(clock=lambda: clock[0])
    levels = set()
    for i, snap in enumerate(_walk(stage, 20, 30, 0.05)):
        clock[0] = i * 0.05
        sm.update(radar_view(snap, 60.0))
        for rc in sm.frame().cars:
            if rc.y < -1.0 and abs(rc.x) < 4.5:
                levels.add(proximity(rc) if approaching_from_behind(rc) else 0)
    return levels


def _primary_flag(stage, t):
    return DigFlagTracker().update(at(stage, t)).primary


def _incident_counts():
    from kerbhud.core.incidents import IncidentCounter
    c = IncidentCounter()
    for snap in _walk("lmu", 0, 35, 0.05):
        c.update(snap)
    return c.hits, c.offs


def _skip_changes_stage():
    """Ctrl+Alt+N (e o item do menu) chamam next_stage(): o roteiro tem de ir para a etapa seguinte."""
    d = DemoProvider("tour")
    first = d._where(d._now())[0]
    d.next_stage()
    second = d._where(d._now())[0]
    return first == TOUR[0] and second == TOUR[1]


def _race_end():
    from kerbhud.core.roster import Roster
    r = Roster()
    s = None
    for t in (10, 40, 55, 70, 75, 79):
        s = r.update(at("corrida", t))
    return s.cars


class TestDemoCoversEveryFeature(unittest.TestCase):
    def test_every_declared_feature_has_a_check_and_a_real_stage(self):
        self.assertEqual(set(DEMO_FEATURES), set(CHECKS), "recurso novo? acrescente a verificação em CHECKS")
        for feat, stage in DEMO_FEATURES.items():
            self.assertIn(stage, STAGES, feat)
            self.assertIn(stage, TOUR, f"{feat}: etapa fora do roteiro completo")

    def test_every_feature_is_visible_in_the_demo(self):
        for feat, check in CHECKS.items():
            with self.subTest(feat):
                self.assertTrue(check(), feat)


if __name__ == "__main__":
    unittest.main()
