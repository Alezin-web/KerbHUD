"""Histórico recente dos inputs do piloto (camada de processamento).

O motor publica snapshots numa thread; este buffer se inscreve nele, guarda as
amostras com carimbo de tempo e a UI lê janelas de tempo para desenhar gráficos.
Thread-safe. Memória limitada: no máximo `max_seconds` de histórico.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional

from .model import Sim, Snapshot


@dataclass(frozen=True)
class Sample:
    t: float  # time.monotonic() no momento em que o snapshot chegou
    throttle: float
    brake: float
    clutch: float
    speed_ms: float
    rpm: float
    steering: float  # -1..1, negativo = esquerda
    rpm_max: Optional[float]
    steering_deg: Optional[float]
    gear: int
    abs_on: bool = False
    tc_on: bool = False
    lock: bool = False


class TelemetryHistory:
    def __init__(self, max_seconds: float = 120.0, max_samples: int = 30000):
        self.max_seconds = max_seconds
        self._buf: deque[Sample] = deque(maxlen=max_samples)
        self._lock = threading.Lock()
        self._sim: Optional[Sim] = None

    # ---- escrita (thread do motor) ------------------------------------- #
    def on_snapshot(self, snap: Snapshot, now: Optional[float] = None) -> None:
        with self._lock:
            if not snap.connected or snap.sim != self._sim:
                self._buf.clear()  # simulador mudou ou desconectou: histórico antigo não vale
            self._sim = snap.sim if snap.connected else None
            i = snap.inputs
            if not snap.connected or i is None:
                return
            t = time.monotonic() if now is None else now
            self._buf.append(Sample(t, i.throttle, i.brake, i.clutch, i.speed_ms, i.rpm,
                                    i.steering, i.rpm_max, i.steering_deg, i.gear,
                                    i.abs_active is True, i.tc_active is True, i.lockup is True))
            cutoff = t - self.max_seconds
            while self._buf and self._buf[0].t < cutoff:
                self._buf.popleft()

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    # ---- leitura (thread da UI) ----------------------------------------- #
    def window(self, seconds: float) -> list[Sample]:
        """Amostras dos últimos `seconds`, ancoradas na amostra mais recente.

        Ancorar na última amostra (e não no relógio) congela o gráfico quando o jogo
        é pausado, em vez de deixá-lo deslizar para fora da tela.
        """
        with self._lock:
            if not self._buf:
                return []
            cutoff = self._buf[-1].t - seconds
            out: list[Sample] = []
            for s in reversed(self._buf):
                if s.t < cutoff:
                    break
                out.append(s)
        out.reverse()
        return out

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


def decimate_columns(ts: list[float], vs: list[float], buckets: int) -> tuple[list[float], list[float]]:
    """Reduz uma série para ~4 pontos por coluna de pixel sem perder picos.

    Divide as amostras em `buckets` fatias e, em cada uma, mantém primeiro, último,
    mínimo e máximo (em ordem temporal). Um toque rápido no freio continua visível
    mesmo com 60 s de histórico numa área de poucas centenas de pixels. Usa
    `min`/`max` sobre fatias (executados em C), por isso é barato.
    """
    n = len(ts)
    if buckets <= 0 or n <= buckets * 2:
        return ts, vs
    out_t: list[float] = []
    out_v: list[float] = []
    for b in range(buckets):
        lo, hi = b * n // buckets, (b + 1) * n // buckets
        if hi <= lo:
            continue
        seg = vs[lo:hi]
        keep = {lo, hi - 1, seg.index(min(seg)) + lo, seg.index(max(seg)) + lo}
        for k in sorted(keep):
            out_t.append(ts[k])
            out_v.append(vs[k])
    return out_t, out_v
