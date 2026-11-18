"""Animação de ultrapassagens (sem Qt, testável com relógio injetado).

Inspirada no vídeo de referência: quando as posições mudam, as linhas DESLIZAM suavemente para o
novo lugar, o conteúdo esmaece levemente durante o movimento e a linha que subiu/desceu recebe um
destaque verde/vermelho que some em ~1 s. Linhas que entram na lista aparecem com fade-in.

Uso: a cada desenho, chame `set_targets(itens, agora)` com as linhas visíveis na ordem dos slots e
depois `sample(chave, agora)` para saber o deslocamento/opacidade/destaque de cada linha.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Hashable, Optional, Sequence

MOVE_S = 0.45
FLASH_S = 1.0
FADE_DIP = 0.45  # quanto o conteúdo esmaece no meio do movimento


@dataclass(frozen=True)
class RowAnim:
    dy_rows: float = 0.0  # somar a (slot * altura da linha): negativo = vem de cima, positivo = vem de baixo
    alpha: float = 1.0  # fade-in de linhas novas
    flash: float = 0.0  # +1 verde (ganhou posição) ... -1 vermelho (perdeu); decai a zero
    content_alpha: float = 1.0  # esmaece durante o movimento

    @property
    def moving(self) -> bool:
        return abs(self.dy_rows) > 1e-3


NEUTRAL = RowAnim()


def ease_out_cubic(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1.0 - (1.0 - t) ** 3


class SlotAnimator:
    def __init__(self, move_s: float = MOVE_S, flash_s: float = FLASH_S, enabled: bool = True):
        self.move_s, self.flash_s, self.enabled = move_s, flash_s, enabled
        self._slot: dict[Hashable, int] = {}
        self._rank: dict[Hashable, int] = {}
        self._move: dict[Hashable, tuple[float, float, float]] = {}  # chave -> (de, para, t0)
        self._flash: dict[Hashable, tuple[int, float]] = {}  # chave -> (sinal, t0)
        self._appear: dict[Hashable, float] = {}  # chave -> t0

    def reset(self) -> None:
        self._slot.clear(); self._rank.clear(); self._move.clear(); self._flash.clear(); self._appear.clear()

    # ---- entrada ---------------------------------------------------------- #
    def set_targets(self, items: Sequence[Optional[tuple[Hashable, int]]], now: float) -> None:
        """`items[slot]` = (chave, rank) ou None (slot vazio). rank menor = melhor posição."""
        if not self.enabled:
            self.reset()
            return
        new_slot = {it[0]: i for i, it in enumerate(items) if it is not None}
        new_rank = {it[0]: it[1] for it in items if it is not None}
        fresh = [k for k in new_slot if k not in self._slot]
        # primeira chamada ou troca drástica (layout/escopo/sessão): sem animação, só atualiza
        if not self._slot or (len(new_slot) > 3 and len(fresh) * 2 >= len(new_slot)):
            self.reset()
            self._slot, self._rank = new_slot, new_rank
            return
        for key, slot in new_slot.items():
            if key not in self._slot:
                self._appear[key] = now
                continue
            old_slot, old_rank = self._slot[key], self._rank[key]
            if slot != old_slot:
                shown = self._displayed(key, now)
                self._move[key] = (shown, float(slot), now)
            if new_rank[key] != old_rank:
                self._flash[key] = (1 if new_rank[key] < old_rank else -1, now)
        for key in list(self._slot):
            if key not in new_slot:
                for d in (self._move, self._flash, self._appear):
                    d.pop(key, None)
        self._slot, self._rank = new_slot, new_rank

    # ---- saída ------------------------------------------------------------ #
    def _displayed(self, key: Hashable, now: float) -> float:
        mv = self._move.get(key)
        if mv is None:
            return float(self._slot[key])
        src, dst, t0 = mv
        p = (now - t0) / self.move_s
        return dst if p >= 1.0 else src + (dst - src) * ease_out_cubic(p)

    def sample(self, key: Hashable, now: float) -> RowAnim:
        if not self.enabled or key not in self._slot:
            return NEUTRAL
        dy, content = 0.0, 1.0
        mv = self._move.get(key)
        if mv is not None:
            src, dst, t0 = mv
            p = (now - t0) / self.move_s
            if p >= 1.0:
                del self._move[key]
            else:
                dy = (src + (dst - src) * ease_out_cubic(p)) - dst
                content = 1.0 - FADE_DIP * math.sin(math.pi * min(max(p, 0.0), 1.0))
        alpha = 1.0
        t_app = self._appear.get(key)
        if t_app is not None:
            alpha = min(max((now - t_app) / self.move_s, 0.0), 1.0)
            if alpha >= 1.0:
                del self._appear[key]
        flash = 0.0
        fl = self._flash.get(key)
        if fl is not None:
            sign, t0 = fl
            left = 1.0 - (now - t0) / self.flash_s
            if left <= 0.0:
                del self._flash[key]
            else:
                flash = sign * left
        return RowAnim(dy, alpha, flash, content)

    def active(self, now: float) -> bool:
        """Há algo animando? (o módulo pede novo desenho enquanto isso for verdade)"""
        if not self.enabled:
            return False
        return (any(now - t0 < self.move_s for _s, _d, t0 in self._move.values())
                or any(now - t0 < self.flash_s for _sg, t0 in self._flash.values())
                or any(now - t0 < self.move_s for t0 in self._appear.values()))
