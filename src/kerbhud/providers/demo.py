"""Provider DEMO.

DADOS 100% SINTÉTICOS, apenas para testar a interface sem simulador.
Todo Snapshot deste provider vem com `is_demo=True`, `sim=Sim.DEMO` e o aviso
"DEMO" em `warnings`; a interface deve exibir um selo permanente.

O DEMO é um ROTEIRO de etapas que exercita as funções do overlay (ver `STAGES`):

* treino / qualificação: o Standings fica escondido até alguém fazer tempo (aí aparece com fade-in); pilotos
  entram e saem (os que saem ficam apagados, "OUT");
* corrida multiclasse: todos listados, disputas diretas no Relative, carros uma volta à frente/atrás, pits,
  abandono, NRG, logos, bandeiras, pneus, incidentes, SOF/iRating/licença;
* o fim da corrida: pilotos saem um a um e, por fim, todos (a lista continua, apagada);
* corrida de uma classe só, corrida com poucos pilotos, carro SEM NRG (NRG só nas linhas das categorias que têm) e estilo Le Mans Ultimate
  (sem iRating, licença, incidentes nem bandeiras).

* combustível (consumo medido, quanto abastecer), avarias (por região e tempo de reparo), parada nos boxes do
  piloto e traçado do circuito gravado numa volta; o piloto do DEMO se chama sempre "ieieu";

* categorias de nome comprido com etiqueta curta (F1600, FVee, MX-5), LMP3 de marcas pequenas (Adess, Duqueine),
  ícones de rank do LMU (Safety Rank trocando entre Rookie...Staff) e piloto começando na garagem.

REGRA DO PROJETO: toda novidade de interface/dados deve ser acrescentada aqui (uma etapa nova ou um detalhe nas
existentes) e registrada em `DEMO_FEATURES`; `tests/test_demo_coverage.py` confere que cada item continua visível.

O cenário padrão (`tour`) percorre tudo em ciclo; os demais rodam uma etapa só, em repetição.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from typing import Optional

from ..core.model import (
    CAP_BEST_LAST_LAP, CAP_CAR_MODEL, CAP_CAR_NUMBER, CAP_CLASS, CAP_ENERGY, CAP_GAPS, CAP_INCIDENTS,
    CAP_CONTACT, CAP_DAMAGE, CAP_FLAGS, CAP_FUEL, CAP_POSE, CAP_SIDE_TRAFFIC, CAP_TIRE_DETAIL, CAP_INPUTS,
    CAP_PROFILE_IRATING, CAP_PROFILE_LICENSE, CAP_SHIFT_LIGHTS_DERIVED, CAP_STANDINGS,
    CAP_PLAYER_XY_ESTIMATED, CAP_STEERING_ANGLE, CAP_TIRE, CAP_TRACKMAP_PCT, CAP_TRACKMAP_XY, CarState, CarStatus,
    CarDamage, ContactState, PlayerPose, TIRE_CORNERS, TireSet, TireWheel, DriverProfile, FuelState, Inputs, ProfileSource, SessionState, Sim, Snapshot,
)
from .base import Provider

TRACK_LEN = 5200.0
PLAYER_NAME = "ieieu"  # o piloto do DEMO (você) se chama sempre assim, em todas as etapas
LANE_M = 3.2  # distância lateral de um carro "ao lado" (m)
FUEL_CAPACITY_L = 80.0
FUEL_BURN_L = 3.4  # litros por volta (sintético)
RACE_HEAD_START_S = 600.0  # a corrida "já começou há 10 minutos" (há voltas e diferenças de volta)

# classe -> (nome, cor, tempo de volta base em s)
_CLASSES = {
    "hyper": ("Hypercar", "#e10600", 98.0),
    "lmp2": ("LMP2", "#2f6bff", 104.0),
    "lmp3": ("LMP3", "#a855f7", 109.0),
    "gt3": ("GT3", "#14c05a", 111.0),
    "ff": ("Formula Ford 1600", "#f59e0b", 125.0),
    "fvee": ("Formula Vee", "#22d3ee", 130.0),
    "mx5": ("Global Mazda MX-5 Cup", "#f472b6", 127.0),
}
_DR_CYCLE = ["B2", "S3", "G1", "P2"]  # troca a cada 7 s: mostra as cores dos níveis (bronze, prata, ouro, platina)
_SAFETY_BADGES = ["Rookie", "Good", "Trusted", "Warning", "Probation", "Creator", "Driver", "Staff"]
_TIRES = ["S", "M", "H", "M", "S", "H", "W", "I"]
_LICENSES = [("A", 3.21), ("B", 2.84), ("C", 4.12), ("B", 3.67), ("A", 4.01), ("D", 2.15), ("A", 1.98), ("R", 2.50)]


@dataclass(frozen=True)
class Entry:
    """Um carro/piloto do catálogo sintético."""
    key: str
    cls: str
    number: str
    driver: str
    country: str
    model: str
    ir: int


def _e(key, cls, number, driver, country, model, ir) -> Entry:
    return Entry(key, cls, number, driver, country, model, ir)


CATALOG: dict[str, Entry] = {e.key: e for e in [
    # Hypercar
    _e("h1", "hyper", "7", "Mateus Oliveira", "br", "Toyota GR010 Hybrid", 4210),
    _e("h2", "hyper", "50", "Luca Bianchi", "it", "Ferrari 499P", 5120),
    _e("h3", "hyper", "6", "Jonas Becker", "de", "Porsche 963 GTP", 3890),
    _e("h4", "hyper", "2", "Ethan Walker", "us", "Cadillac V-Series.R", 2750),
    _e("h5", "hyper", "94", "Hugo Laurent", "fr", "Peugeot 9X8", 3310),
    _e("h6", "hyper", "15", "Oliver Smith", "gb-eng", "BMW M Hybrid V8", 4480),
    # LMP2
    _e("p1", "lmp2", "22", "Diego Fernández", "es", "Oreca 07", 2210),
    _e("p2", "lmp2", "28", "Tiago Ferreira", "pt", "Oreca 07", 1980),
    _e("p3", "lmp2", "35", "Kenji Tanaka", "jp", "Oreca 07", 2640),
    _e("me_p", "lmp2", "88", "Alex Costa", "br", "Oreca 07", 2500),
    # LMP3
    _e("l1", "lmp3", "11", "Nicolas Dupont", "fr", "Ligier JS P320", 1640),
    _e("l2", "lmp3", "17", "Max van Dijk", "nl", "Ligier JS P320", 1720),
    # GT3
    _e("g1", "gt3", "51", "Marco Rossi", "it", "Ferrari 296 GT3", 3120),
    _e("g2", "gt3", "31", "Felix Wagner", "de", "BMW M4 GT3", 2480),
    _e("g3", "gt3", "59", "Harry Johnson", "gb", "McLaren 720S GT3", 2890),
    _e("g4", "gt3", "33", "Jake Miller", "us", "Corvette Z06 GT3.R", 1870),
    _e("g5", "gt3", "27", "Sam Taylor", "au", "Aston Martin Vantage GT3", 2310),
    _e("g6", "gt3", "78", "Yuki Sato", "jp", "Lexus RC F GT3", 2050),
    _e("g7", "gt3", "63", "Lucas Pereira", "br", "Lamborghini Huracán GT3", 2670),
    _e("g8", "gt3", "4", "Rafael Almeida", "br", "Audi R8 LMS GT3", 3010),
    # LMP3 (marcas pequenas) e categorias de nome comprido (etiquetas curtas: F1600, FVee, MX-5)
    _e("l3", "lmp3", "4", "Sofia Lindqvist", "se", "Adess AD25", 1500),
    _e("l4", "lmp3", "13", "Pierre Martin", "fr", "Duqueine D09", 1610),
    *[_e(f"v{i}", "fvee", str(30 + i), n, c, "Formula Vee", ir) for i, (n, c, ir) in enumerate([
        ("Otto Becker", "de", 1300), ("Rui Santos", "pt", 1450), ("Tom Evans", "gb", 1220),
        ("Lena Novak", "cz", 1380)], start=1)],
    *[_e(f"m{i}", "mx5", str(50 + i), n, c, "Mazda MX-5 Cup", ir) for i, (n, c, ir) in enumerate([
        ("Ken Ito", "jp", 2400), ("Carla Dias", "br", 2250), ("Ryan Cole", "us", 2600)], start=1)],
    _e("me", "gt3", "77", "Alex Costa", "br", "Mercedes-AMG GT3", 2500),
    # Formula Ford 1600 (uma classe só)
    *[_e(f"f{i}", "ff", str(10 + i * 3), n, c, "Ray FF1600", ir) for i, (n, c, ir) in enumerate([
        ("Bruno Carvalho", "br", 1850), ("Liam O'Connor", "ie", 2100), ("Pedro Gomes", "pt", 1420),
        ("Emma Clarke", "gb-eng", 2380), ("Mateo Ruiz", "ar", 1190), ("Noah Fischer", "de", 1760),
        ("Alex Costa", "br", 2500), ("Hana Sato", "jp", 1530)], start=1)],
]}


@dataclass
class Stage:
    key: str
    label: str
    session_type: str
    track: str
    duration: float
    cars: list[str]  # ordem = ordem na pista dentro da classe (o primeiro de cada classe lidera a classe)
    player: str
    timed: bool = False  # treino/qualy: posição só depois de fazer tempo
    gap_s: float = 1.6  # intervalo médio (s) entre carros da mesma classe
    first_lap: dict[str, float] = field(default_factory=dict)  # (timed) quando cada carro faz o 1º tempo
    join: dict[str, float] = field(default_factory=dict)  # entra na sessão neste instante
    leave: dict[str, float] = field(default_factory=dict)  # sai da sessão neste instante
    pits: dict[str, tuple[float, float]] = field(default_factory=dict)  # (início, fim) nos boxes
    retire: dict[str, float] = field(default_factory=dict)  # abandona (OUT, continua na lista)
    fight_behind: float = 0.0  # >0: o carro logo atrás do piloto fica a esta distância (s)
    fight_ahead: float = 0.0  # >0: idem à frente
    ends_at: Optional[float] = None  # a partir daqui todos saem e a sessão deixa de ser publicada
    energy: bool = True  # carros de Hypercar/GT3 têm NRG
    lmu_style: bool = False  # sem iRating, licença, incidentes e bandeiras
    total_s: float = 7200.0
    incidents: int = 6
    time_scale: float = 5.0  # o relógio da corrida anda mais rápido que o do roteiro: dá várias voltas por etapa
    fuel_start: float = 40.0  # litros no tanque no início da etapa
    approach_events: tuple = ()  # (carro, início, fim): vem de trás até colar no piloto e volta a recuar
    side_events: tuple = ()  # (carro, início, fim, "left"|"right"): o carro emparelha ao lado do piloto
    damage: str = ""  # "" | "zones" (amassados por região, estilo LMU) | "repair" (tempo de reparo, estilo iRacing)


_MULTI = ["h1", "h2", "h3", "h4", "h5", "h6", "p1", "p2", "p3", "l1", "l2",
          "g1", "g2", "g3", "me", "g4", "g5", "g6", "g7", "g8"]

STAGES: dict[str, Stage] = {s.key: s for s in [
    Stage("treino", "Treino: Standings escondido até o 1º tempo; pilotos entram e saem", "Practice",
          "DEMO Circuit - Treino", 50.0,
          ["h1", "h2", "h3", "h4", "p1", "p2", "p3", "g1", "g2", "me", "g4", "g5"], "me", timed=True, gap_s=4.0,
          first_lap={"h2": 7, "h1": 9, "g1": 12, "me": 14, "p1": 16, "h3": 18, "g2": 21, "p2": 23, "h4": 26,
                     "g4": 29, "p3": 33, "g5": 37},
          join={"g5": 22.0, "p3": 20.0}, leave={"h4": 40.0, "g4": 44.0}, total_s=3600.0, incidents=0),
    Stage("quali", "Qualificação: Standings reaparece com fade-in a cada nova sessão", "Qualify",
          "DEMO Circuit - Quali", 40.0,
          ["h1", "h2", "h3", "h4", "h5", "p1", "p2", "p3", "g1", "g2", "me", "g4", "g5", "g6"], "me", timed=True,
          gap_s=3.0,
          first_lap={"h1": 6, "h5": 8, "g1": 10, "h2": 12, "me": 15, "p1": 17, "g2": 19, "h3": 21, "p2": 24,
                     "g4": 27, "g5": 29, "g6": 32, "h4": 34, "p3": 36},
          leave={"p3": 38.0}, total_s=1200.0, incidents=2),
    Stage("corrida", "Corrida multiclasse: disputas, pits, abandono, NRG, logos, bandeiras; no fim todos saem",
          "Race", "DEMO Circuit - Corrida", 80.0, _MULTI, "me", gap_s=1.8,
          pits={"g3": (15.0, 30.0), "p2": (40.0, 52.0)}, retire={"g6": 20.0},
          leave={"l2": 38.0, "g8": 42.0, "h5": 46.0, "g5": 50.0, "h2": 54.0, "p1": 56.0, "g2": 58.0, "h6": 60.0,
                 "g1": 61.0, "p3": 62.0, "h3": 63.0, "g4": 64.0, "h1": 65.0, "me": 66.0, "g7": 67.0, "g3": 68.0,
                 "h4": 69.0, "l1": 70.0, "p2": 71.0},
          ends_at=72.0, fight_behind=0.7, fight_ahead=0.8, incidents=6,
          side_events=(("g4", 14.0, 20.0, "left"), ("g2", 16.0, 19.0, "right"), ("g4", 26.0, 30.0, "right")),
          approach_events=(("g5", 32.0, 40.0),)),
    Stage("monoclasse", "Corrida de UMA classe só: cabeçalho com a quantidade de pilotos", "Race",
          "DEMO Circuit - Monoclasse", 40.0, [f"f{i}" for i in range(1, 9)], "f7", gap_s=1.2,
          energy=False, fight_behind=0.6, fight_ahead=0.9, total_s=1800.0, incidents=3),
    Stage("poucos", "Corrida com poucos pilotos: o painel se ajusta ao tamanho da lista", "Race",
          "DEMO Circuit - Poucos", 30.0, ["h1", "g1", "me", "g2"], "me", gap_s=3.0, fight_behind=0.9,
          total_s=1800.0, incidents=1),
    Stage("sem_nrg", "Seu carro SEM NRG (LMP2): a coluna NRG continua (há categorias com NRG), mas só nas linhas delas", "Race",
          "DEMO Circuit - Sem NRG", 35.0,
          ["h1", "h2", "h3", "p1", "p2", "me_p", "p3", "g1", "g2", "g3", "g4"], "me_p", gap_s=2.0,
          fight_behind=0.8, incidents=4),
    Stage("formulas", "Categorias de nome comprido: etiquetas curtas (F1600, FVee, MX-5)", "Race",
          "DEMO Circuit - Formulas", 35.0,
          ["f1", "f2", "f3", "f4", "v1", "v2", "v3", "v4", "m1", "m2", "m3"], "f2", gap_s=1.5,
          energy=False, fight_behind=0.7, fight_ahead=0.9, total_s=1800.0, incidents=2),
    Stage("box", "Combustível e avarias: consumo medido, quanto abastecer, parada com reparo e traçado do circuito",
          "Race", "DEMO Circuit - Box", 60.0,
          ["h1", "h2", "h3", "p1", "p2", "me", "g1", "g2", "g3"], "me", gap_s=2.4,
          pits={"me": (30.0, 38.0)}, total_s=1800.0, incidents=2, fuel_start=34.0, damage="repair",
          side_events=(("g3", 14.0, 20.0, "left"),), approach_events=(("g3", 24.0, 30.0),),
          time_scale=12.0),
    Stage("lmu", "Estilo Le Mans Ultimate: sem iRating, licença, incidentes nem bandeiras", "Race",
          "DEMO Circuit - Estilo LMU", 35.0,
          ["h1", "h2", "h3", "h4", "h5", "p1", "p2", "l3", "l4", "g1", "g2", "me", "g4", "g5", "g6"], "me", gap_s=2.2,
          lmu_style=True, fight_behind=0.8, pits={"g2": (12.0, 24.0)}, damage="zones",
          side_events=(("g4", 12.0, 18.0, "left"), ("g1", 14.0, 17.0, "right")),
          approach_events=(("g4", 21.0, 29.0),)),
]}

#: Novidades que o DEMO precisa exibir: recurso -> etapa onde aparece. Ao criar um recurso novo, acrescente aqui.
DEMO_FEATURES: dict[str, str] = {
    "standings_escondido_ate_1o_tempo": "treino",
    "pilotos_saem_ficam_apagados": "corrida",
    "fim_de_corrida_todos_saem": "corrida",
    "varias_classes_e_cabecalhos": "corrida",
    "uma_classe_so": "monoclasse",
    "poucos_pilotos": "poucos",
    "nrg_so_nas_categorias_que_tem": "sem_nrg",
    "estilo_lmu_sem_ir_licenca_incidentes": "lmu",
    "etiquetas_curtas_de_categoria": "formulas",
    "marcas_pequenas_adess_duqueine_ligier": "lmu",
    "icones_de_rank_lmu": "lmu",
    "piloto_na_garagem": "treino",
    "piloto_dirigindo_ou_fora_do_carro": "treino",
    "mapa_grava_mesmo_com_box_na_reta": "box",
    "mapa_por_posicao_estimada_iracing": "corrida",
    "atalho_pula_para_a_proxima_etapa": "treino",
    "disputas_e_voltas_a_frente_atras": "corrida",
    "pits_e_abandono": "corrida",
    "bandeiras_e_pneus": "corrida",
    "piloto_ieieu": "treino",
    "mapa_do_circuito": "corrida",
    "combustivel_medido_e_abastecer": "box",
    "reparo_iracing": "box",
    "avarias_por_regiao": "lmu",
    "pneus_temperatura_pressao_desgaste": "lmu",
    "bandeiras_digflag": "corrida",
    "spotter_iracing_carro_ao_lado": "corrida",
    "spotter_lmu_por_geometria": "lmu",
    "radar_com_carros_ao_redor": "lmu",
    "radar_alerta_carro_vindo_de_tras": "lmu",
    "radar_meia_lua_lateral": "lmu",
    "radar_so_aparece_com_carro_perto": "lmu",
    "pneus_tres_zonas_e_volta": "corrida",
    "spotter_animacao_carro_ao_lado": "lmu",
    "spotter_barras_com_posicao_do_carro": "lmu",
    "trackmap_movimento_suave_lmu": "lmu",
    "digflag_painel_de_leds": "corrida",
    "contador_batidas_e_fora_de_pista_lmu": "lmu",
    "selo_de_rank_no_lugar_da_bandeira": "lmu",
}

#: ordem do cenário padrão e o que cada nome de cenário significa
TOUR = ["treino", "quali", "corrida", "box", "monoclasse", "formulas", "poucos", "sem_nrg", "lmu"]
SCENARIOS: dict[str, str] = {"tour": "Roteiro completo (todas as etapas, em ciclo)",
                             **{k: s.label for k, s in STAGES.items()}}


def _estimated_xy(x: float, z: float, distance_m: float) -> tuple[float, float]:
    """Como o iRacing de verdade: a posição do piloto é ESTIMADA (velocidade x rumo), começa numa origem qualquer e
    acumula deriva. O DEMO imita isso (origem deslocada + deriva de 0,4%) para exercitar o mesmo caminho do traçado."""
    return x + 1234.5 + 0.004 * distance_m, z - 987.6 - 0.003 * distance_m


def _track_xy(pct: float) -> tuple[float, float]:
    t = 2 * math.pi * pct
    return 900 * math.cos(t) + 220 * math.cos(3 * t), 520 * math.sin(t) + 140 * math.sin(2 * t)


#: bandeiras do DEMO: (início, fim, bandeira) em segundos da etapa. Ao fim da sessão aparece a de chegada.
LMU_UPDATE_S = 0.125  # intervalo entre atualizações de posição no estilo LMU
CHECKERED_TAIL_S = 5.0  # a chegada aparece nos últimos segundos de cada etapa
FLAG_SCRIPT = ((0.0, 6.0, "green"), (12.0, 18.0, "yellow"), (20.0, 24.0, "blue"), (26.0, 30.0, "debris"),
               (32.0, 36.0, "caution"), (38.0, 41.0, "red"), (43.0, 46.0, "white"))


def _dir(pct: float) -> tuple[float, float]:
    """Vetor unitário da frente do carro no ponto `pct` da pista (plano X/Z)."""
    x0, z0 = _track_xy(pct)
    x1, z1 = _track_xy(pct + 0.002)
    n = math.hypot(x1 - x0, z1 - z0) or 1.0
    return (x1 - x0) / n, (z1 - z0) / n


def _left(fwd: tuple[float, float]) -> tuple[float, float]:
    return -fwd[1], fwd[0]  # mundo com +z à frente e +x à direita: a esquerda de (0,1) é (-1,0)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


class DemoProvider(Provider):
    sim = Sim.DEMO

    def __init__(self, scenario: str = "tour") -> None:
        self._t0 = time.monotonic()
        self._skip = 0.0  # tempo "pulado" ao avançar de etapa
        self.scenario = scenario if scenario in SCENARIOS else "tour"
        self._player_idx = 0
        self._layout_cache: dict[str, dict] = {}

    # ---- controle ------------------------------------------------------- #
    def set_scenario(self, name: str) -> None:
        if name not in SCENARIOS:
            raise ValueError(name)
        self.scenario = name
        self._t0 = time.monotonic()
        self._skip = 0.0

    def next_stage(self) -> None:
        """Pula para o início da próxima etapa (no roteiro completo) ou reinicia a etapa atual."""
        key, local, _ = self._where(self._now())
        self._skip += STAGES[key].duration - local + 0.01

    def connect(self) -> bool:
        self._t0 = time.monotonic()
        self._skip = 0.0
        return True

    def hint(self) -> str:
        return "Modo DEMO: dados sintéticos."

    # ---- roteiro -------------------------------------------------------- #
    def _now(self) -> float:
        return (time.monotonic() - self._t0) + self._skip

    def _where(self, t: float) -> tuple[str, float, int]:
        """(etapa, tempo dentro da etapa, nº da etapa no ciclo) para o tempo `t` do roteiro."""
        order = TOUR if self.scenario == "tour" else [self.scenario]
        cycle = sum(STAGES[k].duration for k in order)
        t_in = t % cycle
        for n, k in enumerate(order):
            d = STAGES[k].duration
            if t_in < d:
                return k, t_in, n
            t_in -= d
        return order[-1], STAGES[order[-1]].duration, len(order) - 1  # inalcançável; só por segurança

    def _layout(self, st: Stage) -> dict:
        """Parâmetros fixos de cada carro da etapa (calculados uma vez)."""
        if st.key in self._layout_cache:
            return self._layout_cache[st.key]
        rnd = random.Random(st.key)
        info: dict[str, dict] = {}
        count: dict[str, int] = {}
        for i, k in enumerate(st.cars):
            e = CATALOG[k]
            _name, _color, base = _CLASSES[e.cls]
            n = count.get(e.cls, 0)
            count[e.cls] = n + 1
            pace = base + 0.012 * n + rnd.uniform(-0.04, 0.04)
            info[k] = dict(order=i, rank_in_class=n, pace=pace)
        # distância inicial: dentro da classe os carros ficam a `gap_s` um do outro (as diferenças ficam estáveis);
        # as classes largam deslocadas para se misturarem na pista
        class_off = {"hyper": 0.0, "lmp2": -0.35, "lmp3": -0.1, "gt3": -0.6, "ff": 0.0, "fvee": -0.15, "mx5": -0.3}
        for cls in _CLASSES:
            members = [k for k in st.cars if CATALOG[k].cls == cls]
            acc = 0.0
            prev: Optional[str] = None
            for k in members:
                gap = st.gap_s
                if prev is not None and st.fight_behind and prev == st.player:
                    gap = st.fight_behind
                if prev is not None and st.fight_ahead and k == st.player:
                    gap = st.fight_ahead
                if prev is not None:
                    acc += gap + rnd.uniform(-0.2, 0.2) * st.gap_s
                speed = TRACK_LEN / info[k]["pace"]
                info[k]["start"] = (class_off[cls] * TRACK_LEN) - acc * speed
                prev = k
        self._layout_cache[st.key] = info
        return info

    # ---- snapshot ------------------------------------------------------- #
    def poll(self) -> Optional[Snapshot]:
        t_script = self._now()
        key, local, _n = self._where(t_script)
        st = STAGES[key]
        info = self._layout(st)
        ended = st.ends_at is not None and local >= st.ends_at
        base_t = (RACE_HEAD_START_S if not st.timed else 120.0) + local * st.time_scale

        present: list[str] = []
        for k in st.cars:
            if ended:
                continue
            if st.join.get(k, 0.0) > local:
                continue
            if st.leave.get(k, 1e9) <= local:
                continue
            present.append(k)

        dists = {k: max(0.0, info[k]["start"] + base_t * TRACK_LEN / info[k]["pace"]) for k in present}
        player_key = st.player
        sides: dict[str, str] = {}  # carros emparelhados ao lado do piloto agora
        if player_key in dists:
            for k, t0, t1, side in st.side_events:
                if k in dists and t0 <= local < t1:
                    dists[k] = dists[player_key] - 1.0
                    sides[k] = side

        for k, t0, t1 in st.approach_events:  # chega por trás (de 45 m a 3 m) e depois recua
            if k in dists and player_key in dists and t0 <= local < t1:
                u = 1.0 - abs(2.0 * (local - t0) / (t1 - t0) - 1.0)
                dists[k] = dists[player_key] - (45.0 * (1.0 - u) + 3.0)

        cars: list[CarState] = []
        order = sorted(present, key=lambda k: -dists[k])
        leader_d = dists[order[0]] if order else 0.0
        cls_pos: dict[str, int] = {}
        pos_of: dict[str, int] = {}
        for pos, k in enumerate(order, start=1):
            pos_of[k] = pos
        for slot, k in enumerate(st.cars):
            if k not in present:
                continue
            e = CATALOG[k]
            cname, color, base = _CLASSES[e.cls]
            pace = info[k]["pace"]
            d = dists[k]
            pos = pos_of[k]
            speed = TRACK_LEN / pace
            pct = (d / TRACK_LEN) % 1.0
            scripted = {e[0] for e in st.side_events} | {e[0] for e in st.approach_events}
            if st.lmu_style and k != player_key and k not in scripted:
                # LMU: o jogo só atualiza a posição dos outros carros ~8 vezes por segundo (testa a suavização);
                # os carros dos eventos de lado/aproximação ficam exatos para o roteiro do radar/spotter.
                step = speed * st.time_scale * LMU_UPDATE_S  # (o DEMO corre em tempo acelerado)
                pct = (math.floor(d / step) * step / TRACK_LEN) % 1.0
            x, z = _track_xy(pct)
            true_x, true_z = x, z
            if k in sides:  # emparelhado: deslocado para o lado do piloto
                lx, lz = _left(_dir(pct))
                off = LANE_M if sides[k] == "left" else -LANE_M
                x, z = x + lx * off, z + lz * off
            status = CarStatus.RUNNING
            if k == player_key and st.key == "treino" and local < 4.0:
                status = CarStatus.GARAGE  # começa na garagem (para testar "só na pista"/"só na garagem")
            pit = st.pits.get(k)
            if pit and pit[0] <= local < pit[1]:
                status = CarStatus.PITS
            if k in st.retire and local >= st.retire[k]:
                status = CarStatus.OUT
            lap_n = int(d // TRACK_LEN)
            lic_class, lic_sr = _LICENSES[slot % len(_LICENSES)]
            has_nrg = st.energy and e.cls in ("hyper", "gt3")
            energy = (100.0 - ((base_t * 0.35 + slot * 13.0) % 100.0)) if has_nrg else None
            best = last = None
            if st.timed:
                t_first = st.first_lap.get(k)
                if t_first is not None and local >= t_first:
                    # melhora aos poucos com o tempo (como quem vai achando ritmo)
                    best = pace * (1.0 + 0.018 * math.exp(-(local - t_first) / 14.0)) * 0.992
                    last = best * (1.0 + 0.004 * ((slot * 7 + int(local)) % 5))
            else:
                wob = 0.004 * math.sin(lap_n + slot)
                best = pace * 0.995
                last = pace * (1 + wob)
            cars.append(CarState(
                idx=slot, driver_name=PLAYER_NAME if k == player_key else e.driver, team_name=f"Demo Team {slot:02d}",
                car_number=e.number, car_model=e.model, class_name=cname,
                class_color=color, position=pos, class_position=0,
                laps_completed=lap_n, lap_dist_pct=pct,
                best_lap=best, last_lap=last,
                gap_leader=(None if st.timed else ((leader_d - d) / speed if pos > 1 else 0.0)),
                laps_behind_leader=(None if st.timed else int((leader_d - d) // TRACK_LEN)),
                gap_ahead=(None if st.timed or pos == 1 else (dists[order[pos - 2]] - d) / speed),
                status=status, is_player=(k == player_key),
                irating=None if st.lmu_style else e.ir,
                license=None if st.lmu_style else f"{lic_class} {lic_sr:.2f}",
                license_class=None if st.lmu_style else lic_class,
                license_sr=None if st.lmu_style else lic_sr,
                est_lap_time=pace,
                tire=_TIRES[slot % len(_TIRES)] if e.cls != "ff" else None,
                energy_pct=energy, vehicle_raw=e.model,
                country=None if st.lmu_style else e.country,
                world_x=x if st.lmu_style else (_estimated_xy(true_x, true_z, d)[0] if k == player_key else None),
                world_z=z if st.lmu_style else (_estimated_xy(true_x, true_z, d)[1] if k == player_key else None),
            ))
        # posição na classe, pela posição geral
        for c in sorted(cars, key=lambda c: c.position or 0):
            cls_pos[c.class_name or ""] = cls_pos.get(c.class_name or "", 0) + 1
            c.class_position = cls_pos[c.class_name or ""]

        me = next((c for c in cars if c.is_player), None)
        fuel = self._fuel(st, info, player_key, local, me)
        damage = self._damage(st, local, me)
        contact = self._contact(st, local, me)
        tires = self._tires(st, local) if me is not None else None
        pose = side_traffic = None
        if me is not None and st.lmu_style:
            f = _dir(me.lap_dist_pct or 0.0)
            pose = PlayerPose(forward=f, left=_left(f))
        elif me is not None:  # estilo iRacing: o "simulador" informa quantos carros há de cada lado
            side_traffic = (sum(1 for s in sides.values() if s == "left"), sum(1 for s in sides.values() if s == "right"))
        flags = ["checkered"] if ended else [f for t0, t1, f in FLAG_SCRIPT if t0 <= local < t1]
        if not ended and not st.lmu_style and local >= st.duration - CHECKERED_TAIL_S:
            flags = ["checkered"]  # nos últimos segundos de cada etapa aparece a bandeira de chegada
        self._player_idx = me.idx if me else -1
        inputs = self._inputs(me.lap_dist_pct or 0.0, local) if me else None
        remaining = max(0.0, st.total_s - (base_t if not st.timed else local * 6))
        session = SessionState(
            active=not ended, track_name=st.track, track_length_m=TRACK_LEN,
            session_type=st.session_type,
            time_remaining_s=remaining, flag="checkered" if ended else "green", in_realtime=not ended,
            elapsed_s=st.total_s - remaining, total_s=st.total_s,
            incidents=None if st.lmu_style else st.incidents,
            incident_limit=None if st.lmu_style else (25 if st.incidents else None),
            flags=flags)
        caps = {CAP_STANDINGS, CAP_GAPS, CAP_BEST_LAST_LAP, CAP_CAR_NUMBER, CAP_CAR_MODEL, CAP_CLASS, CAP_INPUTS,
                CAP_STEERING_ANGLE, CAP_SHIFT_LIGHTS_DERIVED, CAP_TRACKMAP_PCT, CAP_TIRE, CAP_FUEL}
        caps.add(CAP_TRACKMAP_XY if st.lmu_style else CAP_PLAYER_XY_ESTIMATED)
        if st.damage:
            caps.add(CAP_DAMAGE)
        if st.lmu_style:
            caps.add(CAP_CONTACT)
        caps |= {CAP_TIRE_DETAIL, CAP_FLAGS}
        if pose is not None:
            caps.add(CAP_POSE)
        if side_traffic is not None:
            caps.add(CAP_SIDE_TRAFFIC)
        if st.energy:
            caps.add(CAP_ENERGY)
        if not st.lmu_style:
            caps |= {CAP_PROFILE_IRATING, CAP_PROFILE_LICENSE, CAP_INCIDENTS}
        if st.lmu_style:
            badge = _SAFETY_BADGES[int(local // 5) % len(_SAFETY_BADGES)]  # troca a cada 5 s: mostra todos os ícones
            profile = DriverProfile(driver_rank=_DR_CYCLE[int(local // 7) % len(_DR_CYCLE)], safety_rank="S3", contact_badge=badge,
                                    source=ProfileSource.MANUAL, notes=["Valores fictícios do modo DEMO."])
        else:
            profile = DriverProfile(license_class="A", license_sr=3.2, irating=2500,
                                    source=ProfileSource.MANUAL, notes=["Valores fictícios do modo DEMO."])
        return Snapshot(
            sim=Sim.DEMO, connected=True, is_demo=True,
            session=session, inputs=inputs, cars=cars, player_idx=self._player_idx if me else None,
            fuel=fuel, damage=damage, contact=contact, tires=tires, pose=pose, side_traffic=side_traffic,
            in_garage=bool(me and me.status == CarStatus.GARAGE),
            driving=bool(me and me.status not in (CarStatus.GARAGE, CarStatus.OUT)),
            profile=profile, capabilities=frozenset(caps),
            warnings=["MODO DEMO: dados sintéticos, não vêm de um simulador."],
            status_text=f"DEMO · {st.label}",
            debug={"demo_stage": st.key, "demo_stage_t": round(local, 1), "demo_scenario": self.scenario},
        )

    @staticmethod
    def _laps_at(st: Stage, info: dict, key: str, local: float) -> float:
        base_t = (RACE_HEAD_START_S if not st.timed else 120.0) + local * st.time_scale
        return max(0.0, info[key]["start"] + base_t * TRACK_LEN / info[key]["pace"]) / TRACK_LEN

    def _fuel(self, st: Stage, info: dict, key: str, local: float, me) -> Optional[FuelState]:
        """Combustível sintético: queima por volta e reabastece se o piloto tiver uma parada nos boxes."""
        if me is None:
            return None
        l0, now = self._laps_at(st, info, key, 0.0), self._laps_at(st, info, key, local)
        level = st.fuel_start - FUEL_BURN_L * (now - l0)
        pit = st.pits.get(key)
        if pit and local >= pit[0]:
            at_in = max(0.0, st.fuel_start - FUEL_BURN_L * (self._laps_at(st, info, key, pit[0]) - l0))
            if local < pit[1]:
                level = at_in + (FUEL_CAPACITY_L - at_in) * (local - pit[0]) / (pit[1] - pit[0])
            else:
                level = FUEL_CAPACITY_L - FUEL_BURN_L * (now - self._laps_at(st, info, key, pit[1]))
        return FuelState(level_l=max(0.0, min(FUEL_CAPACITY_L, level)), capacity_l=FUEL_CAPACITY_L)

    @staticmethod
    def _tires(st: Stage, local: float) -> TireSet:
        """Pneus sintéticos: a temperatura passa por frio/bom/quente, o desgaste desce e (no LMU) uma roda fura."""
        wheels = {}
        for k, corner in enumerate(TIRE_CORNERS):
            temp = 85.0 + 28.0 * math.sin(local / 5.0 + k * 1.4)
            wear = max(2.0, 100.0 - local * (0.9 + 0.15 * (k % 2)) - 4.0 * k)
            zt = (temp - 7.0, temp, temp + 7.0) if k % 2 == 0 else (temp + 6.0, temp, temp - 6.0)  # esquerda/centro/direita
            zw = None if st.lmu_style else (wear + 2.0, wear, wear - 3.0)  # o LMU só informa um desgaste por roda
            wheels[corner] = TireWheel(
                temp_c=temp, optimal_c=90.0 if st.lmu_style else None, temps_c=zt, wear_zones=zw,
                pressure_kpa=170.0 + 6.0 * math.sin(local / 7.0 + k) + 2.0 * k, wear_pct=wear,
                flat=(st.lmu_style and corner == "rr" and 24.0 <= local < 30.0))
        return TireSet(wheels=wheels, compound="Medium" if st.lmu_style else None)

    @staticmethod
    def _contact(st: Stage, local: float, me) -> Optional[ContactState]:
        """LMU não publica incidentes: o DEMO simula 2 batidas (uma leve demais para contar) e 2 saídas de pista."""
        if me is None or not st.lmu_style:
            return None
        hits = [(8.0, 400.0), (14.0, 50.0), (20.0, 900.0)]  # (instante, intensidade)
        last = max((t for t, _ in hits if t <= local), default=None)
        mag = next((m for t, m in hits if t == last), 0.0)
        off = (14.0 <= local < 16.0) or (26.0 <= local < 28.0)
        return ContactState(impact_et=1000.0 + (last or 0.0), impact_mag=mag, wheels_off=4 if off else 0)

    @staticmethod
    def _damage(st: Stage, local: float, me) -> Optional[CarDamage]:
        if me is None or not st.damage:
            return None
        if st.damage == "zones":  # amassados aparecendo aos poucos; "conserta" no fim do ciclo
            z = [0] * 8
            if local < 30.0:
                if local >= 6.0:
                    z[0] = 1
                if local >= 12.0:
                    z[1], z[7] = 2, 1
                if local >= 18.0:
                    z[4] = 1
            return CarDamage(zones=z, detached=18.0 <= local < 30.0, overheating=24.0 <= local < 30.0)
        if local < 12.0:  # "repair": o reparo só aparece depois da batida e zera ao passar pelos boxes
            return CarDamage(repair_required_s=0.0, repair_optional_s=0.0, tow_s=0.0)
        pit = st.pits.get(st.player)
        if pit and local >= pit[1]:
            return CarDamage(repair_required_s=0.0, repair_optional_s=0.0, tow_s=0.0)
        left = 1.0 if not pit or local < pit[0] else max(0.0, (pit[1] - local) / (pit[1] - pit[0]))
        return CarDamage(repair_required_s=45.0 * left, repair_optional_s=20.0 * left, tow_s=0.0)

    @staticmethod
    def _inputs(pct: float, t: float) -> Inputs:
        # Perfil sintético: 4 curvas por volta com frenagem, troca de marcha e esterço.
        phase = (pct * 4.0) % 1.0
        brake = _clamp(1.0 - abs(phase - 0.12) / 0.10) if phase < 0.22 else 0.0
        throttle = 0.0 if brake > 0.05 else _clamp((phase - 0.22) / 0.2 + 0.35)
        corner = math.sin(math.pi * _clamp((phase - 0.1) / 0.4)) if 0.1 < phase < 0.5 else 0.0
        side = 1.0 if int(pct * 4.0) % 2 == 0 else -1.0
        steer = _clamp(corner * 0.55, 0, 1) * side
        speed = 28 + 40 * (1 - corner) * (1 - 0.7 * brake)
        gear = max(2, min(6, int(speed / 11)))
        rpm = 4000 + 4100 * ((speed % 11) / 11)
        rpm_max = 8200.0
        return Inputs(
            throttle=throttle, brake=brake, clutch=_clamp(1.0 - (speed % 11) / 0.8), steering=steer,
            steering_deg=steer * 270.0, gear=gear, rpm=rpm, rpm_max=rpm_max, speed_ms=speed,
            shift_pct=_clamp((rpm - 7200) / 900), shift_source="derived",
        )
