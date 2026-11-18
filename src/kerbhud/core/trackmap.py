"""Track Map: traçado gravado por uma volta do piloto (sem Qt, testável).

O traçado NUNCA é genérico: é desenhado com as coordenadas reais do circuito carregado.
* LMU: coordenadas de mundo (x, z) de cada carro (`CarState.world_x/world_z`).
* iRacing: só o carro do piloto tem posição (GPS Lat/Lon). A primeira volta limpa grava o traçado; os outros carros
  são colocados nele pela posição percentual da volta (`lap_dist_pct`).
Depois de gravado, o traçado fica salvo em `<config>/tracks/<pista>.json` e volta pronto nas próximas sessões.
Convenção: norte para cima (y de tela = -z do mundo). Se algum simulador vier espelhado, há a opção "Espelhar".
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .model import CarState, CarStatus, Sim, Snapshot

BINS = 400  # pontos do traçado (um a cada 0,25% da volta)
COMPLETE_AT = 0.97  # fração da volta que precisa ter sido coberta
MIN_SPEED_MS = 3.0  # abaixo disso (boxes, rodada) não grava
MAX_CLOSURE = 0.10  # distância entre o fim e o começo, como fração do tamanho do circuito


def track_key(snap: Snapshot) -> Optional[str]:
    name = (snap.session.track_name or "").strip()
    if not name:
        return None
    length = f"-{round(snap.session.track_length_m)}" if snap.session.track_length_m else ""
    return re.sub(r"[^a-z0-9]+", "-", f"{snap.sim.value}-{name}{length}".lower()).strip("-")


@dataclass
class TrackShape:
    key: str
    name: str
    points: list[tuple[float, float]]  # BINS pontos; o ponto i está em pct = i / BINS

    def xy_at(self, pct: float) -> tuple[float, float]:
        n = len(self.points)
        f = (pct % 1.0) * n
        i = int(f) % n
        t = f - int(f)
        (x0, y0), (x1, y1) = self.points[i], self.points[(i + 1) % n]
        return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)

    def bounds(self) -> tuple[float, float, float, float]:
        xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def to_dict(self) -> dict:
        return {"version": 1, "key": self.key, "name": self.name,
                "points": [[round(x, 2), round(y, 2)] for x, y in self.points]}

    @staticmethod
    def from_dict(d: dict) -> "TrackShape":
        pts = [(float(x), float(y)) for x, y in d["points"]]
        if len(pts) < 50 or not all(math.isfinite(v) for p in pts for v in p):
            raise ValueError("traçado inválido")
        return TrackShape(str(d["key"]), str(d.get("name") or ""), pts)


class TrackStore:
    """Traçados gravados, um arquivo por pista."""

    def __init__(self, directory: Path):
        self.dir = Path(directory)

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def load(self, key: str) -> Optional[TrackShape]:
        try:
            return TrackShape.from_dict(json.loads(self._path(key).read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def save(self, shape: TrackShape) -> None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self._path(shape.key).with_suffix(".tmp")
            tmp.write_text(json.dumps(shape.to_dict()), encoding="utf-8")
            tmp.replace(self._path(shape.key))
        except OSError:
            pass  # sem permissão de escrita: o traçado vale só nesta sessão

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except OSError:
            pass


@dataclass
class TrackRecorder:
    store: Optional[TrackStore] = None
    shape: Optional[TrackShape] = None
    progress: float = 0.0
    _key: Optional[str] = None
    _sum: list = field(default_factory=lambda: [[0.0, 0.0, 0] for _ in range(BINS)])

    def reset(self, forget_saved: bool = False) -> None:
        if forget_saved and self.store and self._key:
            self.store.delete(self._key)
        self.shape, self.progress = None, 0.0
        self._sum = [[0.0, 0.0, 0] for _ in range(BINS)]
        if not forget_saved:
            self._key = None

    def update(self, snap: Snapshot) -> Optional[TrackShape]:
        key = track_key(snap) if snap.connected else None
        if key != self._key:
            self.reset()
            self._key = key
            if key and self.store:
                self.shape = self.store.load(key)
        if key is None or self.shape is not None:
            return self.shape
        me = snap.player()
        if me is None or me.world_x is None or me.world_z is None or me.lap_dist_pct is None:
            return None
        if me.status != CarStatus.RUNNING or not me.in_session:
            return None
        if snap.inputs is not None and snap.inputs.speed_ms < MIN_SPEED_MS:
            return None
        b = int((me.lap_dist_pct % 1.0) * BINS) % BINS
        acc = self._sum[b]
        acc[0] += me.world_x
        acc[1] += -me.world_z  # norte para cima
        acc[2] += 1
        filled = sum(1 for a in self._sum if a[2])
        self.progress = filled / BINS
        if self.progress >= COMPLETE_AT:
            self._finish(snap)
        return self.shape

    def _finish(self, snap: Snapshot) -> None:
        pts = self._interpolated()
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        size = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        known = [i for i, a in enumerate(self._sum) if a[2]]
        first, last = pts[known[0]], pts[known[-1]]  # medidos (o resto foi interpolado)
        if math.hypot(first[0] - last[0], first[1] - last[1]) > MAX_CLOSURE * size:
            self.reset()  # volta suja (rodada, atalho, teletransporte): descarta e grava de novo
            self._key = track_key(snap)
            return
        self.shape = TrackShape(self._key or "", snap.session.track_name or "", pts)
        if self.store:
            self.store.save(self.shape)

    def _interpolated(self) -> list[tuple[float, float]]:
        vals = [(a[0] / a[2], a[1] / a[2]) if a[2] else None for a in self._sum]
        known = [i for i, v in enumerate(vals) if v is not None]
        out: list[tuple[float, float]] = []
        for i in range(BINS):
            if vals[i] is not None:
                out.append(vals[i])  # type: ignore[arg-type]
                continue
            prev = max((k for k in known if k < i), default=known[-1])
            nxt = min((k for k in known if k > i), default=known[0])
            span = (nxt - prev) % BINS or BINS
            t = ((i - prev) % BINS) / span
            (x0, y0), (x1, y1) = vals[prev], vals[nxt]  # type: ignore[misc]
            out.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        return out


@dataclass
class MapCar:
    car: CarState
    x: float
    y: float
    on_track: bool  # False = nos boxes (desenhado apagado)


def map_cars(snap: Snapshot, shape: TrackShape) -> list[MapCar]:
    """Posição de cada carro NO traçado. Coordenadas reais quando o carro as tem; senão pela volta percentual."""
    out: list[MapCar] = []
    for c in snap.cars:
        if not c.in_session or c.status in (CarStatus.OUT, CarStatus.GARAGE, CarStatus.DISQUALIFIED):
            continue
        if c.world_x is not None and c.world_z is not None:
            x, y = c.world_x, -c.world_z
        elif c.lap_dist_pct is not None:
            x, y = shape.xy_at(c.lap_dist_pct)
        else:
            continue
        out.append(MapCar(c, x, y, c.status != CarStatus.PITS))
    return out
