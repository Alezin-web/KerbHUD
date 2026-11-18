"""DigFlag: a bandeira atual, em destaque (sem Qt, testável).

Mostra a bandeira MAIS IMPORTANTE entre as que o simulador mostra ao piloto (ordem em `FLAG_PRIORITY`). A verde só
aparece por `GREEN_SHOW_S` depois de começar (senão ficaria na tela a corrida toda); sem bandeira, nada aparece.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .model import FLAG_PRIORITY, Snapshot

GREEN_SHOW_S = 6.0

#: bandeira -> (rótulo, cor de fundo, cor do texto)
FLAG_STYLE: dict[str, tuple[str, str, str]] = {
    "red": ("VERMELHA", "#d4141c", "#ffffff"),
    "black": ("PRETA", "#050506", "#ffffff"),
    "disqualify": ("DESQUALIFICADO", "#050506", "#e10600"),
    "repair": ("REPARO OBRIGATÓRIO", "#111111", "#f5c400"),
    "yellow": ("AMARELA", "#f5c400", "#111111"),
    "caution": ("SAFETY CAR", "#f5c400", "#111111"),
    "blue": ("AZUL", "#2f6bff", "#ffffff"),
    "debris": ("DETRITOS", "#f5c400", "#111111"),
    "white": ("BRANCA", "#f4f4f5", "#111111"),
    "checkered": ("CHEGADA", "#f4f4f5", "#111111"),
    "green": ("VERDE", "#14c05a", "#ffffff"),
}


#: sigla no painel de LEDs: só o safety car tem texto; as demais bandeiras são mostradas só pela cor
FLAG_CODE = {"caution": "SC"}
THICK_BORDER_FLAGS = ("caution",)  # moldura de LEDs mais grossa (duas voltas de pontos)
FLAG_LED = {"red": "#ff2a2a", "black": "#f4f4f5", "disqualify": "#ff2a2a", "repair": "#ffd400", "yellow": "#ffd400",
            "caution": "#ffd400", "blue": "#3a7bff", "debris": "#ffd400", "white": "#f4f4f5", "checkered": "#f4f4f5",
            "green": "#25e06a"}
DEBRIS_STRIPE = "#ff2a2a"  # detritos: amarelo com listras vermelhas na diagonal
STRIPE_WIDTH = 2           # largura da listra, em LEDs


def debris_stripe(gx: int, gy: int) -> bool:
    """True se o LED (gx, gy) da grade cai numa listra vermelha da bandeira de detritos."""
    return ((gx + gy) // STRIPE_WIDTH) % 2 == 1


BLINK_FLAGS = tuple(FLAG_STYLE)  # todas as bandeiras piscam (2 Hz); a de chegada inverte o xadrez em vez de apagar

#: fonte de pontos 5x7 (só as letras usadas nas siglas)
_FONT = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "I": "01110 00100 00100 00100 00100 00100 01110",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "N": "10001 11001 10101 10011 10001 10001 10001", "O": "01110 10001 10001 10001 10001 10001 01110",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
}


def led_pattern(text: str) -> list[list[int]]:
    """Texto -> matriz de pontos (7 linhas), letras de 5 colunas separadas por 1 coluna apagada."""
    rows = [[] for _ in range(7)]
    for n, ch in enumerate(text.upper()):
        glyph = _FONT.get(ch, "00000 " * 6 + "00000").split()
        for r in range(7):
            if n:
                rows[r].append(0)
            rows[r].extend(int(c) for c in glyph[r])
    return rows


@dataclass
class FlagView:
    primary: Optional[str] = None
    others: list[str] = field(default_factory=list)  # as outras ativas, da mais para a menos importante

    @property
    def active(self) -> bool:
        return self.primary is not None


class DigFlagTracker:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._green_since: Optional[float] = None

    def update(self, snap: Optional[Snapshot]) -> FlagView:
        if snap is None or not snap.connected:
            self._green_since = None
            return FlagView()
        now = self._clock()
        flags = [f for f in FLAG_PRIORITY if f in snap.session.flags]
        if "green" in flags:
            if self._green_since is None:
                self._green_since = now
            if now - self._green_since > GREEN_SHOW_S:
                flags.remove("green")
        else:
            self._green_since = None
        return FlagView(primary=flags[0], others=flags[1:]) if flags else FlagView()
