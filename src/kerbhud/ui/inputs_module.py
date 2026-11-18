"""Módulo INPUTS: faixa compacta retangular (cantos levemente arredondados) com gráfico embutido.

Da esquerda para a direita: traço do histórico (acelerador, freio, embreagem e,
opcionalmente, direção), barras verticais dos pedais com a porcentagem embaixo,
marcha, velocidade + RPM e volante. Os LEDs de shift light ocupam a borda
superior de ponta a ponta, recortados pelo contorno do módulo.
"""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..core.history import decimate_columns
from ..core.model import Inputs
from ..core.viewmodel import (SHIFT_LED_COUNT, gear_label, get_shift_start, get_trace_s,
                              shift_lights, speed_unit, speed_value, steer_label)
from . import theme
from .module_base import ModuleWindow, make_font
from .plotting import plot_series

_LED_COLORS = [theme.GREEN] * 5 + [theme.RED] * 4 + [theme.BLUE] * 3  # 12 LEDs

# Geometria em unidades de projeto (620 x 112). Margens verticais mínimas: 7 de LEDs
# no topo, 4 de respiro e 3 embaixo.
LED_H, LED_GAP = 7.0, 4.0
TOP, BOTTOM = 11.0, 109.0  # área útil vertical (y)
TRACE = (14.0, TOP, 256.0, BOTTOM - TOP)  # x, y, w, h do gráfico
BAR_X0, BAR_W, BAR_GAP, BAR_Y, BAR_H = 282.0, 26.0, 8.0, TOP, 80.0
LABEL_Y, LABEL_H = BAR_Y + BAR_H + 2.0, 16.0  # % embaixo de cada barra
GEAR = (388.0, TOP, 52.0, BOTTOM - TOP)
SPEED_X, SPEED_W = 448.0, 70.0
WHEEL_C, WHEEL_R, RIM = (566.0, 53.0), 33.0, 9.0  # centro, raio do aro, espessura do aro


DESIGN_W, DESIGN_H, MIN_W = 620.0, 112.0, 470.0


