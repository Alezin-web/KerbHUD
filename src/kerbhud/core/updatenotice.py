"""Quando e como avisar que há versão nova (sem Qt): faixa na janela principal, balão na bandeja e item no menu.

Regras: a faixa aparece enquanto houver versão nova que a pessoa ainda não dispensou ("Agora não" vale só para
aquela versão: uma versão mais nova volta a avisar); o balão da bandeja aparece uma vez por versão e por execução
(as checagens periódicas não repetem o aviso). O KerbHUD nunca abre janelas sozinho: no meio de uma corrida isso
tiraria o foco do jogo."""
from __future__ import annotations

from typing import Optional

from .updater import parse_version

RECHECK_HOURS = 6  # reconferir de tempos em tempos (o programa fica dias aberto na bandeja)


class UpdateNotice:
    def __init__(self, dismissed: str = ""):
        self.dismissed = str(dismissed or "")
        self._ballooned: set[str] = set()

    def banner_visible(self, available: Optional[str]) -> bool:
        if not available:
            return False
        if not self.dismissed:
            return True
        try:
            return parse_version(available) > parse_version(self.dismissed)
        except ValueError:
            return available != self.dismissed

    def dismiss(self, version: str) -> None:
        self.dismissed = str(version or "")

    def should_balloon(self, version: str) -> bool:
        """True só na primeira vez que esta versão é anunciada nesta execução."""
        if version in self._ballooned:
            return False
        self._ballooned.add(version)
        return True
