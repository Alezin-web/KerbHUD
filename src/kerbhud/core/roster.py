"""Memória de quem já esteve na sessão (sem Qt, testável).

Quando um piloto sai da sessão (ou todos saem ao fim da corrida), o simulador simplesmente para de listá-lo e a
classificação ficaria incompleta ou vazia. O `Roster` lembra os carros vistos e devolve os ausentes como
"fantasmas": mesmos dados da última vez em que foram vistos, `in_session = False` e `status = OUT`, no fim da lista.
Os módulos mostram esses pilotos apagados, em vez de removê-los.

A memória vale por sessão: reinicia quando começa uma sessão NOVA (outra pista ou outro tipo) ou quando o simulador
desconecta. Ao fim de uma sessão (o jogo para de publicá-la) a última classificação continua disponível, apagada,
até uma nova sessão começar.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Optional

from .model import CarState, CarStatus, Sim, Snapshot

GHOST_IDX_BASE = 1000  # idx dos fantasmas: não colide com os índices de carros ao vivo


class Roster:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._sig: Optional[tuple] = None
        self._seen: dict[tuple, CarState] = {}
        self._session = None
        self._ghost_idx: dict[tuple, int] = {}

    @staticmethod
    def _key(c: CarState) -> tuple:
        # `idx` não é estável (no LMU os índices deslizam quando alguém sai): usamos nome + número do carro
        return ((c.driver_name or "").strip().lower() or f"#{c.idx}", c.car_number or "")

    def update(self, snap: Snapshot) -> Snapshot:
        if not snap.connected or snap.sim == Sim.NONE:
            self.reset()
            return snap
        if snap.session.active:
            sig = (snap.sim, snap.session.track_name, snap.session.session_type)
            if sig != self._sig:  # sessão nova: esquece a anterior
                self.reset()
                self._sig = sig
            self._session = snap.session
        live = {self._key(c): c for c in snap.cars if c.in_session}
        self._seen.update(live)
        gone = [(k, c) for k, c in self._seen.items() if k not in live]
        session = snap.session if snap.session.active or self._session is None else self._session
        if not gone:
            return snap if session is snap.session else replace(snap, session=session)

        live_pos = max((c.position or 0 for c in snap.cars), default=0)
        class_pos: dict[Optional[str], int] = {}
        for c in snap.cars:
            class_pos[c.class_name] = max(class_pos.get(c.class_name, 0), c.class_position or 0)
        gone.sort(key=lambda kc: (-(kc[1].laps_completed or 0), kc[1].position or 9999))  # quem foi mais longe, antes
        ghosts: list[CarState] = []
        player_idx = snap.player_idx
        for n, (k, c) in enumerate(gone, start=1):
            idx = self._ghost_idx.setdefault(k, GHOST_IDX_BASE + len(self._ghost_idx))
            class_pos[c.class_name] = class_pos.get(c.class_name, 0) + 1
            ghosts.append(replace(c, idx=idx, position=live_pos + n, class_position=class_pos[c.class_name],
                                  status=CarStatus.OUT, in_session=False))
            if c.is_player:
                player_idx = idx  # o piloto local saiu: o `player()` passa a apontar para o fantasma
        return replace(snap, cars=list(snap.cars) + ghosts, session=session, player_idx=player_idx)
