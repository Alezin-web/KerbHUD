"""Posição estimada do carro do piloto a partir de velocidade e rumo (sem Qt, testável).

O iRacing NÃO publica a posição (Lat/Lon) na telemetria ao vivo das versões normais do jogo. O que ele publica é
a velocidade (`Speed`), o rumo em relação ao norte (`YawNorth`) e o relógio da sessão (`SessionTime`). Somando
"velocidade x tempo" na direção do rumo dá o caminho que o carro fez; ele só serve para desenhar o traçado do circuito
(o `TrackRecorder` corrige a deriva de cada volta). Não vem de uma fonte inventada: é cálculo sobre dados reais.

Convenção: x = leste, z = norte. O iRacing mede o giro para a ESQUERDA como positivo (sentido anti-horário), então o rumo
no relógio (horário a partir do norte) é `-YawNorth`. Se o desenho sair espelhado no seu jogo, use "Espelhar" no Track Map.
"""
from __future__ import annotations

import math
from typing import Optional

MAX_DT_S = 0.25  # buraco maior que isso (pausa, replay, travada) não é integrado: o caminho seria inventado


class DeadReckoner:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.x = 0.0
        self.z = 0.0
        self._t: Optional[float] = None
        self._speed = 0.0
        self._heading = 0.0
        self.valid = False  # já tem pelo menos uma amostra boa

    def update(self, session_time: Optional[float], speed_ms: Optional[float], yaw_north: Optional[float]) -> Optional[tuple[float, float]]:
        """Devolve (x, z) em metros, ou None se faltam dados. A origem (0, 0) é onde a estimativa começou."""
        if session_time is None or speed_ms is None or yaw_north is None:
            return None
        if not all(math.isfinite(v) for v in (session_time, speed_ms, yaw_north)):
            return None
        heading = -yaw_north  # horário a partir do norte
        if self._t is not None:
            dt = session_time - self._t
            if 0.0 < dt <= MAX_DT_S:
                # rumo médio entre as duas amostras (pelo caminho curto do círculo) e velocidade média
                dh = math.atan2(math.sin(heading - self._heading), math.cos(heading - self._heading))
                mid = self._heading + dh / 2.0
                v = (speed_ms + self._speed) / 2.0
                self.x += v * math.sin(mid) * dt
                self.z += v * math.cos(mid) * dt
            elif dt <= 0.0 or dt > MAX_DT_S:
                pass  # tempo voltou (replay) ou ficou parado: só atualiza a referência
        self._t, self._speed, self._heading = session_time, speed_ms, heading
        self.valid = True
        return self.x, self.z
