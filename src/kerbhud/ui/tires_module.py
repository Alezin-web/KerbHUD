"""Módulo PNEUS: o carro visto de cima (como o Car Damage), com os quatro pneus nas pontas e, ao lado de cada um, o que
interessa: a TEMPERATURA (média grande + as três zonas da banda) e, menor, o desgaste (número e barra).

* O pneu desenhado tem três faixas verticais (esquerda/centro/direita da banda), na cor da temperatura da zona
  (azul = fria, verde = ideal, lima/amarelo/laranja/vermelho = quente).
* Temperatura: iRacing lê a da carcaça (ao vivo na pista; se não houver, a de superfície); LMU, a de cada zona.
* Desgaste: o número é o da zona mais gasta (100% = novo) e a barra tem uma faixa por zona quando o simulador informa
  por zona (iRacing); o LMU informa um valor só por roda (barra inteira).
* Embaixo, discreta, a pressão (unidade em Bandeja > Pneus). No meio do carro, a volta atual.
Roda furada/solta aparece em vermelho. Sem dados do simulador, nada é inventado.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ..core.i18n import tr
from ..core.tireview import format_pressure, get_pressure_unit, tire_view
from . import theme
from .module_base import ModuleWindow, make_font

HEADER_H = 28.0
TIRE_W = 18.0
_POS = {"fl": (0, 0), "fr": (1, 0), "rl": (0, 1), "rr": (1, 1)}
_WEAR = {"ok": theme.GREEN, "warn": theme.YELLOW, "danger": theme.RED, "nodata": "#3a3a44"}


def _wear_color(pct) -> str:
    if pct is None:
        return _WEAR["nodata"]
    return _WEAR["ok"] if pct >= 60 else (_WEAR["warn"] if pct >= 30 else _WEAR["danger"])


class TiresModule(ModuleWindow):
    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        v = tire_view(self.snapshot)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawRect(QRectF(0, 0, w, 3))
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(14, True))
        p.drawText(QRectF(0, 4, w, HEADER_H - 4), Qt.AlignCenter, "PNEUS" + (f"  ·  {v.compound}" if v.compound else "")
                   + (f"  ·  {tr('ÚLTIMA LEITURA')}" if v.stale else ""))
        if not v.has_data:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(14, True))
            p.drawText(QRectF(10, HEADER_H, w - 20, h - HEADER_H), Qt.AlignCenter, v.message or "SEM DADOS")
            return
        unit = get_pressure_unit(self.options)
        top = HEADER_H + 4
        area_h = h - top - 8
        car_w = max(46.0, min(70.0, w * 0.17))
        cx = w / 2
        self._car(p, cx, top, car_w, area_h, v.lap)
        row_h = area_h / 2
        for corner, (sx, sy) in _POS.items():
            y = top + sy * row_h
            tire_x = cx - car_w / 2 - 4 - TIRE_W if sx == 0 else cx + car_w / 2 + 4
            info_x0, info_x1 = (8.0, tire_x - 7) if sx == 0 else (tire_x + TIRE_W + 7, w - 8)
            self._tire(p, tire_x, y + 5, TIRE_W, row_h - 10, v.cells[corner])
            self._info(p, info_x0, y + 5, info_x1 - info_x0, row_h - 10, v.cells[corner], unit)

    @staticmethod
    def _car(p: QPainter, cx: float, top: float, cw: float, ch: float, lap) -> None:
        p.setPen(QPen(QColor("#6b6b75"), 2.0))
        p.setBrush(QColor("#17171c"))
        p.drawRoundedRect(QRectF(cx - cw / 2, top + 2, cw, ch - 4), 18, 18)
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(10, True))
        p.drawText(QRectF(cx - cw / 2, top + ch / 2 - 22, cw, 14), Qt.AlignCenter, "VOLTA")
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(24, True))
        p.drawText(QRectF(cx - cw / 2, top + ch / 2 - 8, cw, 30), Qt.AlignCenter, "-" if lap is None else str(lap))

    @staticmethod
    def _tire(p: QPainter, x: float, y: float, tw: float, th: float, c) -> None:
        """Pneu com três faixas verticais, na cor da temperatura de cada zona."""
        seg = tw / 3
        p.setPen(Qt.NoPen)
        for i in range(3):
            p.setBrush(QColor(c.temp_colors[i]))
            p.drawRoundedRect(QRectF(x + i * seg + 0.5, y, seg - 1.0, th), 2.5, 2.5)
        if c.flat or c.detached:
            p.setPen(QPen(QColor(theme.RED), 2.5))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(x - 2, y - 2, tw + 4, th + 4), 5, 5)

    @staticmethod
    def _info(p: QPainter, x: float, y: float, iw: float, ih: float, c, unit: str) -> None:
        """TEMPERATURA em destaque (média grande + as três zonas), desgaste menor embaixo e a pressão."""
        # temperatura: número grande na cor da temperatura
        t = c.temp_c
        p.setPen(QColor(c.temp_colors[1] if t is not None else theme.GRAY))
        p.setFont(make_font(22, True))
        p.drawText(QRectF(x, y, iw * 0.62, 26), Qt.AlignVCenter | Qt.AlignLeft, "-" if t is None else f"{t:.0f}°C")
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(10, True))
        p.drawText(QRectF(x + iw * 0.5, y + 2, iw * 0.5, 22), Qt.AlignVCenter | Qt.AlignRight, "TEMP.")
        # as três zonas da banda (esquerda / centro / direita)
        cy = y + 28
        chip_w = (iw - 2 * 3.0) / 3
        chip_h = 18.0
        for i in range(3):
            cx = x + i * (chip_w + 3.0)
            col = QColor(c.temp_colors[i])
            fill = QColor(col)
            fill.setAlphaF(0.2)
            p.setPen(QPen(col, 1.2))
            p.setBrush(fill)
            p.drawRoundedRect(QRectF(cx, cy, chip_w, chip_h), 4, 4)
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(11, True))
            z = c.temps[i]
            p.drawText(QRectF(cx, cy, chip_w, chip_h), Qt.AlignCenter, "-" if z is None else f"{z:.0f}°")
        # desgaste (secundário): número pequeno + barra fina por zona
        wy = cy + chip_h + 4
        worst = c.worst_wear
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(10, True))
        p.drawText(QRectF(x, wy, iw * 0.5, 13), Qt.AlignVCenter | Qt.AlignLeft, "DESG.")
        p.setPen(QColor(_wear_color(worst) if worst is not None else theme.GRAY))
        p.setFont(make_font(11, True))
        p.drawText(QRectF(x + iw * 0.4, wy, iw * 0.6, 13), Qt.AlignVCenter | Qt.AlignRight,
                   "-" if worst is None else f"{worst:.0f}%")
        by = wy + 14
        zones = 3 if c.zoned else 1
        gap = 2.0
        zw = (iw - gap * (zones - 1)) / zones
        p.setPen(Qt.NoPen)
        for i in range(zones):
            zx = x + i * (zw + gap)
            p.setBrush(QColor(0, 0, 0, 130))
            p.drawRoundedRect(QRectF(zx, by, zw, 4), 2, 2)
            val = c.wears[i] if c.zoned else c.wears[1]
            if val is not None:
                p.setBrush(QColor(_wear_color(val)))
                p.drawRoundedRect(QRectF(zx, by, zw * max(0.0, min(1.0, val / 100.0)), 4), 2, 2)
        # pressão (discreta) ou aviso de roda furada/solta
        py = by + 8
        if c.flat or c.detached:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.RED))
            p.drawRoundedRect(QRectF(x, py, iw, 16), 3, 3)
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(11, True))
            p.drawText(QRectF(x, py, iw, 16), Qt.AlignCenter, "FURADO" if c.flat else "SOLTO")
        elif c.pressure_kpa is not None and ih >= py - y + 12:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(10, True))
            p.drawText(QRectF(x, py, iw, 14), Qt.AlignCenter, f"{format_pressure(c.pressure_kpa, unit)} {unit}")
