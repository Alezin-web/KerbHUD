"""Módulo COMBUSTÍVEL: barra do tanque, tabela de consumo (média/máximo/mínimo) e as últimas voltas.

Layout: à esquerda a barra (vazio `E` ... capacidade) com o nível no centro e a tabela USO / VOLTAS / ABASTECER / FIM
para o consumo médio, máximo e mínimo; à direita as últimas voltas medidas (USADO e diferença para a média). No LMU,
carros com energia virtual (NRG) ganham uma linha de resumo no rodapé.
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from ..core.fuel import FuelTracker, Meter, get_reserve
from ..core.i18n import tr
from . import theme
from .module_base import ModuleWindow, make_font

HEADER_H = 40.0
ROW_H = 40.0
SPLIT = 0.66  # fração da largura ocupada pela barra + tabela; o resto é o histórico de voltas
_STATE_COLOR = {"ok": theme.GREEN, "warn": theme.YELLOW, "danger": theme.RED, "nodata": theme.GRAY}


def _num(v, digits: int = 1) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


class FuelModule(ModuleWindow):
    REPAINT_HZ = 10  # muda devagar: não precisa redesenhar a cada quadro da tela
    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._tracker = FuelTracker()
        self._view = None

    def update_snapshot(self, snap) -> None:
        # mede o consumo a CADA snapshot (a volta é detectada na virada do contador), não só quando redesenha
        self._view = self._tracker.update(snap, get_reserve(self.options))
        super().update_snapshot(snap)

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        view = self._view if self.snapshot is not None else None
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawRect(QRectF(0, 0, w, 3))
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(22, True))
        p.drawText(QRectF(0, 4, w, HEADER_H - 4), Qt.AlignCenter, tr("COMBUSTÍVEL"))
        if view is None or not view.available:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(14, True))
            p.drawText(QRectF(10, HEADER_H, w - 20, h - HEADER_H), Qt.AlignCenter,
                       view.message if view else "SEM DADOS")
            return
        main = view.fuel if view.fuel is not None else view.energy
        left_w = w * SPLIT
        y = self._bar(p, 12, HEADER_H + 6, left_w - 20, main)
        self._table(p, 12, y + 4, left_w - 20, main)
        self._history(p, left_w, HEADER_H + 4, w - left_w - 10, main)
        if view.fuel is not None and view.energy is not None:
            self._energy_line(p, w, h, view.energy)
        elif view.laps_to_go is not None:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(20, True))
            p.drawText(QRectF(12, h - 38, w - 24, 34), Qt.AlignVCenter | Qt.AlignLeft,
                       tr("Voltas até o fim (estim.): {}").format(f"{view.laps_to_go:.1f}"))

    @staticmethod
    def _bar(p: QPainter, x: float, y: float, bw: float, m: Meter) -> float:
        color = QColor(_STATE_COLOR[m.state])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.LINE))
        p.drawRect(QRectF(x, y, bw, 30))
        if m.pct is not None:
            p.setBrush(color)
            p.drawRect(QRectF(x, y, bw * m.pct, 30))
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(19, True))
        p.drawText(QRectF(x, y + 32, 36, 24), Qt.AlignVCenter | Qt.AlignLeft, "E")
        cap = "" if not m.capacity else f"{m.capacity:g}{'L' if m.unit == 'L' else '%'}"
        p.drawText(QRectF(x + bw - 80, y + 32, 80, 24), Qt.AlignVCenter | Qt.AlignRight, cap)
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(28, True))
        txt = "-" if m.level is None else f"{m.level:.1f} {m.unit}"
        p.drawText(QRectF(x, y + 30, bw, 36), Qt.AlignCenter, txt)
        return y + 68

    @staticmethod
    def _table(p: QPainter, x: float, y: float, tw: float, m: Meter) -> None:
        cols = ("USO", "VOLTAS", "ABAST.", "FIM")
        label_w = 62.0
        cw = (tw - label_w) / len(cols)
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(17, True))
        for i, c in enumerate(cols):
            p.drawText(QRectF(x + label_w + i * cw, y, cw, 26), Qt.AlignCenter, c)
        y += 30
        rows = ((tr("MÉD"), m.per_lap), (tr("MÁX"), m.max_per_lap), (tr("MÍN"), m.min_per_lap))
        for n, (label, usage) in enumerate(rows):
            if n == 0:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(theme.PANEL_ALT))
                p.drawRect(QRectF(x - 4, y, tw + 8, ROW_H))
            laps, add, finish = m.scenario(usage)
            vals = (_num(usage), _num(laps), _num(add), _num(finish))
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(18, True))
            p.drawText(QRectF(x, y, label_w, ROW_H), Qt.AlignVCenter | Qt.AlignLeft, label)
            for i, v in enumerate(vals):
                is_add = i == 2 and add is not None and add > 0
                p.setPen(QColor(_STATE_COLOR[m.state] if is_add else theme.WHITE))
                p.setFont(make_font(27, True))
                p.drawText(QRectF(x + label_w + i * cw, y, cw, ROW_H), Qt.AlignCenter, v)
            y += ROW_H

    @staticmethod
    def _history(p: QPainter, x: float, y: float, hw: float, m: Meter) -> None:
        cw = hw / 3
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(17, True))
        for i, c in enumerate(("VOLTA", "USADO", "DIF")):
            p.drawText(QRectF(x + i * cw, y, cw, 26), Qt.AlignCenter, c)
        y += 38
        if not m.history:
            p.setFont(make_font(17, True))
            p.drawText(QRectF(x, y, hw, 100), Qt.AlignTop | Qt.AlignHCenter | Qt.TextWordWrap, "medindo...\numa volta completa")
            return
        for lap, used, diff in m.history[:5]:
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(25, True))
            p.drawText(QRectF(x, y, cw, ROW_H), Qt.AlignCenter, "-" if lap is None else str(lap))
            p.drawText(QRectF(x + cw, y, cw, ROW_H), Qt.AlignCenter, f"{used:.1f}")
            p.setPen(QColor(theme.YELLOW if diff > 0.05 else theme.GREEN if diff < -0.05 else theme.GRAY))
            p.drawText(QRectF(x + 2 * cw, y, cw, ROW_H), Qt.AlignCenter, f"{diff:+.1f}" if abs(diff) >= 0.05 else "0.0")
            y += ROW_H

    @staticmethod
    def _energy_line(p: QPainter, w: float, h: float, e: Meter) -> None:
        p.setPen(QColor(_STATE_COLOR[e.state]))
        p.setFont(make_font(21, True))
        add = "" if e.add is None else (f"  ·  abastecer {e.add:.0f}%" if e.add > 0 else "  ·  energia OK")
        per = "medindo..." if not e.per_lap else f"{e.per_lap:.1f}%/volta"
        p.drawText(QRectF(12, h - 38, w - 24, 34), Qt.AlignVCenter | Qt.AlignLeft,
                   f"NRG {e.level:.0f}%  ·  {per}{add}")
