from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..core.model import Sim, Snapshot


class ProviderDisconnected(Exception):
    """O simulador fechou ou a sessão terminou."""


class Provider(ABC):
    """Contrato comum. Um provider só LÊ dados; nunca envia nada ao simulador."""

    sim: Sim = Sim.NONE

    @abstractmethod
    def connect(self) -> bool:
        """Tenta conectar. Retorna True se pronto para `poll()`."""

    @abstractmethod
    def poll(self) -> Optional[Snapshot]:
        """Retorna um novo Snapshot, ou None se não há dados novos desde a última chamada.

        Levanta `ProviderDisconnected` quando o simulador some.
        """

    def close(self) -> None:
        pass

    def hint(self) -> str:
        """Texto de ajuda mostrado quando o simulador não é encontrado."""
        return ""
