"""Módulo SPOTTER: aviso visual de carro ao lado (sem áudio). Duas barras altas, uma em cada borda da janela
(estique a janela para ficarem nas laterais da tela, com a sua visão do carro no meio). Cada barra acende em laranja
quando há carro ao lado, com animação: a barra entra deslizando da borda, a moldura pulsa e um brilho sobe pela barra
como um carro passando; a linha fina marca onde ele está (mais alto = à frente, mais baixo = atrás; no iRacing a posição
não é informada e a linha fica fixa). Barras apagadas somem com fade; ao editar o layout ficam sempre visíveis."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen

from ..core.spotter import CAR_HALF_LEN_M, SpotterTracker
from . import theme
from .module_base import ModuleWindow, make_font

BAR_W = 46.0
FADE_S = 0.18
DEFAULT_MARK = 0.78  # posição da linha (0 = topo, 1 = base) quando não se sabe onde está o carro
TOP, BOTTOM = "#ffb347", "#e8650a"


class SpotterModule(ModuleWindow):
    PANEL_BG = False

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._tracker = SpotterTracker()
        self._sides = None
        self._alpha = [0.0, 0.0]
        self._t = time.monotonic()

    def update_snapshot(self, snap) -> None:
        self._sides = self._tracker.update(snap)  # a cada snapshot: o tempo de espera conta em tempo real
        self._refresh_animating()
        super().update_snapshot(snap)

    def _targets(self) -> list[float]:
        n = self._sides if (self._sides is not None and self.snapshot is not None) else (0, 0)
        return [1.0 if c > 0 else 0.0 for c in n]

    def _refresh_animating(self) -> None:
        # animando enquanto alguma barra está visível (brilho/pulso contínuos) ou em fade
        self.is_animating = any(a > 0.0 or a != t for a, t in zip(self._alpha, self._targets()))

    def _step_fade(self) -> None:
        now = time.monotonic()
        dt = max(0.0, min(now - self._t, 0.25))
        self._t = now
        for i, t in enumerate(self._targets()):
            a = self._alpha[i]
            self._alpha[i] = min(t, a + dt / FADE_S) if a < t else max(t, a - dt / FADE_S)
        self._refresh_animating()

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        self._step_fade()
        sides = self._sides if self.snapshot is not None else None
        if sides is None and self.snapshot is not None and self.snapshot.connected and self._edit:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(13, True))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "spotter sem dados")
        bw = min(BAR_W, w * 0.2)
        top, bh = 4.0, max(20.0, h - 8.0)
        offs = self._tracker.offsets
        for i, x in enumerate((4.0, w - 4.0 - bw)):  # 0 = esquerda, 1 = direita
            alpha = max(self._alpha[i], 0.28 if self._edit else 0.0)
            if alpha <= 0.01:
                continue
            n = sides[i] if sides is not None else 0
            a = self._alpha[i]
            slide = (1.0 - a) ** 2 * bw * 0.9  # entra deslizando da borda e sai de volta para ela
            p.save()
            p.setOpacity(p.opacity() * alpha)
            self._bar(p, x + (-slide if i == 0 else slide), top, bw, bh, n, offs[i], time.monotonic())
            p.restore()

    @staticmethod
    def _bar(p: QPainter, x: float, y0: float, bw: float, bh: float, n: int, off, now: float) -> None:
        pulse = 0.5 + 0.5 * math.sin(now * 2 * math.pi * 1.8) if n else 0.0
        edge = QColor(TOP) if n else QColor(255, 255, 255)
        edge.setAlphaF(0.16 + 0.34 * pulse if n else 0.16)
        p.setPen(QPen(edge, 1.5 + 1.5 * pulse))  # moldura que pulsa enquanto há carro ao lado
        p.setBrush(QColor(8, 8, 12, 165))
        p.drawRoundedRect(QRectF(x, y0, bw, bh), 10, 10)  # caixa escura translúcida
        pad = 6.0
        ix, iy, iw, ih = x + pad, y0 + pad, bw - 2 * pad, bh - 2 * pad
        grad = QLinearGradient(QPointF(ix, iy), QPointF(ix, iy + ih))
        grad.setColorAt(0.0, QColor(TOP))
        grad.setColorAt(1.0, QColor(BOTTOM))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        if n >= 2:  # dois carros: dois blocos
            gap = 6.0
            hh = (ih - gap) / 2
            for y in (iy, iy + hh + gap):
                p.drawRoundedRect(QRectF(ix, y, iw, hh), 6, 6)
        else:
            p.drawRoundedRect(QRectF(ix, iy, iw, ih), 6, 6)
        if n:  # brilho que sobe pela barra, como um carro passando
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(ix, iy, iw, ih), 6, 6)
            p.save()
            p.setClipPath(clip)
            band = ih * 0.5
            top_y = iy + ih - ((now % 1.1) / 1.1) * (ih + band)
            sweep = QLinearGradient(QPointF(ix, top_y), QPointF(ix, top_y + band))
            sweep.setColorAt(0.0, QColor(255, 255, 255, 0))
            sweep.setColorAt(0.5, QColor(255, 255, 255, 120))
            sweep.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(sweep))
            p.drawRect(QRectF(ix, top_y, iw, band))
            p.restore()
        # linha fina: onde está o carro (topo = 5,5 m à frente; base = 5,5 m atrás)
        frac = DEFAULT_MARK if off is None else 0.5 - max(-1.0, min(1.0, off / CAR_HALF_LEN_M)) * 0.5
        y = iy + 4 + frac * (ih - 8)
        p.setPen(QPen(QColor(255, 255, 255, 215), 1.5))
        p.drawLine(QPointF(ix + 2, y), QPointF(ix + iw - 2, y))
