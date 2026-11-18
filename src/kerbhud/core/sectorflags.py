"""Amarela de setor do LMU: só conta o que MUDA em relação ao normal (sem Qt, testável).

Os valores de `mSectorFlag` do LMU não são documentados e o painel ficava sempre amarelo quando qualquer valor diferente de
zero contava. Aqui cada setor aprende o seu valor de repouso (o mais frequente) e só uma MUDANÇA desse valor, mantida por
`HOLD_S`, vira "amarela no setor". Assim funciona seja qual for o número que o jogo usa para "sem bandeira".
"""
from __future__ import annotations

import time
from collections import Counter
from typing import Callable, Optional, Sequence

MIN_BASE_SAMPLES = 60  # leituras antes de confiar no valor de repouso
HOLD_S = 0.4           # a mudança precisa durar isso para valer (evita tremida)


class SectorFlagWatch:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._seen: list[Counter] = []
        self._since: list[Optional[float]] = []

    def reset(self) -> None:
        self._seen, self._since = [], []

    def baseline(self, i: int) -> Optional[int]:
        if i >= len(self._seen) or sum(self._seen[i].values()) < MIN_BASE_SAMPLES:
            return None
        return self._seen[i].most_common(1)[0][0]

    def update(self, values: Sequence[int]) -> bool:
        """True se algum setor está com o valor diferente do repouso há pelo menos `HOLD_S`."""
        now = self._clock()
        while len(self._seen) < len(values):
            self._seen.append(Counter())
            self._since.append(None)
        yellow = False
        for i, v in enumerate(values):
            base = self.baseline(i)
            if base is not None and v != base:
                if self._since[i] is None:
                    self._since[i] = now
                if now - self._since[i] >= HOLD_S:
                    yellow = True
            else:
                self._since[i] = None
                self._seen[i][v] += 1  # só o repouso alimenta a estatística (a amarela não vira o novo normal)
        return yellow
