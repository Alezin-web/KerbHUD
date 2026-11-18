"""Módulo AVARIAS: carro visto de cima com a saúde (100% = sem avarias, desce com os danos) no centro.

LMU: as 8 regiões (4 cantos como rodas e 4 lados como barras) ficam verde / amarelo / vermelho. iRacing: o simulador
não publica avarias por região, então não há percentual: só os tempos de reparo e de reboque.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from ..core.damage import damage_view, format_seconds
from ..core.model import DAMAGE_ZONES
from ..core.i18n import tr
from . import theme
from .module_base import ModuleWindow, make_font

HEADER_H = 28.0
_LEVEL = {"ok": theme.GREEN, "warn": theme.YELLOW, "danger": theme.RED}
_SEV = (theme.GREEN, theme.YELLOW, theme.RED)  # 0 nenhuma, 1 leve, 2 forte
_NEUTRAL = "#3a3a44"


class DamageModule(ModuleWindow):
    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        v = damage_view(self.snapshot)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawRect(QRectF(0, 0, w, 3))
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(14, True))
        p.drawText(QRectF(0, 4, w, HEADER_H - 4), Qt.AlignCenter, "CAR DAMAGE")
        if not v.has_data:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(14, True))
            p.drawText(QRectF(10, HEADER_H, w - 20, h - HEADER_H), Qt.AlignCenter, v.message or "SEM DADOS")
            return
        y = self._car(p, w, HEADER_H + 6, v)
        p.setPen(QColor(_LEVEL[v.level]))
        p.setFont(make_font(14, True))
        p.drawText(QRectF(8, y, w - 16, 22), Qt.AlignCenter, v.headline)
        y += 24
        for tag, on, color in ((tr("PEÇA SOLTA"), v.detached, theme.RED), (tr("SUPERAQUECENDO"), v.overheating, theme.YELLOW)):
            if on:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(16, y, w - 32, 20), 3, 3)
                p.setPen(QColor("#111111"))
                p.setFont(make_font(12, True))
                p.drawText(QRectF(16, y, w - 32, 20), Qt.AlignCenter, tag)
                y += 24
        for label, secs in v.repair_lines:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(12, True))
            p.drawText(QRectF(14, y, w * 0.6, 22), Qt.AlignVCenter | Qt.AlignLeft, label)
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(16, True))
            p.drawText(QRectF(w * 0.5, y, w * 0.5 - 14, 22), Qt.AlignVCenter | Qt.AlignRight, format_seconds(secs))
            y += 24

    @staticmethod
    def _car(p: QPainter, w: float, y0: float, v) -> float:
        zones = v.zones or [None] * len(DAMAGE_ZONES)
        col = {z: QColor(_SEV[s] if s is not None else _NEUTRAL) for z, s in zip(DAMAGE_ZONES, zones)}
        cx, bw, bh = w / 2, 76.0, 150.0
        top = y0 + 6
        # corpo
        p.setPen(QPen(QColor("#6b6b75"), 2.0))
        p.setBrush(QColor("#17171c"))
        p.drawRoundedRect(QRectF(cx - bw / 2, top, bw, bh), 18, 18)
        # rodas (cantos)
        ww, wh = 18.0, 40.0
        for name, sx, sy in (("front_left", -1, 0), ("front_right", 1, 0), ("rear_left", -1, 1), ("rear_right", 1, 1)):
            x = cx + sx * (bw / 2 + 4) - (ww if sx < 0 else 0)
            yy = top + 8 if sy == 0 else top + bh - 8 - wh
            p.setPen(Qt.NoPen)
            p.setBrush(col[name])
            p.drawRoundedRect(QRectF(x, yy, ww, wh), 4, 4)
        # lados (barras entre as rodas)
        side_len = bh - 2 * (8 + wh) - 10
        p.setBrush(col["left"])
        p.drawRoundedRect(QRectF(cx - bw / 2 + 5, top + 8 + wh + 5, 7, side_len), 3, 3)
        p.setBrush(col["right"])
        p.drawRoundedRect(QRectF(cx + bw / 2 - 12, top + 8 + wh + 5, 7, side_len), 3, 3)
        p.setBrush(col["front"])
        p.drawRoundedRect(QRectF(cx - 18, top + 5, 36, 7), 3, 3)
        p.setBrush(col["rear"])
        p.drawRoundedRect(QRectF(cx - 18, top + bh - 12, 36, 7), 3, 3)
        # percentual no centro (100% = sem avarias; só existe quando há regiões)
        p.setFont(make_font(22, True))
        if v.health_pct is None:
            p.setPen(QColor(theme.GRAY))
            txt = "-"
        else:
            p.setPen(QColor(_LEVEL[v.level]))
            txt = f"{v.health_pct:.0f}%"
        p.drawText(QRectF(cx - bw / 2 + 12, top + bh / 2 - 16, bw - 24, 32), Qt.AlignCenter, txt)
        return top + bh + 8
