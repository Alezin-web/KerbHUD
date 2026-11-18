"""Módulo TRACK MAP: traçado real do circuito com todos os carros.

O traçado é gravado numa volta do piloto (ver `core/trackmap.py`) e salvo por pista. Enquanto grava mostra o
progresso. Meu carro: círculo branco maior com contorno; demais carros: ponto na cor da classe com o número.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from ..core.classes import class_style, text_on
from ..core.smooth import PointSmoother
from ..core.model import CAP_PLAYER_XY_ESTIMATED
from ..core.trackmap import MapCar, TrackRecorder, TrackStore, map_cars
from ..core.i18n import tr
from . import theme
from .module_base import ModuleWindow, fit_font, make_font

PAD = 22.0
HEADER_H = 0.0  # sem cabeçalho nem quadro: só o mapa
DOT_R, ME_R = 10.0, 12.0


class TrackMapModule(ModuleWindow):
    PANEL_BG = False

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        store = TrackStore(self.ctx.tracks_dir) if getattr(self.ctx, "tracks_dir", None) else None
        self.recorder = TrackRecorder(store)
        self._demo_recorder = TrackRecorder(None)  # o DEMO nunca grava traçado em disco
        self._fit_cache: tuple | None = None
        self._shape = None
        self._rec = self.recorder
        self._smoother = PointSmoother()
        self._last_cars: list[MapCar] = []

    def update_snapshot(self, snap) -> None:
        # grava o traçado a CADA snapshot (não só quando a janela é redesenhada): a volta de gravação precisa de amostras densas
        rec = self._demo_recorder if snap.is_demo else self.recorder
        self._shape = rec.update(snap) if snap.connected else None
        self._rec = rec
        if self._shape is not None:  # posições de todos os carros; o desenho as suaviza entre as atualizações do jogo
            self._last_cars = map_cars(snap, self._shape)
            self._smoother.update({mc.car.idx: (mc.x, mc.y) for mc in self._last_cars})
        else:
            self._last_cars = []
            self._smoother.reset()
        self.is_animating = bool(self._last_cars)  # repinta a cada ciclo: movimento fluido
        super().update_snapshot(snap)

    # ---- opções ---------------------------------------------------------- #
    def _mirror(self) -> bool:
        return bool(self.options.get("mirror", False))

    def _label_mode(self) -> str:
        """"class_pos" (posição na classe, padrão) | "number" (número do carro) | "none"."""
        v = self.options.get("label", "class_pos")
        return v if v in ("class_pos", "number", "none") else "class_pos"

    def _label(self, c) -> str:
        mode = self._label_mode()
        if mode == "number":
            return c.car_number or ""
        if mode == "class_pos":
            return str(c.class_position) if c.class_position else ""
        return ""

    def regravar(self) -> None:
        """Apaga o traçado salvo desta pista e grava de novo na próxima volta."""
        self.recorder.reset(forget_saved=True)

    # ---- desenho --------------------------------------------------------- #
    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        snap = self.snapshot
        if snap is None or not snap.connected:
            self._msg(p, w, h, "SEM DADOS")
            return
        rec, shape = self._rec, self._shape
        if shape is None:
            pct = int(rec.progress * 100)
            if snap.player() is None or snap.player().world_x is None:
                self._msg(p, w, h, tr("SEM POSIÇÃO DO CARRO\npara gravar o traçado"))
            elif CAP_PLAYER_XY_ESTIMATED in snap.capabilities and not pct and not rec.discards:
                self._msg(p, w, h, tr("AGUARDANDO A LINHA DE LARGADA\npara gravar uma volta completa"))
            elif rec.discards:
                self._msg(p, w, h, tr("VOLTA DESCARTADA (não fechou)\ndê outra volta limpa  {}%").format(pct))
            else:
                self._msg(p, w, h, tr("GRAVANDO O TRAÇADO  {}%\ncomplete uma volta").format(pct))
            return
        self._draw_track(p, w, h, shape, snap)

    @staticmethod
    def _msg(p: QPainter, w: float, h: float, text: str) -> None:
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(14, True))
        p.setPen(QColor(theme.WHITE))
        p.drawText(QRectF(10, 0, w - 20, h - 20), Qt.AlignCenter, text)

    def _transform(self, shape, w: float, h: float):
        """(x, y do mundo) -> (x, y de desenho), mantendo a proporção do circuito e centralizando."""
        key = (id(shape), round(w), round(h), self._mirror())
        if self._fit_cache and self._fit_cache[0] == key:
            return self._fit_cache[1]
        x0, y0, x1, y1 = shape.bounds()
        bw, bh = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        aw, ah = w - 2 * PAD, h - HEADER_H - 2 * PAD
        s = min(aw / bw, ah / bh)
        ox = PAD + (aw - bw * s) / 2
        oy = HEADER_H + PAD + (ah - bh * s) / 2
        mirror = self._mirror()

        def f(x: float, y: float) -> tuple[float, float]:
            dx = (x - x0) * s
            dy = (y - y0) * s
            if mirror:
                dx = bw * s - dx
            return ox + dx, oy + dy
        self._fit_cache = (key, f)
        return f

    def _draw_track(self, p: QPainter, w: float, h: float, shape, snap) -> None:
        f = self._transform(shape, w, h)
        pts = [f(x, y) for x, y in shape.points]
        path = QPainterPath(QPointF(*pts[0]))
        for x, y in pts[1:]:
            path.lineTo(x, y)
        path.closeSubpath()
        p.setBrush(Qt.NoBrush)
        pen = QPen(QColor("#f4f4f5"), 14.0)  # contorno claro da pista
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)
        pen = QPen(QColor("#15151a"), 10.0)  # asfalto escuro
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)
        self._start_line(p, pts)
        pos = self._smoother.frame()
        cars = [MapCar(mc.car, *pos.get(mc.car.idx, (mc.x, mc.y)), mc.on_track) for mc in self._last_cars]
        me = next((c for c in cars if c.car.is_player), None)
        for mc in sorted((c for c in cars if not c.car.is_player), key=lambda c: -(c.car.position or 0)):
            self._car(p, f, mc, False)
        if me is not None:  # o meu carro por cima de todos
            self._car(p, f, me, True)

    @staticmethod
    def _start_line(p: QPainter, pts) -> None:
        (x0, y0), (x1, y1) = pts[0], pts[1]
        ang = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
        dx, dy = math.cos(ang) * 8, math.sin(ang) * 8
        p.setPen(QPen(QColor(theme.WHITE), 3.0))
        p.drawLine(QPointF(x0 - dx, y0 - dy), QPointF(x0 + dx, y0 + dy))

    def _car(self, p: QPainter, f, mc: MapCar, is_me: bool) -> None:
        x, y = f(mc.x, mc.y)
        c = mc.car
        hexcolor = class_style(c.class_name, c.class_color, self.snapshot.sim if self.snapshot else None).color
        color = QColor(hexcolor)
        r = ME_R if is_me else DOT_R
        p.save()
        p.setOpacity(p.opacity() * (1.0 if mc.on_track else 0.45))
        if is_me:  # anel verde em volta + borda branca: o meu carro se acha de longe
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(theme.GREEN), 3.0))
            p.drawEllipse(QPointF(x, y), r + 6, r + 6)
            p.setPen(QPen(QColor(theme.WHITE), 3.0))
        else:
            p.setPen(QPen(QColor("#f4f4f5"), 1.5))
        p.setBrush(color)
        p.drawEllipse(QPointF(x, y), r, r)
        label = self._label(c)
        if label:
            p.setPen(QColor(text_on(hexcolor)))
            p.setFont(fit_font(p, label, 13 if is_me else 12, 2 * r - 3, True, min_px=8.0))
            p.drawText(QRectF(x - r, y - r, 2 * r, 2 * r), Qt.AlignCenter, label)
        if c.class_position == 1 and mc.on_track:  # coroa no líder de cada classe
            p.setPen(QColor(hexcolor))
            p.setFont(make_font(13, True))
            p.drawText(QRectF(x - 10, y - r - 17, 20, 15), Qt.AlignCenter, "\u265b")
        p.restore()
