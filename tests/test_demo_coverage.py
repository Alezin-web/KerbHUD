"""O DEMO precisa mostrar TODAS as novidades (regra do projeto). Cada item de DEMO_FEATURES é conferido aqui."""
import math
import time
import unittest

from kerbhud.core.classes import class_style
from kerbhud.core.digflag import FLAG_CODE, DigFlagTracker, led_pattern
from kerbhud.core.model import CarStatus
from kerbhud.core.radar import radar_view
from kerbhud.core.spotter import side_traffic
from kerbhud.core.tireview import tire_view
from kerbhud.core.standings import NrgTracker, StandingsOptions, build_standings
from kerbhud.providers.demo import DEMO_FEATURES, STAGES, TOUR, DemoProvider


def at(stage, t):
    d = DemoProvider(stage)
    d._t0 = time.monotonic() - t
    return d.poll()


CHECKS = {
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
