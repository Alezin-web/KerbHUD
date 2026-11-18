"""Nomes e cores de exibição das classes de carro (Hypercar, LMP2, GT3...).

Os simuladores entregam nomes brutos diferentes (`LMP2_ELMS`, `LMGT3`, `GT3 Class`...).
Normalizamos por regras de substring. Quando o simulador fornece a cor da classe
(iRacing), ela tem prioridade; senão usamos a paleta de transmissão (WEC/IMSA).
Nomes desconhecidos continuam funcionando: rótulo truncado e cor estável por hash.
"""
from __future__ import annotations

import re
import zlib
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ClassStyle:
    label: str
    color: str  # "#rrggbb"


# (palavras-chave em MAIÚSCULAS, rótulo, cor padrão, cor no iRacing ou None para igual).
# A ordem importa: a primeira regra que casar vence.
#   LMP2 .......... azul claro (a classe "mais potente" depois do Hypercar/GTP)
#   Hypercar (LMU)  vermelho          GTP (iRacing) e DP .. amarelo
#   GT3 (LMU) ..... verde             GT3/GTD (iRacing, IMSA) .. vermelho rosado
RED, YELLOW, LIGHT_BLUE, GREEN, PINK = "#e10600", "#f5c400", "#4cc9f0", "#14c05a", "#ec4b73"
_RULES: tuple[tuple[tuple[str, ...], str, str, Optional[str]], ...] = (
    (("HYPER", "LMH", "LMDH"), "HYPER", RED, None),
    (("GTP",), "GTP", YELLOW, None),
    (("DPI", "DAYTONA"), "DP", YELLOW, None),
    (("LMP2",), "LMP2", LIGHT_BLUE, None),
    (("LMP3",), "LMP3", "#a855f7", None),
    (("GTE",), "GTE", "#f59e0b", None),
    (("GTD",), "GTD", GREEN, PINK),  # IMSA (iRacing): vermelho rosado
    (("GT3",), "GT3", GREEN, PINK),  # inclui LMGT3; rosa só no iRacing
)
# Classes com nome comprido (iRacing: Formula Ford 1600, Formula Vee, NASCAR...): rótulo curto, com a caixa que
# deve aparecer. Palavra-chave curta (até 3 letras) só vale como PALAVRA inteira ("F3" não casa em "F35").
_ABBREV: tuple[tuple[tuple[str, ...], str], ...] = (
    (("FORMULA VEE", "FORMULAVEE", "FVEE", "F VEE"), "FVee"),
    (("FF1600", "FF 1600", "FORMULA FORD", "RAY"), "F1600"),
    (("FORMULA RENAULT 3.5", "FR3.5", "FR35"), "FR3.5"),
    (("FORMULA RENAULT", "FR2.0", "FR20"), "FR2.0"),
    (("SUPER FORMULA", "SUPERFORMULA"), "SF"),
    (("FORMULA 3", "FORMULA3", "F3"), "F3"),
    (("FORMULA 1", "FORMULA ONE", "F1"), "F1"),
    (("INDYCAR", "INDY"), "Indy"),
    (("SKIP BARBER", "SKIPBARBER", "FORMULA 2000", "SBF"), "Skip"),
    (("MX-5", "MX5"), "MX-5"),
    (("GR86", "GR 86"), "GR86"),
    (("GT4",), "GT4"),
    (("TCR",), "TCR"),
    (("XFINITY", "NXS"), "NXS"),
    (("NEXT GEN", "NEXTGEN", "NASCAR"), "NASCAR"),
    (("TRUCK",), "Truck"),
    (("ARCA",), "ARCA"),
    (("LATE MODEL",), "Late"),
    (("SPRINT CAR", "SPRINT"), "Sprint"),
    (("MIDGET",), "Midget"),
    (("LEGENDS",), "Legend"),
    (("STREET STOCK",), "SStock"),
    (("MODIFIED",), "Mod"),
)
_ABBREV_RE = tuple(
    (tuple(re.compile(rf"(?<![A-Z0-9]){re.escape(n)}(?![A-Z0-9])" if len(n) <= 3 else re.escape(n)) for n in needles), label)
    for needles, label in _ABBREV
)
MAX_LABEL = 6  # largura da etiqueta de classe no Standings


def abbreviate_class(name: Optional[str]) -> str:
    """Rótulo curto de uma classe de nome comprido: "Formula Ford 1600" -> "F1600", "Formula Vee" -> "FVee"."""
    raw = (name or "").strip()
    up = raw.upper().replace("_", " ")
    for tests, label in _ABBREV_RE:
        if any(t.search(up) for t in tests):
            return label
    if len(raw) <= MAX_LABEL:
        return up.strip()
    words = re.findall(r"[A-Za-z0-9.]+", raw)
    if len(words) > 1 and words[0].upper() == "FORMULA":  # "Formula X" desconhecida: F + número ou última palavra
        nums = [w for w in words[1:] if any(ch.isdigit() for ch in w)]
        return ("F" + (nums[0] if nums else words[-1].capitalize()))[:MAX_LABEL]
    return up[:MAX_LABEL].strip()


_PALETTE = ("#06b6d4", "#f472b6", "#84cc16", "#fb923c", "#38bdf8", "#c084fc", "#facc15", "#34d399")


def class_style(raw: Optional[str], provided_color: Optional[str] = None, sim: object = None) -> ClassStyle:
    """Rótulo e cor da classe.

    As classes conhecidas usam a paleta do overlay (que depende do simulador: o GT3 do iRacing/IMSA é
    vermelho rosado e o do LMU é verde); a cor que o simulador informa (`provided_color`) só vale para
    classes desconhecidas. `sim` aceita o enum `Sim` ou seu valor em texto.
    """
    name = (raw or "").strip()
    up = name.upper()
    is_iracing = getattr(sim, "value", sim) == "iracing"
    if up in ("DP", "DPI"):  # "DP" só vale como nome exato (evita casar dentro de outras palavras)
        return ClassStyle("DP", YELLOW)
    for needles, label, color, iracing_color in _RULES:
        if any(n in up for n in needles):
            return ClassStyle(label, iracing_color if (is_iracing and iracing_color) else color)
    if not name:
        return ClassStyle("", provided_color or "#8b8b95")
    label = abbreviate_class(name)
    color = provided_color or _PALETTE[zlib.crc32(up.encode("utf-8")) % len(_PALETTE)]
    return ClassStyle(label, color)


def text_on(color: str) -> str:
    """Cor de texto legível (preto ou branco) sobre um fundo `#rrggbb`."""
    try:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, IndexError):
        return "#ffffff"
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#111111" if luminance > 150 else "#ffffff"


_LICENSE_COLORS = {"R": "#e5484d", "D": "#f97316", "C": "#facc15", "B": "#22c55e",
                   "A": "#3b82f6", "P": "#e5e7eb"}


def license_color(letter: Optional[str]) -> str:
    return _LICENSE_COLORS.get((letter or "").upper(), "#8b8b95")
