"""Car Damage (sem Qt, testável): resume as avarias que o simulador realmente publica.

* LMU: gravidade (0 nenhuma, 1 leve, 2 forte) em 8 regiões do carro, peça solta e superaquecimento.
* iRacing: NÃO publica avarias por região; só tempo de reparo obrigatório/opcional e de reboque.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .model import DAMAGE_ZONES, Snapshot

SEVERITY_NAMES = ("OK", "LEVE", "FORTE")


@dataclass
class DamageView:
    has_data: bool = False
    zones: Optional[list[int]] = None  # na ordem de DAMAGE_ZONES
    worst: int = 0
    detached: bool = False
    overheating: bool = False
    repair_lines: list[tuple[str, float]] = field(default_factory=list)  # (rótulo, segundos)
    health_pct: Optional[float] = None  # 100 = sem avarias, desce com os amassados (só quando há regiões; iRacing = None)
    headline: str = ""  # "SEM DANOS", "DANO LEVE"...
    level: str = "ok"  # ok | warn | danger
    message: str = ""


def damage_view(snap: Optional[Snapshot]) -> DamageView:
    if snap is None or not snap.connected:
        return DamageView(message="Aguardando dados")
    d = snap.damage
    if d is None:
        return DamageView(message="Sem dados de danos")
    v = DamageView(has_data=True)
    if d.zones is not None and len(d.zones) == len(DAMAGE_ZONES):
        v.zones = [max(0, min(2, int(z))) for z in d.zones]
        v.worst = max(v.zones)
        v.health_pct = max(0.0, 100.0 - 100.0 * sum(v.zones) / (2 * len(v.zones)))
    v.detached = bool(d.detached)
    v.overheating = bool(d.overheating)
    if v.detached and v.health_pct is not None:
        v.health_pct = max(0.0, v.health_pct - 10.0)  # peça solta pesa mais que um amassado
    for label, secs in (("Reparo obrigatório", d.repair_required_s), ("Reparo opcional", d.repair_optional_s),
                        ("Reboque", d.tow_s)):
        if secs is not None and secs > 0.05:
            v.repair_lines.append((label, secs))
    if v.detached or v.worst >= 2 or any(lbl != "Reparo opcional" for lbl, _ in v.repair_lines):
        v.level = "danger"
    elif v.worst == 1 or v.overheating or v.repair_lines:
        v.level = "warn"
    if v.detached:
        v.headline = "PEÇA SOLTA"
    elif v.worst >= 2:
        v.headline = "DANO FORTE"
    elif v.worst == 1:
        v.headline = "DANO LEVE"
    elif v.repair_lines:
        v.headline = "REPARO PENDENTE"
    else:
        v.headline = "SEM DANOS"
    if v.overheating and v.level == "ok":
        v.level = "warn"
    return v


def format_seconds(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 60}:{s % 60:02d}"
