"""Pneus: temperatura, pressão e desgaste por roda (sem Qt, testável)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import TIRE_CORNERS, Snapshot, TireWheel

COLD_DELTA_C, HOT_DELTA_C = -10.0, 10.0  # em relação à temperatura ideal (quando o jogo informa)
GENERIC_COLD_C, GENERIC_HOT_C = 65.0, 105.0  # sem temperatura ideal informada (iRacing): faixa genérica
PRESSURE_UNITS = ("kpa", "psi")


GENERIC_IDEAL_C = 85.0  # sem temperatura ideal informada
LOW_WEAR_PCT = 90.0  # a zona mais gasta do pneu fica em destaque abaixo disso
#: cor da temperatura, pela diferença para a ideal (°C): azul -> verde -> lima -> amarelo -> laranja -> vermelho
_TEMP_RAMP = ((-20.0, "#5bc0ff"), (-8.0, "#4fd0b0"), (0.0, "#3ddc6b"), (6.0, "#a6d62f"), (12.0, "#f5c400"),
              (22.0, "#ff8a1f"), (32.0, "#ff4d3a"))


def _hex(c: str) -> tuple[int, int, int]:
    return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)


def temp_color(temp_c: Optional[float], optimal_c: Optional[float] = None) -> str:
    """Cor (hex) da temperatura, em degradê pela diferença para a ideal."""
    if temp_c is None:
        return "#3a3a44"
    d = temp_c - (optimal_c if optimal_c is not None else GENERIC_IDEAL_C)
    ramp = _TEMP_RAMP
    if d <= ramp[0][0]:
        return ramp[0][1]
    for (d0, c0), (d1, c1) in zip(ramp, ramp[1:]):
        if d <= d1:
            f = (d - d0) / (d1 - d0)
            a, b = _hex(c0), _hex(c1)
            return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * f) for i in range(3))
    return ramp[-1][1]


def zone_state(temp_c: Optional[float], optimal_c: Optional[float]) -> str:
    if temp_c is None:
        return "nodata"
    if optimal_c is not None:
        d = temp_c - optimal_c
        return "cold" if d < COLD_DELTA_C else ("hot" if d > HOT_DELTA_C else "ok")
    return "cold" if temp_c < GENERIC_COLD_C else ("hot" if temp_c > GENERIC_HOT_C else "ok")


@dataclass
class TireCell:
    corner: str
    temp_c: Optional[float] = None
    temp_state: str = "nodata"  # cold | ok | hot | nodata
    pressure_kpa: Optional[float] = None
    wear_pct: Optional[float] = None
    wear_state: str = "nodata"  # ok | warn | danger | nodata
    flat: bool = False
    detached: bool = False
    temps: tuple = (None, None, None)  # esquerda/centro/direita (°C); sem zonas, repete a média
    temp_colors: tuple = ("#3a3a44",) * 3
    wears: tuple = (None, None, None)  # esquerda/centro/direita (100 = novo); sem zonas, repete o desgaste da roda
    low_wear: Optional[int] = None  # índice da zona mais gasta, se estiver abaixo de LOW_WEAR_PCT
    zoned: bool = False  # True = o simulador informa o desgaste por zona (iRacing); False = um valor só por roda (LMU)
    worst_wear: Optional[float] = None  # o menor desgaste entre as zonas (100 = novo)


@dataclass
class TireView:
    has_data: bool = False
    cells: dict[str, TireCell] = field(default_factory=dict)
    compound: Optional[str] = None
    lap: Optional[int] = None  # volta atual (voltas completas + 1)
    message: str = ""


def temp_state(w: TireWheel) -> str:
    return zone_state(w.temp_c, w.optimal_c)


def wear_state(pct: Optional[float]) -> str:
    if pct is None:
        return "nodata"
    return "ok" if pct >= 60 else ("warn" if pct >= 30 else "danger")


def get_pressure_unit(options: dict) -> str:
    v = str(options.get("pressure_unit", "kpa")).lower() if isinstance(options, dict) else "kpa"
    return v if v in PRESSURE_UNITS else "kpa"


def format_pressure(kpa: Optional[float], unit: str) -> str:
    if kpa is None:
        return "-"
    return f"{kpa * 0.1450377:.1f}" if unit == "psi" else f"{kpa:.0f}"


def tire_view(snap: Optional[Snapshot]) -> TireView:
    if snap is None or not snap.connected:
        return TireView(message="Aguardando dados")
    ts = snap.tires
    if ts is None or not ts.wheels:
        return TireView(message="Sem dados dos pneus")
    cells = {}
    for corner in TIRE_CORNERS:
        w = ts.wheels.get(corner)
        if w is None:
            cells[corner] = TireCell(corner)
            continue
        temps = tuple(w.temps_c) if w.temps_c else (w.temp_c,) * 3
        wears = tuple(w.wear_zones) if w.wear_zones else (w.wear_pct,) * 3
        known = [(v, i) for i, v in enumerate(wears) if v is not None]
        low = None
        if known:
            v, i = min(known)
            low = i if v < LOW_WEAR_PCT else None
        cells[corner] = TireCell(corner, w.temp_c, temp_state(w), w.pressure_kpa, w.wear_pct, wear_state(w.wear_pct),
                                 bool(w.flat), bool(w.detached), temps,
                                 tuple(temp_color(t, w.optimal_c) for t in temps), wears, low,
                                 bool(w.wear_zones), min((v for v, _i in known), default=None))
    me = snap.player()
    lap = me.laps_completed + 1 if me is not None and me.laps_completed is not None else None
    return TireView(True, cells, ts.compound, lap)
