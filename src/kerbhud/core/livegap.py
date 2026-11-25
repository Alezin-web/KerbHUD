"""Int/Gap ao vivo na corrida (sem Qt, testável).

O atraso publicado pelo iRacing (`CarIdxF2Time`) só muda quando o carro cruza a linha, então Int/Gap "pulavam" uma vez
por volta. Aqui o atraso é calculado a cada leitura pela posição na pista: voltas inteiras de diferença vezes o tempo
de volta de referência mais a diferença do tempo estimado até o ponto atual (`CarIdxEstTime`, que já considera que
curvas lentas "valem" mais tempo que retas). Sem o tempo estimado, cai na proporção da volta. Os atrasos são relativos
à PRÓPRIA classe (o primeiro de cada classe é o 0), que é como o Standings mostra Int e Gap.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from .liveorder import progress
from .model import CarState

MAX_GAP_S = 3600.0  # acima disso o cálculo está claramente errado (ex.: leitura inconsistente na linha de chegada)


def _between(a: CarState, b: CarState, est: Callable[[int], Optional[float]]) -> Optional[float]:
    """Segundos que `b` está atrás de `a` (a à frente). None se não dá para calcular."""
    pa, pb = progress(a), progress(b)
    lap = a.est_lap_time or b.est_lap_time
    if pa is None or pb is None or not lap or lap <= 0:
        return None
    ea, eb = est(a.idx), est(b.idx)
    if ea is not None and eb is not None and a.lap_dist_pct is not None and b.lap_dist_pct is not None:
        whole = round((pa - pb) - (a.lap_dist_pct - b.lap_dist_pct))  # voltas inteiras de diferença
        gap = whole * lap + (ea - eb)
    else:
        gap = (pa - pb) * lap
    if gap != gap or gap > MAX_GAP_S:
        return None
    return max(0.0, gap)


def live_gaps(cars: Sequence[CarState], est: Callable[[int], Optional[float]]) -> dict[int, tuple[Optional[float], Optional[float]]]:
    """{idx: (gap_leader, gap_ahead)} por classe, na ordem de `position`. Vazio se nada pôde ser calculado."""
    by_class: dict[Optional[str], list[CarState]] = {}
    for c in sorted((c for c in cars if c.position), key=lambda c: c.position or 0):
        by_class.setdefault(c.class_name, []).append(c)
    out: dict[int, tuple[Optional[float], Optional[float]]] = {}
    computed = False
    for group in by_class.values():
        total: Optional[float] = 0.0
        for k, c in enumerate(group):
            if k == 0:
                out[c.idx] = (0.0, None)
                continue
            step = _between(group[k - 1], c, est)
            total = None if (step is None or total is None) else total + step
            computed = computed or step is not None
            out[c.idx] = (total, step)
    return out if computed else {}
