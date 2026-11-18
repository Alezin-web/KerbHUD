"""Quando mostrar o overlay: sempre, só na pista ou só na garagem (sem Qt, testável).

Só "Sempre" e o modo DEMO mostram tudo o tempo todo. O estado "na garagem" vem do simulador (`Snapshot.in_garage`): iRacing `IsInGarage`; LMU, o carro do piloto parado
na vaga da garagem (`mInGarageStall`). Se o simulador não informar a garagem mas o carro do piloto existir, ele é tratado como "na pista".
No iRacing, replay e telas entre sessões não são "pista" nem "garagem": o simulador diz que o piloto não está dirigindo (`Snapshot.driving`).
Cada módulo pode seguir a regra global (`global`) ou ter a sua própria (`options["show_when"]`).
"""
from __future__ import annotations

from .model import Snapshot

MODES = ("always", "track", "garage")
MODE_LABELS = {"always": "Sempre", "track": "Só na pista", "garage": "Só na garagem"}
GLOBAL = "global"


def normalize(mode) -> str:
    return mode if mode in MODES else "always"


def effective_mode(global_mode, module_mode) -> str:
    return normalize(global_mode) if module_mode in (None, GLOBAL) else normalize(module_mode)


def on_track(snap: Snapshot | None) -> bool:
    """Piloto realmente na pista: simulador conectado, carro do piloto existe e não está na garagem."""
    return bool(snap and snap.connected and snap.player() is not None and snap.in_garage is not True
                and snap.driving is not False)


def in_garage(snap: Snapshot | None) -> bool:
    return bool(snap and snap.connected and snap.in_garage is True)


def allowed(mode: str, snap: Snapshot | None) -> bool:
    """O módulo pode aparecer agora?

    * "Sempre": sempre.
    * Modo DEMO: sempre (é para testar o visual, então nenhuma regra esconde).
    * "Só na pista" / "Só na garagem": só quando o simulador está conectado E o piloto está de fato na pista / na garagem.
      Com o jogo fechado, nos menus ou sem carro do piloto, nada aparece.
    """
    mode = normalize(mode)
    if mode == "always" or (snap is not None and snap.is_demo):
        return True
    return in_garage(snap) if mode == "garage" else on_track(snap)