class InputsModule(ModuleWindow):
    """Texto/elementos de tamanho FIXO: ao alargar a janela só o GRÁFICO cresce (e encolhe até um mínimo);
    pedais, marcha, velocidade e volante mantêm o tamanho."""

    CORNER = 8.0  # retângulo com cantos levemente arredondados
    ANCHOR_TOPLEFT = True
    FIXED_SCALE = True

    def layout_size(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        return max(avail_w, MIN_W), DESIGN_H

    def visible_pedals(self) -> list[str]:
        """Barras exibidas, da esquerda para a direita."""
        names = ["brake", "throttle"]
        if self.options.get("show_clutch", True) is not False:
            names.insert(0, "clutch")
        return names

    def paint_content(self, p: QPainter, aw: float, ah: float) -> None:
        snap = self.snapshot
        live = bool(snap and snap.connected and snap.inputs is not None)
        i: Inputs = snap.inputs if live else Inputs()
        units = self.ctx.units
        w, h = max(aw, MIN_W), DESIGN_H
        dx = w - DESIGN_W  # folga horizontal: vai toda para o gráfico

        if not live:
            p.setOpacity(self.opacity * 0.35)  # esmaece o painel enquanto não há dados
        self._shift_lights(p, w, h, i if live else None)
        self._trace(p, live, dx)
        p.save()
        p.translate(dx, 0)  # blocos à direita do gráfico acompanham a borda direita, sem mudar de tamanho
        self._pedals(p, i, live)
        self._gear(p, i, live)
        self._speed_rpm(p, i, live, units)
        self._wheel(p, i, live)
        p.restore()
        if not live:
            p.setOpacity(self.opacity)
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(16, True))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "SEM DADOS")

    # ---- gráfico embutido ---------------------------------------------- #
    def _trace(self, p: QPainter, live: bool, dx: float = 0.0) -> None:
        x, y, w, h = TRACE
        w += dx  # o gráfico absorve a diferença de largura da janela
        p.setPen(Qt.NoPen)
        bg = QColor(theme.BG)
        bg.setAlphaF(0.55)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
        p.setPen(QPen(QColor(theme.LINE), 1))
        for frac in (0.25, 0.5, 0.75):
            gy = y + h * frac
            p.drawLine(QPointF(x + 10, gy), QPointF(x + w - 10, gy))
        if not live:
            return
        seconds = get_trace_s(self.options)
        samples = self.ctx.history.window(seconds)
        if len(samples) < 2:
            return
        px, py, pw, ph = x + 6, y + 6, w - 12, h - 12  # margem interna: 0% e 100% não são cortados
        t1 = samples[-1].t
        t0 = t1 - seconds
        ts = [s.t for s in samples]
        series = []
        if "clutch" in self.visible_pedals():
            series.append(([s.clutch for s in samples], 1.0, 0.0, theme.BLUE, 1.6))
        series.append(([s.brake for s in samples], 1.0, 0.0, theme.RED, 2.2))
        series.append(([s.throttle for s in samples], 1.0, 0.0, theme.GREEN, 2.2))
        if self.options.get("trace_steering") is True:
            series.append(([s.steering for s in samples], 0.5, 0.5, theme.PURPLE, 1.6))
        p.save()
        p.setClipRect(QRectF(x, y, w, h))
        for vals, vmul, voff, color, width in series:
            dts, dvs = decimate_columns(ts, vals, max(1, int(pw)))
            plot_series(p, dts, dvs, vmul, voff, color, px, py, pw, ph, t0, seconds, width)
        p.restore()

    # ---- pedais ---------------------------------------------------------- #
    def _pedals(self, p: QPainter, i: Inputs, live: bool) -> None:
        colors = {"clutch": theme.BLUE, "brake": theme.RED, "throttle": theme.GREEN}
        values = {"clutch": i.clutch, "brake": i.brake, "throttle": i.throttle}
        names = self.visible_pedals()
        total = len(names) * BAR_W + (len(names) - 1) * BAR_GAP
        x0 = BAR_X0 + (3 * BAR_W + 2 * BAR_GAP - total) / 2
        for k, name in enumerate(names):
            x = x0 + k * (BAR_W + BAR_GAP)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.PANEL_ALT))
            p.drawRoundedRect(QRectF(x, BAR_Y, BAR_W, BAR_H), 4, 4)
            v = min(max(values[name], 0.0), 1.0)
            if v > 0:
                fh = max(4.0, BAR_H * v)  # mínimo visível para um toque leve
                p.setBrush(QColor(colors[name]))
                p.drawRoundedRect(QRectF(x, BAR_Y + BAR_H - fh, BAR_W, fh), 4, 4)
            p.setPen(QColor(theme.WHITE if live else theme.GRAY))
            p.setFont(make_font(12, True))
            # o rótulo pode passar um pouco da barra ("100%" é mais largo que ela)
            p.drawText(QRectF(x - BAR_GAP / 2, LABEL_Y, BAR_W + BAR_GAP, LABEL_H),
                       Qt.AlignCenter, f"{v * 100:.0f}%" if live else "--")

    # ---- marcha / velocidade / RPM ------------------------------------- #
    def _gear(self, p: QPainter, i: Inputs, live: bool) -> None:
        x, y, w, h = GEAR
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.PANEL_ALT))
        p.drawRoundedRect(QRectF(x, y, w, h), 6, 6)
        label = gear_label(i.gear) if live else "-"
        if not live:
            color = theme.GRAY
        elif i.gear == 0:
            color = theme.YELLOW
        elif i.gear < 0:
            color = theme.RED
        else:
            color = theme.WHITE
        p.setPen(QColor(color))
        p.setFont(make_font(56, True))
        p.drawText(QRectF(x, y, w, h), Qt.AlignCenter, label)

    def _speed_rpm(self, p: QPainter, i: Inputs, live: bool, units: str) -> None:
        p.setPen(QColor(theme.WHITE if live else theme.GRAY))
        p.setFont(make_font(32, True))
        speed = f"{speed_value(i.speed_ms, units):.0f}" if live else "--"
        p.drawText(QRectF(SPEED_X, 24, SPEED_W, 40), Qt.AlignCenter, speed)
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(13))
        p.drawText(QRectF(SPEED_X, 64, SPEED_W, 16), Qt.AlignCenter, speed_unit(units))
        p.setFont(make_font(12))
        rpm = f"{i.rpm:,.0f}".replace(",", " ") + " rpm" if live else "-- rpm"
        p.drawText(QRectF(SPEED_X - 8, 82, SPEED_W + 16, 16), Qt.AlignCenter, rpm)

    # ---- volante --------------------------------------------------------- #
    def _wheel(self, p: QPainter, i: Inputs, live: bool) -> None:
        cx, cy = WHEEL_C
        r = WHEEL_R
        # Com ângulo em graus (positivo = direita = horário). Sem graus, gira pelo
        # valor normalizado só como indicação visual e não mostra o número.
        angle = i.steering_deg if i.steering_deg is not None else i.steering * 180.0
        color = QColor(theme.WHITE if live else theme.GRAY)
        side = math.radians(18.0)  # raios laterais levemente inclinados para baixo
        sx, sy = (r - 3) * math.cos(side), (r - 3) * math.sin(side)
        p.save()
        p.translate(cx, cy)
        p.rotate(angle if live else 0.0)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, RIM))
        p.drawEllipse(QPointF(0, 0), r, r)  # aro grosso
        p.setPen(QPen(color, 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0, 0), QPointF(-sx, sy))  # raio esquerdo
        p.drawLine(QPointF(0, 0), QPointF(sx, sy))  # raio direito
        p.drawLine(QPointF(0, 0), QPointF(0, r - 3))  # raio inferior
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(0, 0), 9, 9)  # miolo
        p.setPen(QPen(QColor(theme.RED), RIM, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(-3.5, -r), QPointF(3.5, -r))  # marca vermelha no topo do aro
        p.restore()
        p.setPen(QColor(theme.WHITE if live else theme.GRAY))
        p.setFont(make_font(12, True))
        label = steer_label(i.steering_deg) if live else "--"
        p.drawText(QRectF(cx - 36, LABEL_Y, 72, LABEL_H), Qt.AlignCenter, label)

    # ---- shift lights ---------------------------------------------------- #
    def _shift_lights(self, p: QPainter, w: float, h: float, i: Inputs | None) -> None:
        """Fileira de LEDs de ponta a ponta no topo, recortada pelo contorno do módulo."""
        n = SHIFT_LED_COUNT
        lit, flash = shift_lights(i.shift_pct if i else None, i.shift_source if i else None, n,
                                  get_shift_start(self.options))
        blink_on = int(time.monotonic() * 10) % 2 == 0
        led_w = (w - LED_GAP * (n - 1)) / n
        outline = QPainterPath()
        outline.addRoundedRect(QRectF(0, 0, w, h), self.CORNER, self.CORNER)
        p.save()
        p.setClipPath(outline)
        p.setPen(Qt.NoPen)
        for k in range(n):
            if flash:
                color = QColor(theme.BLUE if blink_on else theme.LINE)
            else:
                color = QColor(_LED_COLORS[k] if k < lit else theme.LINE)
            p.setBrush(color)
            p.drawRect(QRectF(k * (led_w + LED_GAP), 0, led_w, LED_H))
        p.restore()
