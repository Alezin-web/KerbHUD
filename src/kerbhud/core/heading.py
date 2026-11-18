"""Direção do meu carro a partir do MOVIMENTO (sem Qt, testável).

A orientação que o LMU entrega (`mOri`) é difícil de interpretar sem conferir no jogo; o rumo real do carro é
simplesmente para onde ele está andando. Por isso o radar e o spotter do LMU usam o deslocamento do carro quando ele
está em movimento e só caem para o `mOri` quando está parado.
"""
from __future__ import annotations

import math
import time
from collections import deque
from typing import Callable, Optional

MIN_MOVE_M = 1.5    # deslocamento mínimo para confiar na direção
MIN_WINDOW_S = 0.15  # janela mínima entre as amostras comparadas
MAX_WINDOW_S = 0.6   # amostras mais velhas que isso são descartadas (janela curta: acompanha as curvas)


class MotionHeading:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hist: deque[tuple[float, float, float]] = deque()
        self._last: Optional[tuple[float, float]] = None
        self.moving = False  # True se, na última atualização, o carro andou o suficiente para confiar na direção

    def reset(self) -> None:
        self._hist.clear()
        self._last = None
        self.moving = False

    def update(self, x: float, z: float) -> Optional[tuple[float, float]]:
        """Registra a posição do meu carro e devolve o vetor unitário (x, z) da frente, ou None se nunca andou."""
        now = self._clock()
        if not self._hist or (x, z) != self._hist[-1][1:]:
            self._hist.append((now, x, z))
        while self._hist and now - self._hist[0][0] > MAX_WINDOW_S:
            self._hist.popleft()
        self.moving = False
        for t0, x0, z0 in self._hist:  # a amostra mais antiga dentro da janela
            if now - t0 < MIN_WINDOW_S:
                break
            dx, dz = x - x0, z - z0
            d = math.hypot(dx, dz)
            if d >= MIN_MOVE_M and math.isfinite(d):
                self._last = (dx / d, dz / d)
                self.moving = True
            break
        return self._last


def _unit(x: float, z: float) -> Optional[tuple[float, float]]:
    n = math.hypot(x, z)
    return (x / n, z / n) if n > 1e-6 and math.isfinite(n) else None


class OriCalibrator:
    """Descobre qual leitura da orientação do jogo (`mOri`) é a FRENTE do carro, comparando com o movimento.

    Testa as interpretações possíveis (linhas e colunas da matriz, nos dois sentidos) e mantém a média de quanto cada
    uma concorda com a direção em que o carro anda. Com o carro parado, a frente vem da que mais concorda (se for
    confiável), em vez de uma suposição fixa."""

    MIN_SAMPLES = 40  # só confia depois de MUITAS leituras andando de verdade (e com curvas)
    MIN_SCORE = 0.95
    ALPHA = 0.05

    def __init__(self) -> None:
        self.score: dict[str, float] = {}
        self.n = 0

    @staticmethod
    def candidates(ori) -> dict[str, tuple[float, float]]:
        """`ori`: três linhas (x, y, z). Devolve {nome: vetor unitário (x, z)}."""
        (r0x, _y0, r0z), (_x1, _y1, _z1), (r2x, _y2, r2z) = ori[0], ori[1], ori[2]
        base = {"linha0": (r0x, r0z), "linha2": (r2x, r2z), "coluna_x": (r0x, r2x), "coluna_z": (r0z, r2z)}
        out = {}
        for name, (x, z) in base.items():
            u = _unit(x, z)
            if u:
                out[name] = u
                out["-" + name] = (-u[0], -u[1])
        return out

    def observe(self, ori, motion: Optional[tuple[float, float]]) -> None:
        """Chamar com o carro andando (`motion` = direção do deslocamento)."""
        if motion is None:
            return
        self.n += 1
        for name, u in self.candidates(ori).items():
            dot = u[0] * motion[0] + u[1] * motion[1]
            self.score[name] = self.score.get(name, dot) + (dot - self.score.get(name, dot)) * self.ALPHA

    def best(self) -> Optional[tuple[str, float]]:
        if self.n < self.MIN_SAMPLES or not self.score:
            return None
        name = max(self.score, key=self.score.get)
        return (name, self.score[name]) if self.score[name] >= self.MIN_SCORE else None

    def top(self, k: int = 3) -> list[tuple[str, float]]:
        """As `k` leituras que mais concordam com o movimento (para o diagnóstico)."""
        return sorted(self.score.items(), key=lambda kv: -kv[1])[:k]

    def forward(self, ori) -> Optional[tuple[float, float]]:
        b = self.best()
        return self.candidates(ori).get(b[0]) if b else None


class TurnSense:
    """Descobre de que lado fica a ESQUERDA do carro no mapa, comparando o giro da direção (rumo pelo movimento) com o
    volante (negativo = esquerda). Não depende de nenhuma suposição sobre `mOri` nem sobre o sentido dos eixos."""

    MIN_SPEED_MS = 8.0
    MIN_EVIDENCE = 0.6  # rad x volante acumulados

    def __init__(self) -> None:
        self._prev: Optional[tuple[float, float]] = None
        self.evidence = 0.0

    def observe(self, fwd: Optional[tuple[float, float]], steering: float, speed_ms: float) -> None:
        if fwd is None or speed_ms < self.MIN_SPEED_MS:
            self._prev = None
            return
        if self._prev is not None:
            cross = self._prev[0] * fwd[1] - self._prev[1] * fwd[0]
            dot = self._prev[0] * fwd[0] + self._prev[1] * fwd[1]
            self.evidence += steering * math.atan2(cross, dot)
        self._prev = fwd

    def left_of(self, fwd: tuple[float, float]) -> Optional[tuple[float, float]]:
        """Vetor da esquerda para o rumo `fwd`, ou None se ainda não há evidência."""
        if abs(self.evidence) < self.MIN_EVIDENCE:
            return None
        # volante à direita girando o rumo no sentido +: a esquerda é (fz, -fx); no outro sentido, (-fz, fx)
        return (fwd[1], -fwd[0]) if self.evidence > 0 else (-fwd[1], fwd[0])
