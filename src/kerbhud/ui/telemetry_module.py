"""Módulo TELEMETRIA: gráficos em tempo real do histórico recente.

Faixas empilhadas (pedais, velocidade, RPM, direção). Cada canal pode ser ligado
ou desligado; o histórico mostrado (5 a 60 s) é configurável.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ..core.history import Sample, decimate_columns
from ..core.viewmodel import (CHANNEL_SHORT, enabled_lanes, get_channels, get_history_s,
                              lane_layout, nice_ceiling, speed_unit, speed_value, steer_label)
from ..core.i18n import tr
from . import theme
from .module_base import ModuleWindow, make_font
from .plotting import plot_flag_runs, plot_series

COLORS = {"throttle": theme.GREEN, "brake": theme.RED, "clutch": theme.BLUE,
          "speed": theme.WHITE, "rpm": theme.YELLOW, "steering": theme.PURPLE}
PLOT_X, PLOT_Y, GUTTER, BOTTOM = 8.0, 8.0, 84.0, 18.0


class TelemetryModule(ModuleWindow):
    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        snap = self.snapshot
        live = bool(snap and snap.connected and snap.inputs is not None)
        channels = get_channels(self.options)
        seconds = get_history_s(self.options)
        lanes = enabled_lanes(channels)
        plot_w = w - PLOT_X - GUTTER - 8
        plot_h = h - PLOT_Y - BOTTOM
        if not lanes:
            self._message(p, w, h, "NENHUM CANAL ATIVO")
            return
        samples = self.ctx.history.window(seconds) if live else []
        rects = lane_layout(lanes, PLOT_X, PLOT_Y, plot_w, plot_h)

        if len(samples) < 2:
            self._draw_frames(p, lanes, rects)
            self._message(p, w, h, tr("AGUARDANDO TELEMETRIA"))
            self._time_axis(p, w, h, seconds)
            return

        t1 = samples[-1].t
        t0 = t1 - seconds
        units = self.ctx.units
        ts = [s.t for s in samples]
        kmult = 2.2369362921 if units == "mph" else 3.6
        cols = {
            "throttle": ([s.throttle for s in samples], 1.0, 0.0),
            "brake": ([s.brake for s in samples], 1.0, 0.0),
            "clutch": ([s.clutch for s in samples], 1.0, 0.0),
            "steering": ([s.steering for s in samples], 0.5, 0.5),  # -1..1 -> 0..1
        }
        for lane_id, chans, _wt in lanes:
            x, y, lw, lh = rects[lane_id]
            self._draw_lane_bg(p, x, y, lw, lh, lane_id)
            scale = 1.0
            if lane_id == "speed":
                speed_ms = [s.speed_ms for s in samples]
                scale = nice_ceiling(max(speed_ms) * kmult, 50.0)
                cols["speed"] = (speed_ms, kmult / scale, 0.0)
            elif lane_id == "rpm":
                rpm = [s.rpm for s in samples]
                scale = nice_ceiling(max(samples[-1].rpm_max or 0.0, max(rpm)), 1000.0)
                cols["rpm"] = (rpm, 1.0 / scale, 0.0)
            p.save()
            p.setClipRect(QRectF(x, y, lw, lh))
            for ch in chans:
                vals, vmul, voff = cols[ch]
                dts, dvs = decimate_columns(ts, vals, max(1, int(lw)))
                plot_series(p, dts, dvs, vmul, voff, COLORS[ch], x, y, lw, lh, t0, seconds)
                if self.options.get("abs_tc_alert", True) is not False and ch in ("brake", "throttle"):
                    flag = (lambda s: s.abs_on) if ch == "brake" else (lambda s: s.tc_on)  # ABS no freio, TC no acelerador
                    plot_flag_runs(p, samples, lambda s, c=ch: getattr(s, c), flag, theme.GOLD, x, y, lw, lh, t0, seconds)
            p.restore()
            self._lane_labels(p, lane_id, x, y, lh, scale, units)
        self._gutter(p, lanes, rects, samples[-1], units, plot_w)
        self._time_axis(p, w, h, seconds)

    # ---- desenho -------------------------------------------------------- #
    def _draw_frames(self, p: QPainter, lanes, rects) -> None:
        for lane_id, _c, _w in lanes:
            x, y, lw, lh = rects[lane_id]
            self._draw_lane_bg(p, x, y, lw, lh, lane_id)

    @staticmethod
    def _draw_lane_bg(p: QPainter, x: float, y: float, lw: float, lh: float, lane_id: str) -> None:
        p.setPen(Qt.NoPen)
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.8)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(x, y, lw, lh), 4, 4)
        p.setBrush(Qt.NoBrush)
        grid = QPen(QColor(theme.LINE), 1)
        p.setPen(grid)
        for frac in (0.0, 0.5, 1.0):
            gy = y + lh * (1 - frac)
            gy = min(max(gy, y + 0.5), y + lh - 0.5)
            p.drawLine(QPointF(x, gy), QPointF(x + lw, gy))
        if lane_id == "steering":  # linha central mais visível: volante reto
            p.setPen(QPen(QColor(theme.GRAY), 1, Qt.DashLine))
            cy = y + lh / 2
            p.drawLine(QPointF(x, cy), QPointF(x + lw, cy))

    @staticmethod
    def _lane_labels(p: QPainter, lane_id: str, x: float, y: float, lh: float,
                     scale: float, units: str) -> None:
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(10))
        if lane_id == "speed":
            p.drawText(QRectF(x + 4, y + 1, 90, 12), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{scale:.0f} {speed_unit(units)}")
        elif lane_id == "rpm":
            p.drawText(QRectF(x + 4, y + 1, 90, 12), Qt.AlignLeft | Qt.AlignVCenter, f"{scale:.0f} rpm")
        elif lane_id == "pedals":
            p.drawText(QRectF(x + 4, y + 1, 90, 12), Qt.AlignLeft | Qt.AlignVCenter, "100%")

    def _gutter(self, p: QPainter, lanes, rects, last: Sample, units: str, plot_w: float) -> None:
        gx = PLOT_X + plot_w + 8
        for lane_id, chans, _wt in lanes:
            x, y, lw, lh = rects[lane_id]
            n = len(chans)
            row_h = min(18.0, lh / max(n, 1))
            top = y + (lh - row_h * n) / 2
            for k, ch in enumerate(chans):
                p.setPen(QColor(COLORS[ch]))
                p.setFont(make_font(12, True))
                rect = QRectF(gx, top + k * row_h, GUTTER, row_h)
                p.drawText(rect, Qt.AlignLeft | Qt.AlignVCenter, CHANNEL_SHORT[ch])
                p.setPen(QColor(theme.WHITE))
                p.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, self._value_text(ch, last, units))

    @staticmethod
    def _value_text(ch: str, s: Sample, units: str) -> str:
        if ch == "throttle":
            return f"{s.throttle * 100:.0f}%"
        if ch == "brake":
            return f"{s.brake * 100:.0f}%"
        if ch == "clutch":
            return f"{s.clutch * 100:.0f}%"
        if ch == "speed":
            return f"{speed_value(s.speed_ms, units):.0f}"
        if ch == "rpm":
            return f"{s.rpm:.0f}"
        return steer_label(s.steering_deg) or f"{s.steering * 100:+.0f}%"

    @staticmethod
    def _time_axis(p: QPainter, w: float, h: float, seconds: float) -> None:
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(10))
        left = PLOT_X
        right = w - GUTTER - 8
        p.drawText(QRectF(left, h - BOTTOM + 2, 80, 14), Qt.AlignLeft | Qt.AlignVCenter, f"-{seconds:.0f} s")
        p.drawText(QRectF(right - 80, h - BOTTOM + 2, 80, 14), Qt.AlignRight | Qt.AlignVCenter, "agora")

    @staticmethod
    def _message(p: QPainter, w: float, h: float, text: str) -> None:
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(16, True))
        p.drawText(QRectF(0, 0, w - GUTTER, h), Qt.AlignCenter, text)
