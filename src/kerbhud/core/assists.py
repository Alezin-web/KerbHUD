"""Ajudas e travamento no Inputs/Telemetria (sem Qt, testável).

* ABS e TC "atuando" vêm do simulador (LMU: `mABSActive`/`mTCActive`; iRacing: `BrakeABSactive`; o iRacing não informa o TC).
  Sem a informação, o valor é None e nada é mostrado.
* Travamento de roda NÃO vem pronto: é DERIVADO no LMU da velocidade de deslizamento longitudinal do contato do pneu com a
  pista (`mLongitudinalPatchVel`) em relação à velocidade do carro, só com o pé no freio. Limiares A VALIDAR no jogo.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

LOCKUP_SLIP = 0.30         # deslizamento (fração da velocidade do carro) a partir do qual a roda é considerada travada
LOCKUP_MIN_BRAKE = 0.10    # só conta com freio pressionado (evita confundir com patinação na aceleração)
LOCKUP_MIN_SPEED_MS = 8.0  # abaixo disso (~29 km/h) a razão fica instável
PULSE_HZ = 6.0             # pulsar do aviso de ABS/TC


def lockup(speed_ms: float, brake: float, patch_vels: Iterable[float]) -> bool:
    """True se alguma roda desliza pelo menos `LOCKUP_SLIP` da velocidade do carro com o freio pressionado."""
    if brake < LOCKUP_MIN_BRAKE or not math.isfinite(speed_ms) or speed_ms < LOCKUP_MIN_SPEED_MS:
        return False
    for v in patch_vels:
        if math.isfinite(v) and abs(v) / speed_ms >= LOCKUP_SLIP:
            return True
    return False


def assist_on(abs_active: Optional[bool], tc_active: Optional[bool]) -> bool:
    return abs_active is True or tc_active is True


def pulse(now: float) -> float:
    """Intensidade 0.6..1.0 do aviso (pulsa suavemente, sem apagar por completo)."""
    return 0.8 + 0.2 * math.sin(now * 2.0 * math.pi * PULSE_HZ)
