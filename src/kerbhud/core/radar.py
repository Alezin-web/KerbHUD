"""Radar (vista de cima, centrada no meu carro) — sem Qt, testável.

* LMU: posição e orientação reais -> lateral e longitudinal em metros.
* iRacing: o simulador só dá a distância na volta (LapDistPct): a distância à frente/atrás é real; o lado só se sabe
  por `CarLeftRight`, então os carros colados (até `SIDE_PAIR_M`) são colocados ao lado indicado e os demais ficam
  no eixo central (`lateral_real = False`, e a interface avisa).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .model import CarState, CarStatus, Snapshot
from .spotter import relative_xy, same_stretch

DEFAULT_RANGE_M = 30.0
RANGE_CHOICES = (20.0, 30.0, 40.0, 60.0)
SIDE_PAIR_M = 8.0
LANE_OFFSET_M = 3.2


def get_range(options: dict) -> float:
    try:
        v = float(options.get("range_m", DEFAULT_RANGE_M))
    except (TypeError, ValueError):
        return DEFAULT_RANGE_M
    return v if v in RANGE_CHOICES else DEFAULT_RANGE_M


RED_M, YELLOW_M = 6.0, 14.0  # distância (m) para o carro ficar vermelho / amarelo
BEHIND_LANE_M = 4.5  # carro atrás dentro dessa faixa lateral conta como "vindo de trás"
MIN_CLOSING_MS = 0.5  # m/s de aproximação para contar como "se aproximando"
MAX_EXTRAP_S = 0.35  # quanto tempo se projeta o movimento entre duas atualizações do jogo


@dataclass
class RadarCar:
    car: CarState
    x: float  # metros para a DIREITA (negativo = esquerda)
    y: float  # metros À FRENTE (negativo = atrás)
    vx: float = 0.0  # velocidade relativa no quadro do radar (m/s)
    vy: float = 0.0

    @property
    def distance(self) -> float:
        return math.hypot(self.x, self.y)

    @property
    def closing(self) -> float:
        """m/s em que a distância diminui (positivo = se aproximando)."""
        d = self.distance
        return 0.0 if d < 1e-6 else -(self.x * self.vx + self.y * self.vy) / d


def proximity(rc: RadarCar) -> int:
    """0 = longe, 1 = atenção (amarelo), 2 = perigo (vermelho), pela distância."""
    d = rc.distance
    return 2 if d <= RED_M else (1 if d <= YELLOW_M else 0)


def approaching_from_behind(rc: RadarCar) -> bool:
    """Carro atrás, na minha faixa, chegando mais perto (ou já muito colado): vira a linha de alerta."""
    if rc.y >= -1.0 or abs(rc.x) > BEHIND_LANE_M or proximity(rc) == 0:
        return False
    return rc.closing >= MIN_CLOSING_MS or proximity(rc) == 2


SHOW_M_CORE = 22.0  # o módulo Radar aparece quando há carro a até essa distância (ui/radar_module.py)
SIDE_LONG_M = 5.5   # carro ao lado: no máximo essa distância à frente/atrás...
SIDE_LAT_MIN_M, SIDE_LAT_MAX_M = 1.0, 5.5  # ...e nessa faixa lateral
SIDE_RED_M = 2.4    # lateral abaixo disso = quase encostando (vermelho)
MAX_STRIP_SLOPE = 0.35  # inclinação máxima da faixa de aproximação (dx por dy)


def side_levels(cars: list[RadarCar]) -> dict[str, int]:
    """Alerta de carro AO LADO, por lado: 0 = livre, 1 = amarelo (emparelhado), 2 = vermelho (quase encostando)."""
    out = {"left": 0, "right": 0}
    for rc in cars:
        ax = abs(rc.x)
        if abs(rc.y) > SIDE_LONG_M or not (SIDE_LAT_MIN_M <= ax <= SIDE_LAT_MAX_M):
            continue
        side = "left" if rc.x < 0 else "right"
        out[side] = max(out[side], 2 if ax < SIDE_RED_M else 1)
    return out


def strip_slope(rc: RadarCar) -> float:
    """Inclinação (dx por dy) da faixa de aproximação: segue a direção em que o carro anda em relação a mim."""
    if abs(rc.vy) < 0.5:
        return 0.0
    return max(-MAX_STRIP_SLOPE, min(MAX_STRIP_SLOPE, rc.vx / rc.vy))


@dataclass
class RadarView:
    cars: list[RadarCar] = field(default_factory=list)
    lateral_real: bool = True
    available: bool = False
    message: str = ""


def radar_view(snap: Optional[Snapshot], range_m: float = DEFAULT_RANGE_M) -> RadarView:
    if snap is None or not snap.connected:
        return RadarView(message="Aguardando dados")
    me = snap.player()
    if me is None:
        return RadarView(message="Sem seu carro")
    in_pits = me.status == CarStatus.PITS
    others = [c for c in snap.cars if not c.is_player and c.in_session
              and c.status not in (CarStatus.OUT, CarStatus.GARAGE, CarStatus.DISQUALIFIED)
              and (in_pits or c.status != CarStatus.PITS)]  # carros nos boxes só aparecem se eu também estou
    view = RadarView(available=True)
    if snap.pose is not None and me.world_x is not None:
        for c in others:
            rel = relative_xy(snap, c)
            if rel is None or not same_stretch(snap, c, max(25.0, range_m * 1.5)):
                continue  # sem posição, ou em outro trecho da pista (paralelo/fora da pista)
            lat, fwd = rel
            if math.hypot(lat, fwd) <= range_m:  # círculo, como o desenho
                view.cars.append(RadarCar(c, -lat, fwd))
        return view
    track = snap.session.track_length_m
    if not track or me.lap_dist_pct is None:
        return RadarView(message="Sem dados de posição para o radar")
    view.lateral_real = False
    cand: list[tuple[float, CarState]] = []
    for c in others:
        if c.lap_dist_pct is None:
            continue
        d = ((c.lap_dist_pct - me.lap_dist_pct + 0.5) % 1.0 - 0.5) * track  # + = à frente
        if abs(d) <= range_m:
            cand.append((d, c))
    left_n, right_n = snap.side_traffic or (0, 0)
    near = sorted((t for t in cand if abs(t[0]) <= SIDE_PAIR_M), key=lambda t: abs(t[0]))
    lateral: dict[int, float] = {}
    for _d, c in near[:left_n]:
        lateral[c.idx] = -LANE_OFFSET_M
    for _d, c in [t for t in near if t[1].idx not in lateral][:right_n]:
        lateral[c.idx] = LANE_OFFSET_M
    view.cars = [RadarCar(c, lateral.get(c.idx, 0.0), d) for d, c in cand]
    return view


class RadarSmoother:
    """Deixa o radar fluido: o jogo atualiza a posição dos outros carros poucas vezes por segundo (LMU: ~5 a 10 Hz),
    então estima a velocidade de cada carro e projeta o movimento entre as atualizações, suavizando o desenho."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._st: dict[int, dict] = {}
        self._view = RadarView()
        self._t_frame: Optional[float] = None

    def update(self, view: RadarView) -> None:
        now = self._clock()
        self._view = view
        seen = set()
        for rc in view.cars:
            i = rc.car.idx
            seen.add(i)
            st = self._st.get(i)
            if st is None or math.hypot(rc.x - st["tx"], rc.y - st["ty"]) > 60.0:  # novo (ou teleporte)
                self._st[i] = {"tx": rc.x, "ty": rc.y, "t": now, "vx": 0.0, "vy": 0.0, "dx": rc.x, "dy": rc.y}
                continue
            if abs(rc.x - st["tx"]) > 0.02 or abs(rc.y - st["ty"]) > 0.02:  # o jogo atualizou de verdade
                dt = now - st["t"]
                if 0.01 <= dt <= 1.0:
                    st["vx"] += ((rc.x - st["tx"]) / dt - st["vx"]) * 0.5
                    st["vy"] += ((rc.y - st["ty"]) / dt - st["vy"]) * 0.5
                st["tx"], st["ty"], st["t"] = rc.x, rc.y, now
        for i in [k for k in self._st if k not in seen]:
            del self._st[i]

    def frame(self) -> RadarView:
        """Posições suavizadas para desenhar AGORA (chamar a cada repintura)."""
        now = self._clock()
        dt = 0.0 if self._t_frame is None else max(0.0, min(0.25, now - self._t_frame))
        self._t_frame = now
        k = 1.0 - math.exp(-dt * 22.0)
        out = []
        for rc in self._view.cars:
            st = self._st.get(rc.car.idx)
            if st is None:
                out.append(rc)
                continue
            ahead = min(MAX_EXTRAP_S, max(0.0, now - st["t"]))
            px, py = st["tx"] + st["vx"] * ahead, st["ty"] + st["vy"] * ahead
            st["dx"] += (px - st["dx"]) * k
            st["dy"] += (py - st["dy"]) * k
            out.append(RadarCar(rc.car, st["dx"], st["dy"], st["vx"], st["vy"]))
        return RadarView(out, self._view.lateral_real, self._view.available, self._view.message)
