"""RPM de troca aprendido pelo próprio piloto (sem Qt, testável).

O Le Mans Ultimate não informa em que RPM o shift light do carro acende. Em vez de usar só o RPM máximo (o corte), o
KerbHUD observa as trocas de marcha para cima feitas com o acelerador a fundo e guarda o RPM em que ocorreram; o LED
passa a "encher" até esse RPM. Zera ao trocar de carro (RPM máximo muda). Enquanto não aprendeu, usa o RPM máximo.
"""
from __future__ import annotations

from collections import deque
from typing import Deque, Optional

MIN_SAMPLES = 2
KEEP = 8
FULL_THROTTLE = 0.9
MIN_FRAC_OF_MAX = 0.80  # troca abaixo disso não conta (troca precoce/ruído)
RECENT_S = 0.4          # o pico de RPM considerado é o dos instantes antes da troca


class ShiftLearner:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._samples: Deque[float] = deque(maxlen=KEEP)
        self._gear: Optional[int] = None
        self._recent: Deque[tuple[float, float, float]] = deque()  # (t, rpm, throttle)
        self._rpm_max: Optional[float] = None

    def reference(self, rpm_max: Optional[float]) -> Optional[float]:
        if not rpm_max:
            return None
        if len(self._samples) < MIN_SAMPLES:
            return rpm_max
        return min(rpm_max, max(self._samples))

    def observe(self, gear: int, rpm: float, throttle: float, rpm_max: Optional[float], now: float) -> None:
        if rpm_max and self._rpm_max and abs(rpm_max - self._rpm_max) > 0.05 * self._rpm_max:
            self.reset()  # outro carro
        if rpm_max:
            self._rpm_max = rpm_max
        self._recent.append((now, rpm, throttle))
        while self._recent and now - self._recent[0][0] > RECENT_S:
            self._recent.popleft()
        if self._gear is not None and gear > self._gear >= 1 and rpm_max:
            full = [r for _t, r, th in self._recent if th >= FULL_THROTTLE]
            if full and max(full) >= MIN_FRAC_OF_MAX * rpm_max:
                self._samples.append(max(full))
        self._gear = gear
