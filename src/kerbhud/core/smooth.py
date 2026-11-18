"""Suavização de posições para o desenho ficar fluido (sem Qt, testável).

O LMU atualiza a posição dos carros poucas vezes por segundo (cerca de 5 a 10 Hz). Entre duas atualizações,
estima-se a velocidade de cada ponto e projeta-se o movimento por até `MAX_EXTRAP_S`, com suavização exponencial.
"""
from __future__ import annotations

import math
import time
from typing import Callable, Hashable, Optional

MAX_EXTRAP_S = 0.35
SMOOTH_RATE = 22.0  # 1/s: quanto mais alto, mais "colado" na posição alvo


class PointSmoother:
    def __init__(self, clock: Callable[[], float] = time.monotonic, jump_m: float = 80.0) -> None:
        self._clock = clock
        self._jump = jump_m  # salto maior que isso = teleporte (sem suavizar)
        self._st: dict[Hashable, dict] = {}
        self._t_frame: Optional[float] = None

    def reset(self) -> None:
        self._st.clear()
        self._t_frame = None

    def update(self, points: dict[Hashable, tuple[float, float]]) -> None:
        """Entrega as posições do último snapshot: {chave: (x, y)}."""
        now = self._clock()
        for k, (x, y) in points.items():
            st = self._st.get(k)
            if st is None or math.hypot(x - st["tx"], y - st["ty"]) > self._jump:
                self._st[k] = {"tx": x, "ty": y, "t": now, "vx": 0.0, "vy": 0.0, "dx": x, "dy": y}
                continue
            if abs(x - st["tx"]) > 0.02 or abs(y - st["ty"]) > 0.02:  # o jogo atualizou de verdade
                dt = now - st["t"]
                if 0.01 <= dt <= 1.0:
                    st["vx"] += ((x - st["tx"]) / dt - st["vx"]) * 0.5
                    st["vy"] += ((y - st["ty"]) / dt - st["vy"]) * 0.5
                st["tx"], st["ty"], st["t"] = x, y, now
        for k in [k for k in self._st if k not in points]:
            del self._st[k]

    def frame(self) -> dict[Hashable, tuple[float, float]]:
        """Posições suavizadas para desenhar AGORA (chamar a cada repintura)."""
        now = self._clock()
        dt = 0.0 if self._t_frame is None else max(0.0, min(0.25, now - self._t_frame))
        self._t_frame = now
        k = 1.0 - math.exp(-dt * SMOOTH_RATE)
        out = {}
        for key, st in self._st.items():
            ahead = min(MAX_EXTRAP_S, max(0.0, now - st["t"]))
            px, py = st["tx"] + st["vx"] * ahead, st["ty"] + st["vy"] * ahead
            st["dx"] += (px - st["dx"]) * k
            st["dy"] += (py - st["dy"]) * k
            out[key] = (st["dx"], st["dy"])
        return out
