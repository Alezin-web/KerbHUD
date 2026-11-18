"""Normalização do composto de pneu (texto do simulador -> letra + cor)."""
from __future__ import annotations

from typing import Optional

COLORS = {"S": "#e10600", "M": "#f5c400", "H": "#f4f4f5", "W": "#2f6bff", "I": "#14c05a", "D": "#cfcfd6"}
UNKNOWN_COLOR = "#8b8b95"


def normalize_compound(raw: Optional[str]) -> Optional[str]:
    """"Soft" -> "S", "Wet" -> "W"... None se vazio. Nomes desconhecidos viram a 1ª letra."""
    text = (raw or "").strip().upper()
    if not text:
        return None
    # "INTER" vem antes de "MED": "interMEDiate" contém "MED" e viraria pneu médio.
    for needle, letter in (("SOFT", "S"), ("INTER", "I"), ("MED", "M"), ("HARD", "H"), ("WET", "W"),
                           ("RAIN", "W"), ("SLICK", "D"), ("DRY", "D")):
        if needle in text:
            return letter
    return next((ch for ch in text if ch.isalpha()), None)


def compound_color(letter: Optional[str]) -> str:
    return COLORS.get(letter or "", UNKNOWN_COLOR)
