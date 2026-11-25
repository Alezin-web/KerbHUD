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
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ..core.assists import assist_on, pulse
from ..core.history import downshift_blips
from ..core.history import decimate_columns
from ..core.model import Inputs
from ..core.wheels import get_wheel_image, get_wheel_style, valid_image
from ..core.viewmodel import (SHIFT_LED_COUNT, gear_label, get_shift_start, get_trace_s,
                              shift_lights, speed_unit, speed_value, steer_label)
from . import theme
from .module_base import ModuleWindow, make_font
from .plotting import plot_flag_runs, plot_series

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

    def min_design(self) -> tuple[float, float]:
        return MIN_W, DESIGN_H

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

        alert = live and self.options.get("abs_tc_alert", True) is not False
        abs_on = alert and i.abs_active is True
        tc_on = alert and i.tc_active is True
        lock_on = live and self.options.get("lock_alert", True) is not False and i.lockup is True
        self.is_animating = assist_on(abs_on, tc_on)  # o aviso de ABS/TC pulsa: pede repintura
        if not live:
            p.setOpacity(self.opacity * 0.35)  # esmaece o painel enquanto não há dados
        glow = pulse(time.monotonic()) if self.is_animating else 0.0
        if glow:
            self._assist_tint(p, w, h, glow)
        self._shift_lights(p, w, h, i if live else None)
        self._trace(p, live, dx)
        p.save()
        p.translate(dx, 0)  # blocos à direita do gráfico acompanham a borda direita, sem mudar de tamanho
        self._pedals(p, i, live, abs_on, tc_on, lock_on)
        self._gear(p, i, live)
        self._speed_rpm(p, i, live, units)
        self._wheel(p, i, live)
        p.restore()
        if glow:
            self._assist_border(p, w, h, glow)
        if not live:
            p.setOpacity(self.opacity)
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(16, True))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "SEM DADOS")

    # ---- aviso de ABS / TC ----------------------------------------------- #
    def _assist_tint(self, p: QPainter, w: float, h: float, glow: float) -> None:
        c = QColor(theme.GOLD)
        c.setAlphaF(0.16 * glow)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(0, 0, w, h), self.CORNER, self.CORNER)

    def _assist_border(self, p: QPainter, w: float, h: float, glow: float) -> None:
        c = QColor(theme.GOLD)
        c.setAlphaF(min(1.0, glow))
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(c, 3.0))
        p.drawRoundedRect(QRectF(1.5, 1.5, w - 3, h - 3), self.CORNER, self.CORNER)

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
        px, py, pw, ph = x + 6, y + 13, w - 12, h - 19  # margem interna: 0% e 100% não são cortados; o alto fica para os pontos de travamento
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
        if self.options.get("abs_tc_alert", True) is not False:  # trechos em que o ABS/TC atuou: dourado, na mesma linha
            plot_flag_runs(p, samples, lambda s: s.brake, lambda s: s.abs_on, theme.GOLD, px, py, pw, ph, t0, seconds, 2.6)
            plot_flag_runs(p, samples, lambda s: s.throttle, lambda s: s.tc_on, theme.GOLD, px, py, pw, ph, t0, seconds, 2.6)
        if self.options.get("downshift_marks", True) is not False:  # picos do acelerador ao reduzir a marcha
            blips = downshift_blips(samples)
            plot_flag_runs(p, samples, lambda s: s.throttle, lambda s: id(s) in blips, theme.PURPLE, px, py, pw, ph, t0, seconds, 2.6)
        if self.options.get("lock_alert", True) is not False:  # travamento: pontos azuis FORA das linhas, na faixa do topo
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.BLUE))
            last_col = None
            k = pw / seconds
            for s in samples:
                if s.lock:
                    col = int((s.t - t0) * k // 4)
                    if col != last_col:
                        p.drawEllipse(QPointF(px + (s.t - t0) * k, y + 6.0), 2.6, 2.6)
                        last_col = col
        p.restore()

    # ---- pedais ---------------------------------------------------------- #
    def _pedals(self, p: QPainter, i: Inputs, live: bool, abs_on: bool = False, tc_on: bool = False,
                lock_on: bool = False) -> None:
        colors = {"clutch": theme.BLUE, "brake": theme.GOLD if abs_on else theme.RED,
                  "throttle": theme.GOLD if tc_on else theme.GREEN}
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
            if lock_on and name == "brake":  # roda travando: ponto azul no alto da barra do freio
                p.setPen(QPen(QColor(theme.BG), 1.5))
                p.setBrush(QColor(theme.BLUE))
                p.drawEllipse(QPointF(x + BAR_W / 2, BAR_Y + 8.0), 5.5, 5.5)
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
        style = get_wheel_style(self.options)
        p.save()
        p.translate(cx, cy)
        p.rotate(angle if live else 0.0)
        if style == "hidden" or (style == "custom" and self._draw_custom_wheel(p, r, live)):
            pass
        elif style == "gt":
            self._wheel_gt(p, r, color)
        elif style == "formula":
            self._wheel_formula(p, r, color)
        else:
            self._wheel_classic(p, r, color, sx, sy)
        p.restore()
        p.setPen(QColor(theme.WHITE if live else theme.GRAY))
        p.setFont(make_font(12, True))
        label = steer_label(i.steering_deg) if live else "--"
        p.drawText(QRectF(cx - 36, LABEL_Y, 72, LABEL_H), Qt.AlignCenter, label)

    # estilos de volante (genéricos, desenhados aqui) --------------------------- #
    @staticmethod
    def _wheel_classic(p: QPainter, r: float, color: QColor, sx: float, sy: float) -> None:
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

    @staticmethod
    def _wheel_gt(p: QPainter, r: float, color: QColor) -> None:
        """Aro redondo com a base reta (volante de GT) e dois raios."""
        rim = QPainterPath()
        rim.arcTo(QRectF(-r, -r, 2 * r, 2 * r), 315, 270)  # do canto inferior direito ao inferior esquerdo, pelo alto
        rim.closeSubpath()  # a corda que fecha é a base reta
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(color, RIM, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(rim)
        p.setPen(QPen(color, 7, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(0, 0), QPointF(-(r - 3), 0))
        p.drawLine(QPointF(0, 0), QPointF(r - 3, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(-11, -9, 22, 18), 5, 5)  # miolo com os botões
        p.setPen(QPen(QColor(theme.RED), RIM, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(-3.5, -r), QPointF(3.5, -r))

    @staticmethod
    def _wheel_formula(p: QPainter, r: float, color: QColor) -> None:
        """Volante retangular de monoposto: corpo com tela/botões e duas empunhaduras."""
        hw, hh = r * 0.92, r * 0.52
        p.setPen(QPen(color, 4))
        fill = QColor(theme.PANEL_ALT)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(-hw, -hh, 2 * hw, 2 * hh), 9, 9)
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(-hw - 4, -hh - 2, 9, 2 * hh + 4), 4, 4)  # empunhadura esquerda
        p.drawRoundedRect(QRectF(hw - 5, -hh - 2, 9, 2 * hh + 4), 4, 4)   # empunhadura direita
        screen = QColor(theme.BG)
        p.setBrush(screen)
        p.drawRoundedRect(QRectF(-hw * 0.42, -hh * 0.62, hw * 0.84, hh * 0.78), 3, 3)  # tela
        p.setBrush(color)
        for k in (-2, -1, 0, 1, 2):
            p.drawEllipse(QPointF(k * hw * 0.3, hh * 0.58), 2.6, 2.6)  # botões
        p.setPen(QPen(QColor(theme.RED), 4, Qt.SolidLine, Qt.FlatCap))
        p.drawLine(QPointF(-3.5, -hh), QPointF(3.5, -hh))

    def _draw_custom_wheel(self, p: QPainter, r: float, live: bool) -> bool:
        """Desenha a imagem escolhida (já com a rotação aplicada). False se não houver imagem válida (cai no clássico)."""
        pix = self._custom_pixmap(get_wheel_image(self.options))
        if pix is None:
            return False
        w, h = float(pix.width()), float(pix.height())
        k = (2 * r) / max(w, h)
        p.setOpacity(self.effective_opacity * (1.0 if live else 0.35))
        p.drawPixmap(QRectF(-w * k / 2, -h * k / 2, w * k, h * k), pix, QRectF(0, 0, w, h))
        return True

    def _custom_pixmap(self, path: str):
        """Imagem do volante em cache (relê quando o caminho muda). None se não existir/for inválida."""
        cached = getattr(self, "_wheel_cache", None)
        if cached is not None and cached[0] == path:
            return cached[1]
        pix = None
        if valid_image(path):
            try:
                loaded = QPixmap(path)
                pix = None if loaded.isNull() else loaded
            except Exception:  # noqa: BLE001 - imagem corrompida: usa o volante padrão
                pix = None
        self._wheel_cache = (path, pix)
        return pix

    # ---- shift lights ---------------------------------------------------- #
    def _shift_lights(self, p: QPainter, w: float, h: float, i: Inputs | None) -> None:
        """Fileira de LEDs de ponta a ponta no topo, recortada pelo contorno do módulo."""
        n = SHIFT_LED_COUNT
        lit, flash = shift_lights(i.shift_pct if i else None, i.shift_source if i else None, n,
                                  get_shift_start(self.options), i.shift_blink if i else None)
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
