"""iRating: SOF e projeção de ganho/perda (ESTIMATIVA, não o valor oficial).

* SOF (Strength of Field): fórmula conhecida do iRacing, a partir dos iRatings de quem está
  na corrida (aqui: os carros da classe presentes na sessão).
* Projeção: modelo tipo Elo para corridas multi-piloto. A chance de A bater B segue a curva
  logística base-2 do iRating (1600 pontos = fator 2); a nota esperada de cada piloto é a soma
  das chances contra todos; a variação é (colocação real - esperada) * K / N, com K = 200.
  A soma das variações do grupo é zero. O iRacing aplica ajustes próprios (ex.: quem não
  largou/terminou), então o valor oficial pós-corrida pode diferir. É um indicador ao vivo.
"""
from __future__ import annotations

import math
from typing import Hashable, Optional, Sequence

BR1 = 1600.0 / math.log(2.0)
K_FACTOR = 200.0


def _expo(rating: float) -> float:
    return math.exp(-rating / BR1)


def sof(ratings: Sequence[float]) -> Optional[float]:
    if not ratings:
        return None
    return -BR1 * math.log(sum(_expo(r) for r in ratings) / len(ratings))


def _chance(ri: float, rj: float) -> float:
    ei, ej = _expo(ri), _expo(rj)
    return ((1.0 - ei) * ej) / ((1.0 - ej) * ei + (1.0 - ei) * ej)


def projected_changes(entries: Sequence[tuple[Hashable, float, int]], k: float = K_FACTOR) -> dict[Hashable, int]:
    """entries: (chave, iRating, posição). Retorna {chave: variação estimada}. Precisa de 2+ pilotos."""
    ordered = sorted(entries, key=lambda e: e[2])
    n = len(ordered)
    if n < 2:
        return {}
    out: dict[Hashable, int] = {}
    for rank, (key, rating, _pos) in enumerate(ordered, start=1):
        expected = sum(_chance(rating, other[1]) for other in ordered if other[0] != key)
        actual = n - rank  # quantos pilotos ficaram atrás
        out[key] = int(round((actual - expected) * k / n))
    return out


def format_ir(value: Optional[float]) -> str:
    if value is None:
        return ""
    v = int(round(value))
    return f"{v / 1000:.1f}k" if v >= 1000 else str(v)
