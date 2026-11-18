"""Módulo RELATIVE: carros à frente e atrás na pista, no estilo dos overlays de transmissão."""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from ..core import badges
from ..core.animation import RowAnim, SlotAnimator
from ..core.classes import class_style, license_color
from ..core.incidents import IncidentCounter
from ..core.irating import format_ir
from ..core.model import CarState
from ..core.relative import (DESIGN_W, FOOTER_H, HEADER_H, NAME_FONT_PX, ROW_H, STATE_ALERT, STATE_DANGER, STATE_FAVORABLE,
                             RelativeEntry, RelativeTracker, RelativeView, get_relative_options)
from . import icons, theme
from .module_base import ModuleWindow, fit_font, make_font

POS_X, POS_W = 8.0, 34.0
NUM_X, NUM_W = 44.0, 56.0
NAME_X = 102.0
BADGE_SLOT = 28.0  # sem iRating (LMU): coluna do selo de contato, no lugar onde ficaria a bandeira
RIGHT = DESIGN_W - 8.0
ARROW_W, GAP_W, IR_W, LIC_W = 18.0, 68.0, 110.0, 76.0
GAP_X = RIGHT - ARROW_W - GAP_W - 2.0
IR_X = GAP_X - 4.0 - IR_W
LIC_X = IR_X - 4.0 - LIC_W
NAME_W = LIC_X - 4.0 - NAME_X

# cor de fundo da caixa de gap por estado (texto branco; amarelo usa texto escuro)
_BOX_BG = {"lap_ahead": ("#b3262d", 0.90), "lap_behind": ("#2f6bff", 0.85), STATE_FAVORABLE: ("#14a24d", 0.80),
           STATE_DANGER: ("#e5484d", 0.85), STATE_ALERT: (theme.YELLOW, 0.95), "neutral": ("#2a2a31", 0.90)}
_TREND_COLOR = {STATE_FAVORABLE: theme.GREEN, STATE_DANGER: theme.RED, STATE_ALERT: theme.YELLOW}


