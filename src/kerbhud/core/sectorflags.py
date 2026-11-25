"""Amarela de setor do LMU: só conta o que MUDA em relação ao normal (sem Qt, testável).

Os valores de `mSectorFlag` do LMU não são documentados e o painel ficava sempre amarelo quando qualquer valor diferente de
zero contava. Aqui cada setor usa como "normal" o valor mais frequente dos últimos `WINDOW_S` segundos, e só uma MUDANÇA
dele, mantida por `HOLD_S`, vira "amarela no setor". Dois cuidados para não ficar preso em amarelo:
* o normal é recalculado continuamente (se o jogo passa a usar outro valor de repouso, por exemplo ao entrar na pista, o
  KerbHUD se adapta em vez de manter o antigo para sempre);
* se TODOS os setores mudam juntos não é amarela de setor (é um estado geral do jogo; a amarela geral vem da fase da sessão).
"""
from __future__ import annotations

import time
from collections import Counter, deque
from typing import Callable, Deque, Optional, Sequence

MIN_BASE_SAMPLES = 60  # leituras antes de confiar no valor de repouso
HOLD_S = 0.4           # a mudança precisa durar isso para valer (evita tremida)
WINDOW_S = 120.0       # janela em que o valor de repouso é escolhido
SAMPLE_EVERY_S = 0.1   # guarda no máximo 10 leituras por segundo (memória limitada)


class SectorFlagWatch:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._hist: Deque[tuple[float, tuple[int, ...]]] = deque()
        self._count: list[Counter] = []
        self._since: list[Optional[float]] = []
        self._last_store = -1e9

    def baseline(self, i: int) -> Optional[int]:
        if i >= len(self._count) or sum(self._count[i].values()) < MIN_BASE_SAMPLES:
            return None
        return self._count[i].most_common(1)[0][0]

    def _store(self, now: float, values: tuple[int, ...]) -> None:
        if now - self._last_store < SAMPLE_EVERY_S - 1e-6:
            return
        self._last_store = now
        while len(self._count) < len(values):
            self._count.append(Counter())
            self._since.append(None)
        self._hist.append((now, values))
        for i, v in enumerate(values):
            self._count[i][v] += 1
        while self._hist and now - self._hist[0][0] > WINDOW_S:
            _t, old = self._hist.popleft()
            for i, v in enumerate(old):
                self._count[i][v] -= 1
                if self._count[i][v] <= 0:
                    del self._count[i][v]

    def update(self, values: Sequence[int]) -> bool:
        """True se algum setor está com o valor diferente do normal há pelo menos `HOLD_S`."""
        now = self._clock()
        vals = tuple(int(v) for v in values)
        while len(self._count) < len(vals):
            self._count.append(Counter())
            self._since.append(None)
        bases = [self.baseline(i) for i in range(len(vals))]
        differs = [b is not None and v != b for v, b in zip(vals, bases)]
        if len(vals) > 1 and all(differs):  # todos mudaram juntos: estado geral, não amarela de setor
            differs = [False] * len(vals)
        yellow = False
        for i, d in enumerate(differs):
            if d:
                if self._since[i] is None:
                    self._since[i] = now
                if now - self._since[i] >= HOLD_S:
                    yellow = True
            else:
                self._since[i] = None
        self._store(now, vals)
        return yellow


class FinishWatch:
    """Bandeira de chegada mostrada por `SHOW_S` segundos depois que o piloto termina (o estado "terminou" dura até a sessão acabar)."""
    SHOW_S = 25.0

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._t0: Optional[float] = None
        self._was = False

    def update(self, finished: bool) -> None:
        if finished and not self._was:
            self._t0 = self._clock()
        if not finished:
            self._t0 = None
        self._was = finished

    @property
    def visible(self) -> bool:
        return self._t0 is not None and self._clock() - self._t0 <= self.SHOW_S
