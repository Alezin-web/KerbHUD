"""Contador de incidentes do piloto para simuladores que não publicam o número (Le Mans Ultimate).

Tudo é DERIVADO da telemetria do próprio carro (nada vem do jogo como "incidente"):
* **batida**: o instante da última batida mudou e a intensidade passou de `IMPACT_MIN` (VERIFICAR o valor no jogo);
* **fora da pista**: as 4 rodas passam a estar sobre grama/terra/brita (zebra e asfalto não contam).
"""
from __future__ import annotations

from typing import Optional

from .model import CAP_CONTACT, Snapshot

IMPACT_MIN = 150.0  # intensidade mínima de uma batida para contar (unidade do jogo; ajustar depois de testar)
OFF_WHEELS = 4  # rodas fora do asfalto para contar uma saída de pista


class IncidentCounter:
    def __init__(self) -> None:
        self.hits = 0
        self.offs = 0
        self._sig: Optional[tuple] = None
        self._impact_et: Optional[float] = None
        self._off = False

    def reset(self) -> None:
        self.hits = self.offs = 0
        self._impact_et = None
        self._off = False

    @property
    def available(self) -> bool:
        return self._sig is not None

    def update(self, snap: Snapshot) -> None:
        c = snap.contact
        if not snap.connected or c is None or not snap.has(CAP_CONTACT):
            self._sig = None
            return
        sig = (snap.sim, snap.session.track_name, snap.session.session_type)
        if sig != self._sig:
            self.reset()  # sessão nova: zera
            self._sig = sig
        if c.impact_et is not None:
            if self._impact_et is not None and c.impact_et < self._impact_et:
                self.reset()  # o relógio voltou (sessão reiniciada)
                self._sig = sig
            if self._impact_et is None:
                self._impact_et = c.impact_et  # 1ª leitura: batida antiga, só marca o ponto de partida
            elif c.impact_et != self._impact_et:
                self._impact_et = c.impact_et
                if (c.impact_mag or 0.0) >= IMPACT_MIN:
                    self.hits += 1
        if c.wheels_off is not None:
            off = c.wheels_off >= OFF_WHEELS
            if off and not self._off:
                self.offs += 1
            self._off = off