class RelativeModule(ModuleWindow):
    CORNER = 8.0
    ANCHOR_TOPLEFT = True

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._tracker = RelativeTracker()
        self._view = RelativeView()
        self._view_snap = None
        self._anim = SlotAnimator()
        self._incidents = IncidentCounter()
        self._clock = time.monotonic  # injetável nos testes

    def update_snapshot(self, snap) -> None:
        self._incidents.update(snap)  # conta a CADA snapshot (uma batida dura um instante)
        super().update_snapshot(snap)

    # ---- dados ---------------------------------------------------------- #
    def _current_view(self) -> RelativeView:
        snap = self.snapshot
        if snap is None or not snap.connected:
            self._tracker.reset()
            self._anim.reset()
            self._view, self._view_snap = RelativeView(message="Aguardando dados"), snap
        elif snap is not self._view_snap:  # só recalcula quando chega snapshot novo
            self._view = self._tracker.update(snap, get_relative_options(self.options))
            self._view_snap = snap
        return self._view

    @staticmethod
    def _row_count(view: RelativeView) -> int:
        """Linhas realmente mostradas: carros à frente + eu + carros atrás (no mínimo 3, para caber a mensagem)."""
        if view.me is None:
            return 3
        return max(len(view.ahead) + 1 + len(view.behind), 3 if view.message else 1)

    def layout_size(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        """O painel se ajusta ao número de linhas (poucos carros = painel baixo); o texto não muda de tamanho."""
        used = HEADER_H + self._row_count(self._current_view()) * ROW_H + FOOTER_H
        return avail_w, min(used, avail_h)

    # ---- desenho -------------------------------------------------------- #
    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        opts = get_relative_options(self.options)
        view = self._current_view()
        self._top_bar(p, w, view)
        if self._incidents.available and not view.bar.incidents_text:
            self._events_bar(p, w)
        # sem linhas em branco: só os carros que existem (a altura do painel acompanha, ver `layout_size`)
        slots: list = list(view.ahead) + ["me"] + list(view.behind)
        n_rows = self._row_count(view)

        # animação de ultrapassagem: rank 1 = ainda à frente, 0 = já passei -> passar um carro (rank cai)
        # destaca em verde; ser ultrapassado (rank sobe) destaca em vermelho
        now = self._clock()
        self._anim.enabled = opts.animations
        items = []
        for slot in slots:
            if slot == "me":
                items.append(("me", 0))
            else:
                items.append((slot.car.idx, 1 if slot.side == "ahead" else 0))
        self._anim.set_targets(items, now)

        pulse = 0.5 + 0.5 * (1 if int(time.monotonic() * 3) % 2 == 0 else 0)  # pisca ~1.5 Hz
        order = []
        for k, slot in enumerate(slots):
            if slot == "me" and view.me is None:
                continue
            key = "me" if slot == "me" else slot.car.idx
            an = self._anim.sample(key, now)
            order.append((an.moving, k, slot, an))
        order.sort(key=lambda t: t[0])  # quem se move é desenhado por último (fica por cima)
        for _moving, k, slot, an in order:
            y = HEADER_H + (k + an.dy_rows) * ROW_H
            if slot == "me":
                self._me_row(p, w, y, view)
            else:
                self._entry_row(p, w, y, slot, view, k, pulse, an)
        self.is_animating = self._anim.active(now)
        if view.message and not view.ahead and not view.behind:
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(13))
            p.drawText(QRectF(0, HEADER_H, w, ROW_H * 3), Qt.AlignCenter, view.message)
        self._footer(p, w, HEADER_H + n_rows * ROW_H, view)

    # ---- barras ---------------------------------------------------------- #
    def _events_bar(self, p: QPainter, w: float) -> None:
        """LMU não publica incidentes: mostra as batidas e saídas de pista contadas pela telemetria (derivadas)."""
        inc = self._incidents
        x = w - 10
        for label, n in (("FORA", inc.offs), ("BAT", inc.hits)):
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(20, True))
            txt = str(n)
            tw = p.fontMetrics().horizontalAdvance(txt)
            p.drawText(QRectF(x - tw - 2, 2, tw + 4, 32), Qt.AlignRight | Qt.AlignVCenter, txt)
            x -= tw + 8
            pw = 14 + 9 * len(label)
            icons.pill(p, QRectF(x - pw, 7, pw, 22), "#2a2a31", label, fg=theme.GRAY, px=13, radius=3)
            x -= pw + 16

    @staticmethod
    def _top_bar(p: QPainter, w: float, view: RelativeView) -> None:
        bar = view.bar
        if bar.sof_text:  # força do grid
            icons.pill(p, QRectF(8, 7, 46, 22), "#2a2a31", "SOF", fg=theme.GRAY, px=13, radius=3)
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(20, True))
            p.drawText(QRectF(60, 2, 90, 32), Qt.AlignLeft | Qt.AlignVCenter, bar.sof_text)
        if bar.incidents_text:  # X tomados / limite: número em branco e ícone colado a ele
            p.setPen(QColor(theme.WHITE))
            p.setFont(make_font(20, True))
            tw = p.fontMetrics().horizontalAdvance(bar.incidents_text)
            p.drawText(QRectF(w - 10 - tw - 2, 2, tw + 4, 32), Qt.AlignRight | Qt.AlignVCenter, bar.incidents_text)
            icons.x_icon(p, w - 10 - tw - 10, 18, 10, theme.GRAY)

    @staticmethod
    def _footer(p: QPainter, w: float, y: float, view: RelativeView) -> None:
        bar = view.bar
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.9)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 2, w, FOOTER_H - 2))
        # "RACE" e o tempo da corrida logo ao lado, sem vão
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(18, True))
        name_w = p.fontMetrics().horizontalAdvance(bar.name)
        p.drawText(QRectF(10, y + 2, name_w + 2, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, bar.name)
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(17, semibold=True))
        p.drawText(QRectF(10 + name_w + 7, y + 2, 220, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, bar.time_text)
        if bar.lap_text:  # "Lap" colado ao valor, ambos encostados na direita
            p.setFont(make_font(18, True))
            val_w = p.fontMetrics().horizontalAdvance(bar.lap_text)
            p.setPen(QColor(theme.WHITE))
            p.drawText(QRectF(w - 8 - val_w - 2, y + 2, val_w + 4, FOOTER_H - 2), Qt.AlignRight | Qt.AlignVCenter,
                       bar.lap_text)
            p.setFont(make_font(16))
            lap_w = p.fontMetrics().horizontalAdvance("Lap")
            p.setPen(QColor(theme.GRAY))
            p.drawText(QRectF(w - 8 - val_w - 5 - lap_w - 2, y + 2, lap_w + 4, FOOTER_H - 2),
                       Qt.AlignRight | Qt.AlignVCenter, "Lap")

    # ---- linhas ---------------------------------------------------------- #
    def _common_cells(self, p: QPainter, y: float, car: CarState, view: RelativeView, bold: bool,
                      reserve: float = 0.0) -> None:
        st = class_style(car.class_name, car.class_color, self.snapshot.sim if self.snapshot else None)
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(20, True))
        p.drawText(QRectF(POS_X, y, POS_W, ROW_H), Qt.AlignCenter, str(car.class_position or car.position or "-"))
        icons.slash(p, NUM_X, y + 6, 6, ROW_H - 12, st.color)
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(19, True))
        p.drawText(QRectF(NUM_X + 14, y, NUM_W - 14, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, car.car_number or "?")
        slot = self._badge_slot()
        if slot and car.is_player and self.snapshot.profile.contact_badge:
            icons.contact_badge(p, NAME_X + slot / 2 - 2, y + ROW_H / 2, badges.slug(self.snapshot.profile.contact_badge),
                                self.ctx.badges, ROW_H - 8)
        avail = NAME_W - reserve - slot
        p.save()
        p.setClipRect(QRectF(NAME_X + slot, y, avail, ROW_H))
        p.setPen(QColor(theme.WHITE))
        # nome COMPLETO: sem abreviar nem cortar; se for muito longo, a fonte encolhe até caber
        p.setFont(fit_font(p, car.driver_name, NAME_FONT_PX, avail, True))
        p.drawText(QRectF(NAME_X + slot, y, avail, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, car.driver_name)
        p.restore()
        self._license_and_rating(p, y, car, view)

    @staticmethod
    def _license_and_rating(p: QPainter, y: float, car: CarState, view: RelativeView) -> None:
        if car.license_class:  # [SR][letra] na cor da licença
            color = license_color(car.license_class)
            sr = f"{car.license_sr:.1f}" if car.license_sr is not None else ""
            icons.pill(p, QRectF(LIC_X, y + 4, 46, ROW_H - 8), icons.shade(color, 0.55), sr,
                       fg=theme.WHITE, px=15, radius=3)
            icons.pill(p, QRectF(LIC_X + 48, y + 4, 28, ROW_H - 8), color, car.license_class, px=17, radius=3)
        if car.irating is not None:  # pílula branca com iRating e variação projetada
            rect = QRectF(IR_X, y + 4, IR_W, ROW_H - 8)
            icons.pill(p, rect, "#f4f4f5", "", radius=3)
            p.setPen(QColor("#111111"))
            p.setFont(make_font(17, True))
            p.drawText(QRectF(IR_X + 7, y + 4, 56, ROW_H - 8), Qt.AlignLeft | Qt.AlignVCenter,
                       format_ir(car.irating))
            delta = view.ir_deltas.get(car.idx)
            if delta is not None:
                good = delta >= 0
                color = "#14a24d" if good else "#d63a3f"
                icons.triangle(p, IR_X + 70, y + ROW_H / 2, good, color, 5.5)
                p.setPen(QColor(color))
                p.setFont(make_font(15, True))
                p.drawText(QRectF(IR_X + 78, y + 4, IR_W - 80, ROW_H - 8), Qt.AlignLeft | Qt.AlignVCenter,
                           str(abs(delta)))

    def _me_row(self, p: QPainter, w: float, y: float, view: RelativeView) -> None:
        me = view.me
        bg = QColor(icons.GOLD)
        bg.setAlphaF(0.62)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 1, w, ROW_H - 2))
        self._common_cells(p, y, me, view, True)
        if not me.license_class:  # LMU: Driver Rank / Safety Rank informados (sem iRating)
            x = LIC_X
            for label, value in self._ranks_parts():
                x += icons.rank_chip(p, x, y + ROW_H / 2, label, str(value), badges.tier_color(value), h=ROW_H - 8,
                                     px=14) + 6
        icons.pill(p, QRectF(GAP_X, y + 4, GAP_W, ROW_H - 8), "#2a2a31", "0.0", fg=theme.WHITE, px=17, radius=3,
                   alpha=0.9)

    def _badge_slot(self) -> float:
        """Reserva a coluna do selo quando há selo de contato para mostrar (LMU, sem iRating): todas as linhas deslocam igual."""
        snap = self.snapshot
        if snap is None or not snap.profile.contact_badge or any(c.irating is not None for c in snap.cars):
            return 0.0
        return BADGE_SLOT

    def _ranks_parts(self) -> list[tuple[str, str]]:
        prof = self.snapshot.profile if self.snapshot else None
        if prof is None:
            return []
        parts = []
        if prof.driver_rank:
            parts.append(("DR", str(prof.driver_rank)))
        if prof.safety_rank:
            parts.append(("SR", str(prof.safety_rank)))
        return parts

    def _entry_row(self, p: QPainter, w: float, y: float, e: RelativeEntry, view: RelativeView, k: int,
                   pulse: float, an: RowAnim) -> None:
        base = self.opacity
        dim = 0.4 if not e.present else (0.6 if e.in_pit else (1.0 if e.same_class else 0.85))  # ausente: bem apagado
        p.setOpacity(base * dim * an.alpha * an.content_alpha)
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.78 if k % 2 == 0 else 0.5)
        if e.fight:  # destaque especial: disputa direta por posição
            bg = QColor(theme.RED)
            bg.setAlphaF(0.18 + 0.20 * pulse)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 1, w, ROW_H - 2))
        if an.flash:  # ultrapassagem: verde = eu passei o carro, vermelho = ele passou por mim
            flash = QColor(theme.GREEN if an.flash > 0 else theme.RED)
            flash.setAlphaF(0.42 * abs(an.flash))
            p.setBrush(flash)
            p.drawRect(QRectF(0, y + 1, w, ROW_H - 2))
            edge = QColor(theme.GREEN if an.flash > 0 else theme.RED)
            edge.setAlphaF(min(1.0, abs(an.flash) * 1.4))
            p.setBrush(edge)
            p.drawRect(QRectF(0, y + 1, 4, ROW_H - 2))
        if e.fight:
            p.setPen(QColor(theme.WHITE))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(1, y + 1.5, w - 2, ROW_H - 3))
        self._common_cells(p, y, e.car, view, e.fight, 38.0 if (not e.present or e.in_pit or e.lap_diff != 0) else 0.0)
        # marcas: PIT e voltas de diferença, no fim do nome
        tag_x = NAME_X + NAME_W - 34
        if not e.present:
            icons.pill(p, QRectF(tag_x, y + 6, 34, ROW_H - 12), "#5a5a63", "OUT", px=12, radius=3)
        elif e.in_pit:
            icons.pill(p, QRectF(tag_x, y + 6, 34, ROW_H - 12), theme.YELLOW, "PIT", px=12, radius=3)
        elif e.lap_diff != 0:
            p.setPen(QColor(theme.BLUE if e.lap_diff > 0 else theme.GRAY))
            p.setFont(make_font(15, True))
            p.drawText(QRectF(tag_x, y, 34, ROW_H), Qt.AlignRight | Qt.AlignVCenter, f"{e.lap_diff:+d}L")
        # caixa de gap colorida + seta de tendência
        bg_color, alpha = _BOX_BG.get(e.box, _BOX_BG["neutral"])
        fg = "#111111" if e.box == STATE_ALERT else theme.WHITE
        icons.pill(p, QRectF(GAP_X, y + 4, GAP_W, ROW_H - 8), bg_color, e.gap_text, fg=fg, px=18, radius=3, alpha=alpha)
        self._trend_arrow(p, RIGHT - ARROW_W / 2, y + ROW_H / 2, e)
        p.setOpacity(base)

    @staticmethod
    def _trend_arrow(p: QPainter, cx: float, cy: float, e: RelativeEntry) -> None:
        """Seta apontando para MIM quando o carro se aproxima, para longe quando se afasta."""
        if e.trend in (None, "steady"):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.GRAY))
            p.drawRect(QRectF(cx - 5, cy - 1, 10, 2))
            return
        toward_me_is_down = e.side == "ahead"  # quem está à frente fica acima de mim na lista
        down = toward_me_is_down == (e.trend == "closing")
        color = _TREND_COLOR.get(e.state, theme.WHITE)
        icons.triangle(p, cx, cy, not down, color, 6.5)
