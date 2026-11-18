"""Módulo DIGFLAG: painel de LEDs com a bandeira atual: moldura de pontos e miolo na cor da bandeira. Só o safety
car tem a sigla "SC" (pontos brancos) e uma moldura mais grossa. Sem bandeira, nada é desenhado (sem quadro de fundo)."""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ..core.digflag import (BLINK_FLAGS, DEBRIS_STRIPE, FLAG_CODE, FLAG_LED, FLAG_STYLE, THICK_BORDER_FLAGS, DigFlagTracker,
                            led_pattern, debris_stripe)
from .module_base import ModuleWindow

BORDER_DOTS = 20  # LEDs por lado da moldura
FADE_S = 0.35  # tempo do fade ao aparecer/sumir
LED_OFF_BORDER = "#050506"  # moldura preta das bandeiras (exceto SC e a preta)


class DigFlagModule(ModuleWindow):
    PANEL_BG = False

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._tracker = DigFlagTracker()
        self._view = None   # bandeira atual (None/inativa = nenhuma)
        self._shown = None  # última bandeira desenhada (continua na tela durante o fade-out)
        self._alpha = 0.0
        self._t = time.monotonic()

    def update_snapshot(self, snap) -> None:
        self._view = self._tracker.update(snap)
        if self._view.active:
            self._shown = self._view
        self._refresh_animating()
        super().update_snapshot(snap)

    def _target(self) -> float:
        return 1.0 if (self._view is not None and self._view.active) else 0.0

    def _refresh_animating(self) -> None:
        blinking = bool(self._view is not None and self._view.active and self._view.primary in BLINK_FLAGS)
        self.is_animating = blinking or self._alpha != self._target()  # piscando ou em fade

    def _step_fade(self) -> None:
        now = time.monotonic()
        dt = max(0.0, min(now - self._t, 0.25))
        self._t = now
        target = self._target()
        if self._alpha < target:
            self._alpha = min(target, self._alpha + dt / FADE_S)
        elif self._alpha > target:
            self._alpha = max(target, self._alpha - dt / FADE_S)
        self._refresh_animating()

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        self._step_fade()
        v = self._shown if self.snapshot is not None else None
        if v is None or self._alpha <= 0.01:
            return
        p.setOpacity(self._alpha)
        side = min(w, h) - 6
        x0, y0 = (w - side) / 2, (h - side) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#08080a"))
        p.drawRoundedRect(QRectF(x0, y0, side, side), 10, 10)
        led = QColor(FLAG_LED[v.primary])
        phase = int(time.monotonic() * 2) % 2 == 1
        checker = v.primary == "checkered"
        blink_off = v.primary in BLINK_FLAGS and phase and not checker  # chegada: inverte o xadrez, não apaga
        step = side / (BORDER_DOTS + 1)
        r = step * 0.36
        rings = 2 if v.primary in THICK_BORDER_FLAGS else 1
        # moldura de LEDs (uma volta; o safety car tem duas, mais grossa)
        for ring in range(rings):
            inset = ring * step
            n = BORDER_DOTS + 1 - 2 * ring
            for i in range(n):
                for (px, py) in ((x0 + inset + step * (0.5 + i), y0 + inset + step * 0.5),
                                 (x0 + inset + step * (0.5 + i), y0 + side - inset - step * 0.5),
                                 (x0 + inset + step * 0.5, y0 + inset + step * (0.5 + i)),
                                 (x0 + side - inset - step * 0.5, y0 + inset + step * (0.5 + i))):
                    # moldura: preta nas bandeiras comuns; SC e a preta mantêm LEDs claros
                    c = QColor(led if v.primary in ("caution", "black") else LED_OFF_BORDER)
                    c.setAlphaF(0.25 if blink_off else 1.0)
                    p.setBrush(c)
                    p.drawEllipse(QPointF(px, py), r, r)
        # miolo: grade de LEDs; safety car = sigla em pontos brancos, as demais = só a cor da bandeira
        code = FLAG_CODE.get(v.primary)
        pattern = led_pattern(code) if code else None
        inner = side - 2 * step * (1.4 + (rings - 1))
        cell = step * 0.95 if not pattern else min(inner / (len(pattern[0]) + 0.6), inner / (len(pattern) + 2.4))
        gx_n = gy_n = int(inner // cell)
        gx0 = x0 + (side - gx_n * cell) / 2
        gy0 = y0 + (side - gy_n * cell) / 2
        fill = QColor(led)
        fill.setAlphaF(0.25 if blink_off else 0.92)
        dim = QColor("#ffffff")
        dim.setAlphaF(0.06)
        for gx in range(gx_n):
            for gy in range(gy_n):
                if pattern is None and v.primary == "checkered":
                    lit = (gx + gy + (1 if phase else 0)) % 2 == 0
                else:
                    lit = pattern is None and v.primary != "black"  # preta: miolo apagado (fica escuro)
                if lit and v.primary == "debris" and debris_stripe(gx, gy):
                    stripe = QColor(DEBRIS_STRIPE)
                    stripe.setAlphaF(0.25 if blink_off else 0.95)
                    p.setBrush(stripe)
                else:
                    p.setBrush(fill if lit else dim)
                p.drawEllipse(QPointF(gx0 + (gx + 0.5) * cell, gy0 + (gy + 0.5) * cell), cell * 0.36, cell * 0.36)
        if pattern:
            cols, rows = len(pattern[0]), len(pattern)
            tx0 = gx0 + (gx_n - cols) // 2 * cell
            ty0 = gy0 + (gy_n - rows) // 2 * cell
            p.setBrush(QColor("#f4f4f5"))
            for ry, row in enumerate(pattern):
                for cx, on in enumerate(row):
                    if on:
                        p.drawEllipse(QPointF(tx0 + (cx + 0.5) * cell, ty0 + (ry + 0.5) * cell), cell * 0.56, cell * 0.56)  # pontos grandes e sobrepostos = letra grossa
        # outras bandeiras ativas: pontinhos coloridos no canto de baixo
        for n, name in enumerate(v.others[:4]):
            p.setBrush(QColor(FLAG_STYLE[name][1]))
            p.setPen(QPen(QColor("#050506"), 1.0))
            p.drawEllipse(QPointF(x0 + step * (3.2 + n * 1.4), y0 + side - step * 3.2), r * 1.2, r * 1.2)
