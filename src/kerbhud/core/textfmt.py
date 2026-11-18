"""Formatação de textos compartilhada pelos módulos (sem Qt)."""
from __future__ import annotations

from typing import Callable, Optional


def is_race(session_type: Optional[str]) -> bool:
    return "race" in (session_type or "").lower()


def format_laptime(seconds: Optional[float]) -> str:
    if seconds is None or seconds <= 0:
        return "—"
    m = int(seconds // 60)
    return f"{m}:{seconds - 60 * m:06.3f}"


def format_gap(seconds: Optional[float], laps: int = 0) -> str:
    if laps > 0:
        return f"+{laps}L"
    if seconds is None:
        return "—"
    seconds = max(0.0, seconds)
    if seconds < 10:
        return f"+{seconds:.3f}"
    if seconds < 100:
        return f"+{seconds:.1f}"
    m, s = divmod(seconds, 60)
    return f"+{int(m)}:{s:04.1f}"


def format_remaining(seconds: Optional[float]) -> str:
    """M:SS ou H:MM:SS."""
    if seconds is None or seconds < 0:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def format_clock(seconds: Optional[float]) -> str:
    """HH:MM:SS (relógio da corrida)."""
    if seconds is None or seconds < 0:
        return ""
    s = int(seconds)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def format_total(seconds: Optional[float]) -> str:
    """Duração total no formato HH:MMm (ex.: 00:45m)."""
    if seconds is None or seconds <= 0:
        return ""
    m = int(round(seconds / 60.0))
    return f"{m // 60:02d}:{m % 60:02d}m"


def fit_font_px(max_px: float, avail: float, measure: Callable[[float], float], min_px: float = 11.0,
                step: float = 0.5) -> float:
    """Maior tamanho de fonte (até `max_px`) em que o texto cabe em `avail`.

    Nomes de pilotos são mostrados COMPLETOS: em vez de abreviar ("J. Chadwick") ou cortar com
    reticências, a fonte encolhe até o texto caber. `measure(px)` devolve a largura do texto com
    aquele tamanho. Nunca vai abaixo de `min_px` (aí o módulo apenas recorta).
    """
    width = measure(max_px)
    if width <= avail or width <= 0:
        return max_px
    px = max(min_px, max_px * avail / width)  # a largura é quase proporcional ao tamanho
    while px > min_px and measure(px) > avail:  # ajuste fino
        px = max(min_px, px - step)
    return px
