"""Modelo de dados padronizado.

Todos os providers (iRacing, LMU, DEMO) produzem um `Snapshot`. Os módulos
visuais só conhecem este modelo, nunca as APIs dos simuladores.

Regra de ouro do projeto: **nenhum valor é inventado**. Quando uma informação
não está disponível, o campo é `None` e o nome da capacidade correspondente
não aparece em `Snapshot.capabilities`.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class Sim(str, Enum):
    IRACING = "iracing"
    LMU = "lmu"
    DEMO = "demo"
    NONE = "none"


class CarStatus(str, Enum):
    RUNNING = "running"
    PITS = "pits"
    GARAGE = "garage"
    OUT = "out"  # abandonou / fora do mundo
    DISQUALIFIED = "dsq"
    FINISHED = "finished"


class ProfileSource(str, Enum):
    LIVE = "live"  # lido do simulador em tempo real
    MANUAL = "manual"  # informado pelo usuário nas configurações
    UNAVAILABLE = "unavailable"


# Capacidades: o que o provider atual realmente consegue entregar.
CAP_STANDINGS = "standings"
CAP_GAPS = "gaps"
CAP_BEST_LAST_LAP = "best_last_lap"
CAP_CAR_NUMBER = "car_number"
CAP_CAR_MODEL = "car_model"
CAP_CLASS = "class"
CAP_INPUTS = "inputs"
CAP_STEERING_ANGLE = "steering_angle"
CAP_SHIFT_LIGHTS_SIM = "shift_lights_sim"  # fornecido pelo simulador
CAP_SHIFT_LIGHTS_DERIVED = "shift_lights_derived"  # calculado por RPM
CAP_TRACKMAP_PCT = "trackmap_pct"  # só posição percentual na volta
CAP_TRACKMAP_XY = "trackmap_xy"  # coordenadas de mundo
CAP_PROFILE_IRATING = "profile_irating"
CAP_PROFILE_LICENSE = "profile_license"
CAP_PROFILE_RANKS = "profile_ranks"  # Driver Rank / Safety Rank
CAP_TIRE = "tire"  # composto de pneu de cada carro
CAP_ENERGY = "energy"  # energia virtual / bateria dos carros
CAP_INCIDENTS = "incidents"  # contagem de incidentes do piloto
CAP_FUEL = "fuel"  # combustível do carro do piloto
CAP_DAMAGE = "damage"  # avarias do carro do piloto (LMU: amassados por região; iRacing: tempo de reparo)
CAP_TIRE_DETAIL = "tire_detail"  # temperatura / pressão / desgaste por roda do carro do piloto
CAP_FLAGS = "flags"  # bandeiras mostradas ao piloto
CAP_SIDE_TRAFFIC = "side_traffic"  # carros ao lado (o simulador informa: iRacing CarLeftRight)
CAP_POSE = "pose"  # orientação do carro do piloto: permite achar carros ao lado e montar o radar (LMU)
CAP_CONTACT = "contact"  # batidas e saídas de pista do piloto, contadas a partir da telemetria (LMU)
CAP_PLAYER_XY_ESTIMATED = "player_xy_estimated"  # posição do piloto ESTIMADA por velocidade x rumo (iRacing sem Lat/Lon): só serve para gravar o traçado
CAP_PLAYER_XY = "player_xy"  # só o carro do piloto tem coordenadas (iRacing: GPS Lat/Lon); serve para gravar o traçado


@dataclass
class DriverProfile:
    """Perfil do piloto local (NÃO é telemetria ao vivo)."""

    license_class: Optional[str] = None  # R, D, C, B, A, P
    license_sr: Optional[float] = None  # Safety Rating numérico (iRacing)
    irating: Optional[int] = None
    driver_rank: Optional[str] = None  # LMU
    safety_rank: Optional[str] = None  # LMU (texto, ex.: "S3")
    contact_badge: Optional[str] = None  # LMU: Driver Contact Badge (Rookie, Good, Trusted, Warning, Probation, Creator, Driver, Staff)
    source: ProfileSource = ProfileSource.UNAVAILABLE
    notes: list[str] = field(default_factory=list)


@dataclass
class Inputs:
    throttle: float = 0.0  # 0..1 (pedal pressionado)
    brake: float = 0.0  # 0..1
    clutch: float = 0.0  # 0..1 (1 = pedal totalmente pressionado)
    steering: float = 0.0  # -1..1 (negativo = esquerda)
    steering_deg: Optional[float] = None  # graus no volante, positivo = direita
    gear: int = 0  # -1 = ré, 0 = neutro
    rpm: float = 0.0
    rpm_max: Optional[float] = None
    speed_ms: float = 0.0
    shift_pct: Optional[float] = None  # 0..1, 1 = hora de trocar
    shift_source: Optional[str] = None  # "sim" | "derived"
    shift_blink: Optional[bool] = None  # LEDs piscando (hora de trocar) segundo o próprio jogo; None = calcular pelo shift_pct
    abs_active: Optional[bool] = None  # ABS atuando agora (None = o simulador não informa)
    tc_active: Optional[bool] = None  # controle de tração atuando agora (None = não informa)
    lockup: Optional[bool] = None  # roda travando (derivado no LMU; None = não dá para saber)

    @property
    def speed_kmh(self) -> float:
        return self.speed_ms * 3.6

    @property
    def speed_mph(self) -> float:
        return self.speed_ms * 2.2369362921


@dataclass
class CarState:
    idx: int
    driver_name: str = ""
    team_name: Optional[str] = None
    car_number: Optional[str] = None
    car_model: Optional[str] = None
    class_name: Optional[str] = None
    class_color: Optional[str] = None  # "#rrggbb"
    position: Optional[int] = None
    class_position: Optional[int] = None
    laps_completed: Optional[int] = None
    lap_dist_pct: Optional[float] = None  # 0..1
    best_lap: Optional[float] = None  # segundos
    last_lap: Optional[float] = None
    gap_leader: Optional[float] = None  # segundos
    laps_behind_leader: Optional[int] = None
    gap_ahead: Optional[float] = None  # segundos para o carro à frente
    est_lap_time: Optional[float] = None
    status: CarStatus = CarStatus.RUNNING
    is_player: bool = False
    irating: Optional[int] = None
    license: Optional[str] = None  # ex.: "A 3.45"
    world_x: Optional[float] = None  # metros (somente LMU)
    world_z: Optional[float] = None
    license_class: Optional[str] = None  # R, D, C, B, A, P (iRacing)
    license_sr: Optional[float] = None  # Safety Rating numérico (iRacing)
    tire: Optional[str] = None  # composto normalizado: S, M, H, W, I... (None = desconhecido)
    energy_pct: Optional[float] = None  # 0..100, energia virtual (LMU) quando o carro usa
    vehicle_raw: Optional[str] = None  # texto bruto do carro, usado para inferir a marca
    country: Optional[str] = None  # código ISO em minúsculas (ex.: "br", "gb-eng"); None = desconhecido
    in_session: bool = True  # False = piloto que SAIU da sessão (lembrado pelo `Roster`, mostrado apagado)


@dataclass
class FuelState:
    """Combustível do carro do piloto (litros). Fonte: telemetria; nada é estimado aqui."""
    level_l: Optional[float] = None
    capacity_l: Optional[float] = None  # tanque; None = o simulador não informa


#: regiões de dano do LMU (ordem de `mDentSeverity`): frente, frente-esq., esquerda, trás-esq., trás, trás-dir.,
#: direita, frente-dir.  VERIFICAR a ordem no jogo.
DAMAGE_ZONES = ("front", "front_left", "left", "rear_left", "rear", "rear_right", "right", "front_right")


@dataclass
class CarDamage:
    """Avarias do carro do piloto. Cada fonte preenche só o que realmente informa (o resto fica None)."""
    zones: Optional[list[int]] = None  # 8 valores 0..2 na ordem de DAMAGE_ZONES (LMU)
    detached: Optional[bool] = None  # peça solta (LMU)
    overheating: Optional[bool] = None  # motor superaquecendo (LMU)
    repair_required_s: Optional[float] = None  # tempo de reparo obrigatório nos boxes (iRacing)
    repair_optional_s: Optional[float] = None  # reparo opcional (iRacing)
    tow_s: Optional[float] = None  # tempo de reboque restante (iRacing)


TIRE_CORNERS = ("fl", "fr", "rl", "rr")  # dianteira esq., dianteira dir., traseira esq., traseira dir.


@dataclass
class TireWheel:
    """Uma roda. Cada fonte preenche só o que realmente informa."""
    temp_c: Optional[float] = None  # média da banda de rodagem (°C)
    optimal_c: Optional[float] = None  # temperatura ideal do composto, se o simulador informa (LMU)
    pressure_kpa: Optional[float] = None
    wear_pct: Optional[float] = None  # 100 = pneu novo, desce com o uso
    temps_c: Optional[tuple[float, float, float]] = None  # temperatura esquerda/centro/direita da banda (°C), se informada
    wear_zones: Optional[tuple[float, float, float]] = None  # desgaste esquerda/centro/direita (100 = novo), se informado
    flat: Optional[bool] = None
    detached: Optional[bool] = None
    stale: bool = False  # True = o simulador não está informando agora; são os últimos valores reais (ex.: do último pit)


@dataclass
class TireSet:
    wheels: dict[str, TireWheel] = field(default_factory=dict)  # chaves de TIRE_CORNERS
    compound: Optional[str] = None  # texto do composto (LMU)


#: bandeiras que o overlay sabe mostrar, da MAIS para a MENOS importante
FLAG_PRIORITY = ("red", "black", "disqualify", "repair", "blue", "yellow", "caution", "debris", "white",
                 "checkered", "green")


@dataclass
class PlayerPose:
    """Orientação do carro do piloto no mundo (vetores unitários no plano X/Z)."""
    forward: tuple[float, float]
    left: tuple[float, float]


@dataclass
class ContactState:
    """Leituras brutas para contar batidas e saídas de pista do piloto (quem conta é `core/incidents.py`)."""
    impact_et: Optional[float] = None  # instante da última batida (muda a cada impacto novo)
    impact_mag: Optional[float] = None  # intensidade dessa batida
    wheels_off: Optional[int] = None  # rodas sobre grama/terra/brita (0..4)


@dataclass
class SessionState:
    active: bool = False
    track_name: Optional[str] = None
    track_length_m: Optional[float] = None
    session_type: Optional[str] = None  # Practice / Qualify / Race ...
    time_remaining_s: Optional[float] = None
    laps_total: Optional[int] = None
    flag: Optional[str] = None  # green / fcy / checkered ...
    in_realtime: Optional[bool] = None
    elapsed_s: Optional[float] = None  # tempo decorrido da sessão
    total_s: Optional[float] = None  # duração total (sessões por tempo)
    incidents: Optional[int] = None  # incidentes do piloto local (iRacing)
    incident_limit: Optional[int] = None  # limite da sessão; None = ilimitado/desconhecido
    flags: list[str] = field(default_factory=list)  # bandeiras mostradas AO PILOTO agora (ver FLAG_PRIORITY)


@dataclass
class Snapshot:
    sim: Sim = Sim.NONE
    connected: bool = False
    is_demo: bool = False
    timestamp: float = field(default_factory=time.time)
    session: SessionState = field(default_factory=SessionState)
    inputs: Optional[Inputs] = None
    cars: list[CarState] = field(default_factory=list)
    player_idx: Optional[int] = None
    fuel: Optional[FuelState] = None
    damage: Optional[CarDamage] = None
    contact: Optional[ContactState] = None
    tires: Optional[TireSet] = None
    side_traffic: Optional[tuple[int, int]] = None  # (carros à esquerda, à direita) quando o simulador informa
    pose: Optional[PlayerPose] = None
    in_garage: Optional[bool] = None  # piloto local na garagem (None = o simulador não informa)
    driving: Optional[bool] = None  # piloto DENTRO do carro, dirigindo (False = replay, tela de resultado, entre sessões; None = não informa)
    profile: DriverProfile = field(default_factory=DriverProfile)
    capabilities: frozenset[str] = frozenset()
    warnings: list[str] = field(default_factory=list)
    status_text: str = ""
    #: valores brutos do provider, só para diagnóstico (`diag`) e validação com o jogo
    debug: dict[str, Any] = field(default_factory=dict)

    def player(self) -> Optional[CarState]:
        for c in self.cars:
            if c.idx == self.player_idx:
                return c
        return None

    def has(self, capability: str) -> bool:
        return capability in self.capabilities


def to_jsonable(obj: Any) -> Any:
    """Converte Snapshot (ou qualquer dataclass do modelo) em estrutura JSON."""
    if hasattr(obj, "__dataclass_fields__"):
        return to_jsonable(asdict(obj))
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(to_jsonable(v) for v in obj)
    if isinstance(obj, Enum):
        return obj.value
    return obj
