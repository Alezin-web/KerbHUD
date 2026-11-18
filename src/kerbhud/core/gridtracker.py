"""Posições ganhas/perdidas desde a largada (coluna da seta no Standings)."""
from __future__ import annotations

from .model import Sim, Snapshot
from .textfmt import is_race


class StartGridTracker:
    """Guarda a posição de cada carro na PRIMEIRA vez em que o overlay o viu na corrida.

    Se o overlay for aberto durante a corrida, a referência é o momento da abertura (e não a
    largada real). Reinicia quando muda o simulador, a pista ou o tipo de sessão.
    """

    def __init__(self) -> None:
        self._sig = None
        self._start: dict[int, int] = {}

    def reset(self) -> None:
        self._sig, self._start = None, {}

    def update(self, snap: Snapshot) -> dict[int, int]:
        """{idx: posições ganhas}; positivo = subiu, negativo = desceu. Vazio fora de corrida."""
        if not snap.connected or snap.sim == Sim.NONE or not is_race(snap.session.session_type):
            self.reset()
            return {}
        sig = (snap.sim, snap.session.track_name, snap.session.session_type)
        if sig != self._sig:
            self._sig, self._start = sig, {}
        for c in snap.cars:
            if c.position and c.idx not in self._start:
                self._start[c.idx] = c.position
        return {c.idx: self._start[c.idx] - c.position
                for c in snap.cars if c.position and c.idx in self._start}
