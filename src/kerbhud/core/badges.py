"""Ícones de Driver Rank / Safety Rank / Driver Contact Badge do Le Mans Ultimate (sem Qt, testável).

O LMU não expõe esses ranks de OUTROS pilotos na memória compartilhada; só o SEU (informado em settings.json, chaves
`lmu.driver_rank` e `lmu.safety_rank`). O valor é convertido numa chave (`slug`): se existir `badges/<chave>.png`
(ou .webp/.jpg/.svg) esse arquivo é desenhado; senão, para os selos de contato conhecidos, um losango desenhado pelo
app; senão, o texto do rank.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

SUPPORTED_EXT = ("png", "webp", "jpg", "jpeg", "svg")

#: selos de contato do LMU: chave -> (nome, cor do losango, cor do símbolo)
CONTACT_BADGES: dict[str, tuple[str, str, str]] = {
    "rookie": ("Rookie", "#ffe600", "#1a1a2e"),
    "good": ("Good", "#3f7fc8", "#1a1a2e"),
    "trusted": ("Trusted", "#1dff63", "#1a1a2e"),
    "warning": ("Warning", "#ff2447", "#1a1a2e"),
    "probation": ("Probation", "#ff8a00", "#1a1a2e"),
    "creator": ("Creator", "#f4f4f6", "#1a1a2e"),
    "driver": ("Driver", "#f4f4f6", "#1a1a2e"),
    "staff": ("Staff", "#f4f4f6", "#1a1a2e"),
}


def slug(value: Optional[str]) -> Optional[str]:
    """"Trusted" -> "trusted"; "B 2" -> "b2". None/vazio -> None."""
    s = re.sub(r"[^a-z0-9]+", "", str(value or "").lower())
    return s or None


def badge_file(directory: Optional[Path], key: Optional[str]) -> Optional[Path]:
    if not key or directory is None:
        return None
    for ext in SUPPORTED_EXT:
        p = Path(directory) / f"{key}.{ext}"
        if p.is_file():
            return p
    return None


def has_icon(directory: Optional[Path], key: Optional[str]) -> bool:
    """Há algo para DESENHAR no lugar do texto (arquivo do usuário ou selo de contato conhecido)?"""
    return bool(key) and (key in CONTACT_BADGES or badge_file(directory, key) is not None)


#: cor do chip de rank (DR/SR) pela inicial do nível: Bronze, Silver, Gold, Platinum (outros: cinza neutro)
_TIER_COLORS = {"b": "#9c6a3a", "s": "#8a9099", "g": "#d4a514", "p": "#4fb3d9"}
TIER_NEUTRAL = "#6b6b75"


def tier_color(value: Optional[str]) -> str:
    s = slug(value)
    return _TIER_COLORS.get(s[0], TIER_NEUTRAL) if s else TIER_NEUTRAL
