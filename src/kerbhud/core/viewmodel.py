"""Lógica de exibição dos módulos Inputs e Telemetria, sem Qt (testável)."""
from __future__ import annotations

import math
from typing import Optional

CHANNELS = ("throttle", "brake", "clutch", "speed", "rpm", "steering")
CHANNEL_LABELS = {"throttle": "Acelerador", "brake": "Freio", "clutch": "Embreagem",
                  "speed": "Velocidade", "rpm": "RPM", "steering": "Direção"}
CHANNEL_SHORT = {"throttle": "THR", "brake": "BRK", "clutch": "CLT",
                 "speed": "SPD", "rpm": "RPM", "steering": "STR"}

# (id da faixa, canais que ela contém, peso de altura)
LANES = (
    ("pedals", ("throttle", "brake", "clutch"), 2.0),
    ("speed", ("speed",), 1.0),
    ("rpm", ("rpm",), 1.0),
    ("steering", ("steering",), 1.0),
)
HISTORY_CHOICES = (5, 10, 20, 30, 60)
TRACE_CHOICES = (3, 6, 10, 20)  # histórico do gráfico embutido no Inputs
DEFAULT_TRACE_S = 6.0
DEFAULT_HISTORY_S = 10.0
SHIFT_LED_COUNT = 12
DEFAULT_SHIFT_START = 0.85  # fração do RPM máx. em que os LEDs começam (quando derivado)


def gear_label(gear: int) -> str:
    return "R" if gear < 0 else ("N" if gear == 0 else str(gear))


def get_channels(options: dict) -> dict[str, bool]:
    """Canais ligados/desligados do módulo de telemetria (padrão: todos ligados)."""
    raw = options.get("channels") if isinstance(options, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {c: (raw[c] if isinstance(raw.get(c), bool) else True) for c in CHANNELS}


def get_history_s(options: dict) -> float:
    try:
        v = float(options.get("history_s", DEFAULT_HISTORY_S))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_HISTORY_S
    return min(max(v, 3.0), 120.0) if math.isfinite(v) else DEFAULT_HISTORY_S


def get_trace_s(options: dict) -> float:
    try:
        v = float(options.get("trace_s", DEFAULT_TRACE_S))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_TRACE_S
    return min(max(v, 2.0), 60.0) if math.isfinite(v) else DEFAULT_TRACE_S


def get_shift_start(options: dict) -> float:
    try:
        v = float(options.get("shift_start", DEFAULT_SHIFT_START))
    except (TypeError, ValueError, AttributeError):
        return DEFAULT_SHIFT_START
    return min(max(v, 0.5), 0.99) if math.isfinite(v) else DEFAULT_SHIFT_START


def shift_lights(pct: Optional[float], source: Optional[str], n: int = SHIFT_LED_COUNT,
                 derived_start: float = DEFAULT_SHIFT_START, blink: Optional[bool] = None) -> tuple[int, bool]:
    """Quantos LEDs acender e se deve piscar (hora de trocar).

    Se o simulador fornece o indicador (`source == "sim"`), usa o valor direto. Se o
    valor foi derivado de RPM/RPM máx., os LEDs só começam em `derived_start`
    (senão ficariam acesos em qualquer rotação); é uma aproximação, configurável.
    """
    if pct is None:
        return 0, False
    p = (pct - derived_start) / (1.0 - derived_start) if source == "derived" else pct
    p = min(max(p, 0.0), 1.0)
    return int(p * n + 1e-9), (p >= 0.98 if blink is None else bool(blink))


def steer_label(deg: Optional[float]) -> str:
    if deg is None:
        return ""
    r = int(round(deg))
    if r == 0:
        return "0°"
    return f"R {abs(r)}°" if r > 0 else f"L {abs(r)}°"


def speed_value(speed_ms: float, units: str) -> float:
    return speed_ms * (2.2369362921 if units == "mph" else 3.6)


def speed_unit(units: str) -> str:
    return "mph" if units == "mph" else "km/h"


def nice_ceiling(v: float, step: float) -> float:
    return max(step, math.ceil(max(v, 0.0) / step) * step)


def enabled_lanes(channels: dict[str, bool]) -> list[tuple[str, tuple[str, ...], float]]:
    out = []
    for lane_id, chans, weight in LANES:
        on = tuple(c for c in chans if channels.get(c))
        if on:
            out.append((lane_id, on, weight))
    return out


def lane_layout(lanes: list[tuple[str, tuple[str, ...], float]], x: float, y: float,
                w: float, h: float, gap: float = 6.0) -> dict[str, tuple[float, float, float, float]]:
    """Divide a área em faixas empilhadas proporcionais ao peso."""
    if not lanes:
        return {}
    total_gap = gap * (len(lanes) - 1)
    unit = max(0.0, h - total_gap) / sum(wt for _, _, wt in lanes)
    out, cy = {}, y
    for lane_id, _, wt in lanes:
        out[lane_id] = (x, cy, w, unit * wt)
        cy += unit * wt + gap
    return out
