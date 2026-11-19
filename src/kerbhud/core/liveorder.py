"""Posição AO VIVO na corrida do iRacing (sem Qt, testável).

O iRacing só atualiza a posição oficial (`CarIdxPosition`) quando o carro cruza a linha de chegada, então Standings e
Relative "pulavam" de volta em volta. Dentro de uma corrida a ordem real é simples: quem tem mais voltas completas
mais a fração da volta atual está na frente. Esta classe calcula essa ordem a cada leitura.

Só vale para CORRIDA. No treino e na classificação a ordem é pela melhor volta, que só muda quando alguém completa
uma volta (então não há "tempo real" a mostrar).

Um filtro de 2 leituras iguais evita que a ordem pisque na linha de chegada, onde o contador de voltas e a fração da
volta podem se atualizar com um instante de diferença.
"""
from __future__ import annotations

from typing import Optional, Sequence

from .model import CarState, CarStatus

CONFIRM_READS = 2


def progress(c: CarState) -> Optional[float]:
    """Voltas completas + fração da volta atual, ou None se o carro não está no mundo/sem dados."""
    if c.lap_dist_pct is None or c.laps_completed is None or c.status in (CarStatus.OUT, CarStatus.GARAGE, CarStatus.DISQUALIFIED):
        return None
    return float(c.laps_completed) + float(c.lap_dist_pct)


class LiveOrder:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._order: list[int] = []
        self._cand: list[int] = []
        self._n = 0

    def order(self, cars: Sequence[CarState]) -> list[int]:
        """Índices dos carros (CarState.idx) do primeiro ao último, só os que têm dados de volta."""
        ranked = sorted(((progress(c), c.idx) for c in cars if progress(c) is not None), key=lambda t: (-t[0], t[1]))
        cand = [idx for _p, idx in ranked]
        if not self._order or set(cand) != set(self._order):
            self._order, self._cand, self._n = cand, cand, CONFIRM_READS  # elenco mudou (entrou/saiu carro): aceita direto
        elif cand == self._cand:
            self._n += 1
        else:
            self._cand, self._n = cand, 1
        if self._n >= CONFIRM_READS:
            self._order = self._cand
        return list(self._order)

    def apply(self, cars: Sequence[CarState]) -> bool:
        """Reescreve `position` e `class_position` dos carros com a ordem ao vivo. False se não deu para calcular."""
        order = self.order(cars)
        if len(order) < 2:
            return False
        by_idx = {c.idx: c for c in cars}
        per_class: dict[Optional[str], int] = {}
        for pos, idx in enumerate(order, start=1):
            c = by_idx[idx]
            per_class[c.class_name] = per_class.get(c.class_name, 0) + 1
            c.position, c.class_position = pos, per_class[c.class_name]
        return True
