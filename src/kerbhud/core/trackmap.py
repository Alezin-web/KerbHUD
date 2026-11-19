"""Track Map: traçado gravado por uma volta do piloto (sem Qt, testável).

O traçado NUNCA é genérico: é desenhado com as coordenadas reais do circuito carregado.
* LMU: coordenadas de mundo (x, z) de cada carro (`CarState.world_x/world_z`).
* iRacing: só o carro do piloto tem posição, e ela é ESTIMADA (velocidade x rumo, `core/deadreckon.py`; o jogo normal não
  publica Lat/Lon). Uma volta limpa de uma linha de largada à próxima grava o traçado e a deriva é distribuída pela volta.
  Os outros carros são colocados nele pela posição percentual da volta (`lap_dist_pct`).
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

from .model import CAP_PLAYER_XY_ESTIMATED, CarState, CarStatus, Snapshot

BINS = 400  # pontos do traçado (um a cada 0,25% da volta)
COMPLETE_AT = 0.97  # fração da volta que precisa ter sido coberta
MAX_HOLE_BINS = 12  # volta estimada: maior trecho sem amostra aceito (3% da volta)
MIN_TRACK = 0.80  # o box só tapa buracos: pelo menos isto da volta tem que ter sido gravado na pista de verdade
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
    discards: int = 0  # voltas gravadas e descartadas por não fecharem (para o módulo avisar, em vez de ficar mudo)
    _key: Optional[str] = None
    _sum: list = field(default_factory=lambda: [[0.0, 0.0, 0] for _ in range(BINS)])
    _pit: list = field(default_factory=lambda: [[0.0, 0.0, 0] for _ in range(BINS)])  # box em movimento: só tapa buracos
    _lap: Optional[list] = None  # posição estimada: amostras (pct, x, z) da volta em curso, a partir da linha de largada
    _last_pct: Optional[float] = None

    def reset(self, forget_saved: bool = False) -> None:
        if forget_saved and self.store and self._key:
            self.store.delete(self._key)
        self.shape, self.progress = None, 0.0
        self._sum = [[0.0, 0.0, 0] for _ in range(BINS)]
        self._pit = [[0.0, 0.0, 0] for _ in range(BINS)]
        self._lap, self._last_pct = None, None
        self.discards = 0
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
        if me.status not in (CarStatus.RUNNING, CarStatus.PITS) or not me.in_session:
            return None
        if CAP_PLAYER_XY_ESTIMATED in snap.capabilities:
            return self._update_estimated(snap, me)
        if snap.inputs is not None and snap.inputs.speed_ms < MIN_SPEED_MS:
            return None
        b = int((me.lap_dist_pct % 1.0) * BINS) % BINS
        acc = self._pit[b] if me.status == CarStatus.PITS else self._sum[b]  # box: só serve para tapar buracos
        acc[0] += me.world_x
        acc[1] += -me.world_z  # norte para cima
        acc[2] += 1
        on_track = sum(1 for a in self._sum if a[2]) / BINS  # só a pista de verdade; o box nunca basta sozinho
        union = sum(1 for a, q in zip(self._sum, self._pit) if a[2] or q[2]) / BINS
        self.progress = on_track if on_track < MIN_TRACK else union
        if on_track >= MIN_TRACK and union >= COMPLETE_AT:
            self._finish(snap)
        return self.shape

    # ---- posição estimada (iRacing) ------------------------------------- #
    def _update_estimated(self, snap: Snapshot, me: CarState) -> Optional[TrackShape]:
        """Grava UMA volta limpa, da linha de largada até a próxima. A posição estimada acumula erro, então só vale
        relativa ao começo da volta; o erro final é distribuído linearmente pela volta (fecha o circuito)."""
        pct = me.lap_dist_pct % 1.0  # type: ignore[operator]
        ok = (me.status == CarStatus.RUNNING and me.in_session and snap.driving is not False
              and (snap.inputs is None or snap.inputs.speed_ms >= MIN_SPEED_MS))
        last, self._last_pct = self._last_pct, (pct if ok else None)
        if not ok:
            self._lap = None  # box, parado, replay: a volta em curso não vale
            self.progress = 0.0
            return None
        crossed = last is not None and last > 0.9 and pct < 0.1
        if last is not None and not crossed and not (-0.002 <= pct - last <= 0.03):
            self._lap = None  # voltou, teletransportou ou deu um salto na volta: descarta
        if crossed:
            if self._lap is not None:
                self._close_estimated_lap(snap, pct, me.world_x, me.world_z)
                if self.shape is not None:
                    return self.shape
            self._lap = []
        if self._lap is not None:
            self._lap.append((pct, me.world_x, me.world_z))
            if self._lap:
                self.progress = min(1.0, (pct - self._lap[0][0]) % 1.0)
        else:
            self.progress = 0.0
        return self.shape

    @staticmethod
    def _longest_hole(filled: set) -> int:
        """Maior sequência de trechos SEM amostra na volta (circular). Buracos pequenos entre amostras vizinhas são
        interpolados sem inventar nada (o carro andou continuamente); um buraco grande não."""
        if not filled:
            return BINS
        ordered = sorted(filled)
        gaps = [(b - a - 1) for a, b in zip(ordered, ordered[1:])] + [ordered[0] + BINS - ordered[-1] - 1]
        return max(gaps)

    def _close_estimated_lap(self, snap: Snapshot, end_pct: float, end_x: float, end_z: float) -> None:
        lap, self._lap = self._lap or [], None
        key = self._key
        p0, x0, z0 = lap[0] if lap else (0.0, 0.0, 0.0)
        span = (1.0 + end_pct) - p0
        ex, ez = end_x - x0, end_z - z0  # quanto o fim ficou longe do começo: é a deriva da volta
        filled = {int(p * BINS) % BINS for p, _x, _z in lap}
        track_len = snap.session.track_length_m or 0.0
        if len(lap) < 2 or span <= 0.5 or self._longest_hole(filled) > MAX_HOLE_BINS or (
                track_len and math.hypot(ex, ez) > MAX_CLOSURE * 2 * track_len):
            self.discards += 1  # volta curta, com buraco grande ou com deriva demais para confiar
            return
        self._sum = [[0.0, 0.0, 0] for _ in range(BINS)]
        for p, x, z in lap:
            f = ((p - p0) % 1.0) / span  # fração da volta (0 no começo, ~1 no fim)
            acc = self._sum[int(p * BINS) % BINS]
            acc[0] += (x - x0) - ex * f
            acc[1] += -((z - z0) - ez * f)  # norte para cima
            acc[2] += 1
        pts = self._interpolated()
        self._pit = [[0.0, 0.0, 0] for _ in range(BINS)]
        self.shape = TrackShape(key or "", snap.session.track_name or "", pts)
        if self.store:
            self.store.save(self.shape)

    def _finish(self, snap: Snapshot) -> None:
        pts = self._interpolated()
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        size = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        covered = [bool(a[2] or q[2]) for a, q in zip(self._sum, self._pit)]
        known = [i for i, c in enumerate(covered) if c]
        first, last = pts[known[0]], pts[known[-1]]  # medidos (o resto foi interpolado)
        # o buraco entre o fim e o começo da volta (ex.: box na reta de largada) pode ser longo: dá folga proporcional a ele
        gap_bins = known[0] + BINS - known[-1] - 1
        perimeter = sum(math.hypot(pts[i][0] - pts[(i + 1) % BINS][0], pts[i][1] - pts[(i + 1) % BINS][1]) for i in range(BINS))
        allowed = MAX_CLOSURE * size + 1.5 * gap_bins / BINS * perimeter
        if math.hypot(first[0] - last[0], first[1] - last[1]) > allowed:
            discards = self.discards + 1
            self.reset()  # volta suja (rodada, atalho, teletransporte): descarta e grava de novo
            self._key = track_key(snap)
            self.discards = discards
            return
        self.shape = TrackShape(self._key or "", snap.session.track_name or "", pts)
        if self.store:
            self.store.save(self.shape)

    def _interpolated(self) -> list[tuple[float, float]]:
        vals = []
        for a, q in zip(self._sum, self._pit):
            src = a if a[2] else q  # a pista tem prioridade; o box só entra onde faltou dado
            vals.append((src[0] / src[2], src[1] / src[2]) if src[2] else None)
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
        if c.world_x is not None and c.world_z is not None and CAP_PLAYER_XY_ESTIMATED not in snap.capabilities:
            x, y = c.world_x, -c.world_z  # (estimada: fica fora do traçado, então todos os carros vão pela volta percentual)
        elif c.lap_dist_pct is not None:
            x, y = shape.xy_at(c.lap_dist_pct)
        else:
            continue
        out.append(MapCar(c, x, y, c.status != CarStatus.PITS))
    return out
