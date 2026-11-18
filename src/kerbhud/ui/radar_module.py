"""Módulo RADAR: vista de cima, centrada no meu carro (frente para cima), com os carros ao redor.

LMU: posições reais. iRacing: a distância à frente/atrás é real, mas o lado só se sabe pelo aviso de carro ao lado
do simulador (por isso aparece "lado estimado"). Carros próximos ficam amarelos (até 14 m) ou vermelhos (até 6 m).
Alertas: carro AO LADO acende uma meia-lua do lado dele (amarela; vermelha se quase encostando); carro VINDO DE TRÁS
desenha uma faixa que sai da frente dele e passa por cima do meu carro, sumindo com fade. O radar só aparece quando
há carro perto (fade-in/out).
"""
from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient

from ..core.classes import class_style
from ..core.radar import (SHOW_M_CORE, RadarSmoother, approaching_from_behind, get_range, proximity, radar_view, side_levels,
                          strip_slope)
from . import theme
from .module_base import ModuleWindow, make_font

CAR_W_M, CAR_L_M = 2.0, 4.6
SHOW_M = SHOW_M_CORE  # o radar aparece quando há carro a até essa distância (22 m)...
HOLD_S = 1.5    # ...e some depois desse tempo sem ninguém perto
FADE_S = 0.3    # duração do fade ao aparecer/sumir
SIDE_EDGE_M = 2.4  # a meia-lua nasce a essa distância lateral do meu carro
_ALERT = {1: "#ffd400", 2: "#ff4a1f"}  # amarelo = atenção, vermelho-alaranjado = perigo (pela distância)


class RadarModule(ModuleWindow):
    PANEL_BG = False

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._smoother = RadarSmoother()
        self._alpha = 0.0
        self._near_t = -1e9  # último instante com carro perto
        self._t = time.monotonic()
        self._connected = False

    def _auto_hide(self) -> bool:
        return bool(self.options.get("auto_hide", True))

    def update_snapshot(self, snap) -> None:
        view = radar_view(snap, get_range(self.options))
        self._smoother.update(view)
        self._connected = bool(snap is not None and snap.connected)
        if view.available and any(rc.distance <= SHOW_M for rc in view.cars):
            self._near_t = time.monotonic()
        self._refresh_animating()
        super().update_snapshot(snap)

    def _target(self) -> float:
        if not self._auto_hide() or self._edit:
            return 1.0  # sempre visível (ou editando o layout: precisa aparecer para posicionar)
        return 1.0 if time.monotonic() - self._near_t <= HOLD_S else 0.0

    def _refresh_animating(self) -> None:
        # movimento fluido enquanto visível; enquanto some/aparece também (fade e tempo de espera)
        self.is_animating = bool(self._connected and (self._alpha > 0.0 or self._target() > 0.0))

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
        if self._alpha <= 0.01:
            return
        p.setOpacity(self._alpha)
        r = min(w, h) / 2 - 4
        cx, cy = w / 2, h / 2
        range_m = get_range(self.options)
        v = self._smoother.frame() if self.snapshot is not None else radar_view(None, range_m)
        self._grid(p, cx, cy, r)  # painel + anéis + cruz
        if not v.available:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(13, True))
            p.drawText(QRectF(cx - r + 12, cy - 30, 2 * r - 24, 60), Qt.AlignCenter | Qt.TextWordWrap,
                       v.message or "SEM DADOS")
            return
        s = r / range_m  # px por metro
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), r - 1, r - 1)
        p.save()
        p.setClipPath(clip)
        for side, level in side_levels(v.cars).items():  # meia-lua do lado do carro emparelhado
            if level:
                self._side_glow(p, cx, cy, r, s, side, level)
        for rc in v.cars:
            if approaching_from_behind(rc):  # faixa de aproximação: do carro dele, para a frente
                self._strip(p, cx, cy, r, s, rc, proximity(rc))
        for rc in sorted(v.cars, key=lambda c: -c.distance):
            self._car(p, cx + rc.x * s, cy - rc.y * s, s, rc, self.snapshot)
        p.restore()
        # meu carro, por cima de tudo
        p.setPen(QPen(QColor(theme.WHITE), 2.0))
        p.setBrush(QColor(theme.GREEN))
        p.drawRoundedRect(QRectF(cx - CAR_W_M * s / 2, cy - CAR_L_M * s / 2, CAR_W_M * s, CAR_L_M * s), 3, 3)
        if not v.lateral_real:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(11, True))
            p.drawText(QRectF(cx - r, cy + r - 22, 2 * r, 18), Qt.AlignCenter, "lado estimado")

    @staticmethod
    def _grid(p: QPainter, cx: float, cy: float, r: float) -> None:
        """Painel redondo translúcido, anel externo, anel do meio e cruz."""
        bg = QColor(theme.PANEL)
        bg.setAlphaF(0.55)
        p.setPen(QPen(QColor(theme.LINE), 2.0))
        p.setBrush(bg)
        p.drawEllipse(QPointF(cx, cy), r, r)
        p.setPen(QPen(QColor(theme.LINE), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r / 2, r / 2)
        p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))

    @staticmethod
    def _side_glow(p: QPainter, cx: float, cy: float, r: float, s: float, side: str, level: int) -> None:
        """Meia-lua que se apaga para fora, com a borda reta rente ao meu carro, do lado do carro emparelhado."""
        sign = -1.0 if side == "left" else 1.0
        ex = cx + sign * SIDE_EDGE_M * s
        rad = max(1.0, r - SIDE_EDGE_M * s)
        col = QColor(_ALERT[level])
        grad = QRadialGradient(QPointF(ex, cy), rad)
        for pos, a in ((0.0, 0.92), (0.55, 0.62), (1.0, 0.0)):
            c = QColor(col)
            c.setAlphaF(a)
            grad.setColorAt(pos, c)
        p.save()
        left, right = (ex, cx + r) if sign > 0 else (cx - r, ex)  # só o lado de fora (a borda reta fica rente ao carro)
        p.setClipRect(QRectF(left, cy - r, right - left, 2 * r), Qt.IntersectClip)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(ex, cy), rad, rad)
        p.restore()

    @staticmethod
    def _strip(p: QPainter, cx: float, cy: float, r: float, s: float, rc, level: int) -> None:
        """Faixa do carro que vem de trás: sai da frente dele, segue em direção à frente e some com fade."""
        x0, y0 = cx + rc.x * s, cy - (rc.y + CAR_L_M / 2) * s
        top = cy - r
        length = max(1.0, y0 - top)
        slope = strip_slope(rc)
        x1, y1 = x0 + slope * length, top
        hw = CAR_W_M * s * 0.45
        col = QColor(_ALERT[level])
        grad = QLinearGradient(QPointF(x0, y0), QPointF(x1, y1))
        c0, c1 = QColor(col), QColor(col)
        c0.setAlphaF(0.9)
        c1.setAlphaF(0.0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.75, c0)
        grad.setColorAt(1.0, c1)
        path = QPainterPath()
        path.moveTo(x0 - hw, y0)
        path.lineTo(x0 + hw, y0)
        path.lineTo(x1 + hw, y1)
        path.lineTo(x1 - hw, y1)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(path)

    @staticmethod
    def _car(p: QPainter, x: float, y: float, s: float, rc, snap) -> None:
        car = rc.car
        level = proximity(rc)
        color = QColor(_ALERT[level] if level else class_style(car.class_name, car.class_color, snap.sim).color)
        p.setPen(QPen(QColor("#050506"), 1.2))
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x - CAR_W_M * s / 2, y - CAR_L_M * s / 2, CAR_W_M * s, CAR_L_M * s), 3, 3)
