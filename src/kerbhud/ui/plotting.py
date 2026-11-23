"""Desenho de séries temporais compartilhado (Inputs e Telemetria)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen


def plot_series(p: QPainter, ts, vs, vmul: float, voff: float, color: str,
                x: float, y: float, w: float, h: float, t0: float, seconds: float,
                width: float = 2.0) -> None:
    """Traça `vs` (já decimado) em (x, y, w, h). valor*vmul+voff é normalizado em 0..1."""
    if not ts:
        return
    path = QPainterPath()
    k = w / seconds
    bottom = y + h
    it = zip(ts, vs)
    t, v = next(it)
    v = v * vmul + voff
    path.moveTo(x + (t - t0) * k, bottom - (0.0 if v < 0.0 else 1.0 if v > 1.0 else v) * h)
    for t, v in it:
        v = v * vmul + voff
        path.lineTo(x + (t - t0) * k, bottom - (0.0 if v < 0.0 else 1.0 if v > 1.0 else v) * h)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)


def plot_flag_runs(p: QPainter, samples, value_of, flag_of, color: str,
                   x: float, y: float, w: float, h: float, t0: float, seconds: float, width: float = 2.4) -> None:
    """Repinta, por cima da linha, só os trechos em que `flag_of(amostra)` é verdadeiro (ex.: ABS atuando) na cor `color`.

    Usa as amostras cruas (os trechos marcados são curtos), então não depende da decimação da linha base."""
    k = w / seconds
    bottom = y + h
    path = QPainterPath()
    open_run = False
    any_run = False
    for s in samples:
        if flag_of(s):
            v = value_of(s)
            px, py = x + (s.t - t0) * k, bottom - (0.0 if v < 0.0 else 1.0 if v > 1.0 else v) * h
            if open_run:
                path.lineTo(px, py)
            else:
                path.moveTo(px, py)
                path.lineTo(px + 0.01, py)  # um ponto isolado também aparece
                open_run = True
                any_run = True
        else:
            open_run = False
    if not any_run:
        return
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.drawPath(path)
