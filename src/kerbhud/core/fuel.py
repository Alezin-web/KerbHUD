"""Fuel Calculator (sem Qt, testável).

Só usa o que o simulador publica: nível de combustível (e a energia virtual do LMU quando o carro tem). O consumo por
volta é MEDIDO nas últimas voltas completas e limpas (sem box e sem reabastecimento). Nada é estimado antes da primeira
volta válida. As voltas restantes da corrida vêm do número de voltas ou do tempo restante (estimativa, ver `laps_to_go`).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .model import CarStatus, Snapshot

KEEP_LAPS = 5  # voltas na média
RESERVE_CHOICES = (0.0, 0.5, 1.0, 2.0)  # voltas de reserva
DEFAULT_RESERVE = 0.5
REFUEL_JUMP_L = 0.5  # subida de nível que conta como reabastecimento
REFUEL_JUMP_PCT = 1.0  # idem para energia (pontos percentuais)


def get_reserve(options: dict) -> float:
    try:
        v = float(options.get("reserve_laps", DEFAULT_RESERVE))
    except (TypeError, ValueError):
        return DEFAULT_RESERVE
    return v if v in RESERVE_CHOICES else DEFAULT_RESERVE


@dataclass
class Meter:
    """Resultado de UMA grandeza (combustível em L ou energia em %)."""
    unit: str
    level: Optional[float] = None
    capacity: Optional[float] = None
    per_lap: Optional[float] = None
    last_lap: Optional[float] = None
    laps_left: Optional[float] = None  # voltas que o que resta rende
    need: Optional[float] = None  # para terminar a corrida (com reserva)
    add: Optional[float] = None  # a acrescentar (>= 0)
    samples: int = 0
    state: str = "nodata"  # ok | warn | danger | nodata
    max_per_lap: Optional[float] = None  # maior consumo entre as voltas medidas
    min_per_lap: Optional[float] = None
    history: list = field(default_factory=list)  # (volta, usado, diferença p/ a média), da mais recente p/ a mais antiga
    laps_to_go: Optional[float] = None
    reserve: float = 0.0

    def scenario(self, usage: Optional[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """(voltas que rende, a abastecer, quanto sobra na bandeirada SEM parar) se o consumo por volta for `usage`.

        'sobra' é None quando não há como estimar ou quando não chega ao fim."""
        if not usage or usage <= 0 or self.level is None:
            return None, None, None
        laps = self.level / usage
        if self.laps_to_go is None:
            return laps, None, None
        need = (self.laps_to_go + self.reserve) * usage
        finish = self.level - self.laps_to_go * usage
        return laps, max(0.0, need - self.level), (finish if finish >= 0 else None)

    @property
    def pct(self) -> Optional[float]:
        if self.level is None or not self.capacity:
            return None
        return max(0.0, min(1.0, self.level / self.capacity))


@dataclass
class FuelView:
    fuel: Optional[Meter] = None
    energy: Optional[Meter] = None
    laps_to_go: Optional[float] = None
    message: str = ""

    @property
    def available(self) -> bool:
        return self.fuel is not None or self.energy is not None


class _LapMeter:
    def __init__(self, unit: str, jump: float):
        self.unit, self.jump = unit, jump
        self.reset()

    def reset(self) -> None:
        self.hist: deque = deque(maxlen=KEEP_LAPS)
        self.laps: deque = deque(maxlen=KEEP_LAPS)  # (nº da volta, usado), para a tabela de voltas
        self.start: Optional[float] = None
        self.prev: Optional[float] = None
        self.dirty = False
        self.last: Optional[float] = None

    def feed(self, level: float, lap_changed: bool, pitted: bool, lap: Optional[int] = None) -> None:
        if self.prev is not None and level > self.prev + self.jump:
            self.dirty = True  # reabasteceu
        if pitted:
            self.dirty = True
        if lap_changed:
            if self.start is not None and not self.dirty:
                used = self.start - level
                if used > 0:
                    self.hist.append(used)
                    self.laps.append((lap, used))
                    self.last = used
            self.start, self.dirty = level, False
        self.prev = level

    @property
    def per_lap(self) -> Optional[float]:
        return sum(self.hist) / len(self.hist) if self.hist else None


class FuelTracker:
    def __init__(self) -> None:
        self._sig: Optional[tuple] = None
        self._lap: Optional[int] = None
        self._fuel = _LapMeter("L", REFUEL_JUMP_L)
        self._energy = _LapMeter("%", REFUEL_JUMP_PCT)

    def reset(self) -> None:
        self._sig, self._lap = None, None
        self._fuel.reset()
        self._energy.reset()

    def update(self, snap: Snapshot, reserve_laps: float = DEFAULT_RESERVE) -> FuelView:
        me = snap.player()
        if not snap.connected or me is None:
            self.reset()
            return FuelView(message="Aguardando dados")
        sig = (snap.sim, snap.session.track_name, snap.session.session_type)
        lap = me.laps_completed
        if sig != self._sig or lap is None or (self._lap is not None and (lap < self._lap or lap > self._lap + 1)):
            self.reset()  # sessão nova, volta reiniciada (reset ao box/garagem) ou salto: recomeça a medir
            self._sig = sig
        lap_changed = lap is not None and self._lap is not None and lap == self._lap + 1
        # a volta em andamento na 1ª leitura é parcial: o 1º cruzamento da linha só marca o ponto de partida
        self._lap = lap
        pitted = me.status in (CarStatus.PITS, CarStatus.GARAGE, CarStatus.OUT)

        view = FuelView()
        laps_to_go = self._laps_to_go(snap, me)
        view.laps_to_go = laps_to_go
        if snap.fuel is not None and snap.fuel.level_l is not None:
            self._fuel.feed(snap.fuel.level_l, lap_changed, pitted, lap)
            view.fuel = self._meter(self._fuel, snap.fuel.level_l, snap.fuel.capacity_l, laps_to_go, reserve_laps)
        if me.energy_pct is not None:
            self._energy.feed(me.energy_pct, lap_changed, pitted, lap)
            view.energy = self._meter(self._energy, me.energy_pct, 100.0, laps_to_go, reserve_laps)
        if not view.available:
            view.message = "Sem dados de combustível"
        return view

    @staticmethod
    def _laps_to_go(snap: Snapshot, me) -> Optional[float]:
        pct = me.lap_dist_pct or 0.0
        total = snap.session.laps_total
        if total and 0 < total < 100000 and me.laps_completed is not None:
            return max(0.0, total - me.laps_completed - pct)
        remaining = snap.session.time_remaining_s
        ref = me.last_lap or me.best_lap or me.est_lap_time
        if remaining is not None and 0 <= remaining < 604800 and ref and ref > 20:
            return remaining / ref + 0.5  # + meia volta: o tempo acaba no meio de uma volta e ela é completada
        return None

    @staticmethod
    def _meter(lm: _LapMeter, level: float, capacity: Optional[float], laps_to_go: Optional[float],
               reserve: float) -> Meter:
        m = Meter(unit=lm.unit, level=level, capacity=capacity, per_lap=lm.per_lap, last_lap=lm.last,
                  samples=len(lm.hist), laps_to_go=laps_to_go, reserve=reserve)
        if m.per_lap is None or m.per_lap <= 0:
            return m
        m.max_per_lap, m.min_per_lap = max(lm.hist), min(lm.hist)
        m.history = [(lap, used, used - m.per_lap) for lap, used in reversed(lm.laps)]
        m.laps_left = level / m.per_lap
        if laps_to_go is not None:
            m.need = (laps_to_go + reserve) * m.per_lap
            m.add = max(0.0, m.need - level)
            if m.laps_left < 1.0:
                m.state = "danger"
            elif m.add > 0:
                m.state = "warn"
            else:
                m.state = "ok"
        else:
            m.state = "danger" if m.laps_left < 1.0 else ("warn" if m.laps_left < 3.0 else "ok")
        return m


def format_amount(v: Optional[float], unit: str) -> str:
    if v is None or not math.isfinite(v):
        return "—"
    return f"{v:.1f} {unit}" if unit == "L" else f"{v:.0f}%"
