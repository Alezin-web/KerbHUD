"""Spotter visual: há carro ao lado? (sem Qt, testável)

iRacing: o próprio simulador informa (`CarLeftRight`). LMU: calculado pela geometria, com a posição dos carros e a
orientação do seu carro. Nada de áudio: só o aviso visual. Ao sumir, o aviso é mantido por `HOLD_S` para não piscar.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .model import CarStatus, Snapshot

CAR_HALF_LEN_M = 5.5  # |distância à frente/atrás| abaixo disto = "lado a lado"
LANE_MIN_M, LANE_MAX_M = 1.2, 5.5  # distância lateral (centro a centro) que conta como "ao lado"
HOLD_S = 0.3
SAME_STRETCH_M = 25.0  # carros mais longe que isso pela volta não contam (trecho paralelo/fora da pista)


def same_stretch(snap: Snapshot, car, max_gap_m: float) -> bool:
    """False se o carro está em outro trecho da pista (longe pela volta), mesmo que perto em linha reta.

    Evita falsos alertas de carros em trechos paralelos, fora da pista ou em outra parte do circuito."""
    me, track = snap.player(), snap.session.track_length_m
    if me is None or not track or me.lap_dist_pct is None or car.lap_dist_pct is None:
        return True  # sem como saber: não corta
    gap = abs((car.lap_dist_pct - me.lap_dist_pct + 0.5) % 1.0 - 0.5) * track
    return gap <= max_gap_m


def relative_xy(snap: Snapshot, car) -> Optional[tuple[float, float]]:
    """(à esquerda, à frente) em metros do `car` em relação ao meu carro, ou None se não há como saber."""
    me, pose = snap.player(), snap.pose
    if me is None or pose is None or me.world_x is None or me.world_z is None:
        return None
    if car.world_x is None or car.world_z is None:
        return None
    dx, dz = car.world_x - me.world_x, car.world_z - me.world_z
    left = dx * pose.left[0] + dz * pose.left[1]
    fwd = dx * pose.forward[0] + dz * pose.forward[1]
    return left, fwd


def side_traffic(snap: Snapshot) -> Optional[tuple[int, int]]:
    """(carros à esquerda, carros à direita) agora; None = sem informação."""
    if not snap.connected:
        return None
    if snap.side_traffic is not None:
        return snap.side_traffic
    if snap.pose is None:
        return None
    left = right = 0
    for c in snap.cars:
        if c.is_player or not c.in_session or c.status != CarStatus.RUNNING:
            continue
        rel = relative_xy(snap, c)
        if rel is None or not same_stretch(snap, c, SAME_STRETCH_M):
            continue
        lat, fwd = rel
        if abs(fwd) <= CAR_HALF_LEN_M and LANE_MIN_M <= abs(lat) <= LANE_MAX_M:
            if lat > 0:
                left += 1
            else:
                right += 1
    return left, right


def side_offsets(snap: Snapshot) -> tuple[Optional[float], Optional[float]]:
    """(esquerda, direita): onde está o carro ao lado, em metros à frente (+) ou atrás (-) do meu; None = sem
    informação (iRacing só diz que há carro, não onde)."""
    if not snap.connected or snap.side_traffic is not None or snap.pose is None:
        return None, None
    best: list[Optional[float]] = [None, None]
    for c in snap.cars:
        if c.is_player or not c.in_session or c.status != CarStatus.RUNNING:
            continue
        rel = relative_xy(snap, c)
        if rel is None or not same_stretch(snap, c, SAME_STRETCH_M):
            continue
        lat, fwd = rel
        if abs(fwd) <= CAR_HALF_LEN_M and LANE_MIN_M <= abs(lat) <= LANE_MAX_M:
            i = 0 if lat > 0 else 1
            if best[i] is None or abs(fwd) < abs(best[i]):
                best[i] = fwd
    return best[0], best[1]


class SpotterTracker:
    """Mantém o último aviso por `HOLD_S` depois que o carro sai da zona."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last = [0.0, 0.0]  # instante em que cada lado esteve ocupado pela última vez
        self._count = [0, 0]
        self._off: list[Optional[float]] = [None, None]

    @property
    def offsets(self) -> tuple[Optional[float], Optional[float]]:
        """Posição (m à frente/atrás) do carro de cada lado, enquanto o aviso está aceso; None = desconhecida."""
        return (self._off[0] if self._count[0] else None, self._off[1] if self._count[1] else None)

    def update(self, snap: Snapshot) -> Optional[tuple[int, int]]:
        now = self._clock()
        cur = side_traffic(snap)
        if cur is not None:
            for i, o in enumerate(side_offsets(snap)):
                if o is not None:
                    self._off[i] = o
        if cur is None:
            self._count = [0, 0]
            self._last = [0.0, 0.0]
            return None
        out = []
        for i in (0, 1):
            if cur[i] > 0:
                self._last[i], self._count[i] = now, cur[i]
            elif now - self._last[i] > HOLD_S:
                self._count[i] = 0
            out.append(self._count[i])
        return out[0], out[1]
