"""Módulo STANDINGS: tabela por classe, no estilo dos overlays de transmissão.

**Texto de tamanho fixo:** redimensionar a janela NÃO encolhe nem aumenta o texto. Janela mais baixa = menos
linhas; mais estreita = menos colunas (somem primeiro as menos importantes: NRG, voltas, pneu...); maior =
mais linhas e colunas, até o que você ativou. O tamanho do texto muda pela roda do mouse (modo de edição) ou
pelo menu da bandeja (Tamanho do texto).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Optional

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from ..core import badges
from ..core.animation import RowAnim, SlotAnimator, ease_out_cubic
from ..core.classes import license_color, text_on
from ..core.gridtracker import StartGridTracker
from ..core.standings import (FOOTER_H, INFO_BADGE_R, INFO_FONT_PX, INFO_HELMET_PX, INFO_LABEL_PX, NAME_FONT_PX, NRG_ICON_X, NRG_TEXT_X, NUM2_FONT_PX, NUM_FONT_PX, PAD_BOTTOM,
                              ROW_H, TITLE_FONT_PX, TITLE_ROW_H, TITLE_ROW_Y, TOP_H,
                              ColumnSpec,
                              HeaderLine, StandingsOptions, StandingsRow, StandingsView, build_standings,
                              columns_width, fit_columns, fit_rows, get_standings_options, select_lines, NrgTracker)
from ..core.i18n import tr
from . import icons, theme
from .module_base import ModuleWindow, fit_font, make_font

_ALIGN = {"left": Qt.AlignLeft | Qt.AlignVCenter, "right": Qt.AlignRight | Qt.AlignVCenter,
          "center": Qt.AlignCenter}
_TITLES = {"delta": "", "tire": "Tire", "laps": "Laps", "int": "Int", "gap": "Gap", "best": "Fastest",
           "last": "Last", "nrg": "NRG"}
_DIM = {"none": 1.0, "other_class": 0.66, "pit": 0.78, "out": 0.40}
_TAG_BG = {"PIT": theme.YELLOW, "OUT": "#5a5a63", "GAR": "#5a5a63", "DSQ": theme.RED, "FIN": theme.WHITE}
LOGO_SIZE = 30.0  # logos das marcas: bem visíveis dentro da linha de 30
FLAG_W, FLAG_H = 28.0, 19.0
EMPTY_W = 520.0  # largura do painel quando ainda não há dados
FADE_IN_S = 0.6  # o Standings aparece com fade-in (não surge de repente quando alguém faz a primeira volta)


@dataclass
class _Prep:
    """Tudo o que depende da janela e do snapshot (calculado uma vez por combinação)."""
    opts: StandingsOptions
    cols: list[ColumnSpec]
    view: Optional[StandingsView] = None
    lines: list = field(default_factory=list)
    used_w: float = EMPTY_W
    used_h: float = TOP_H + 3 * ROW_H
    message: str = ""
    hidden: bool = False  # treino/qualy sem nenhum tempo ainda: o módulo não aparece


class StandingsModule(ModuleWindow):
    CORNER = 8.0
    ANCHOR_TOPLEFT = True
    FIXED_SCALE = True

    def __init__(self, spec, ctx=None):
        super().__init__(spec, ctx)
        self._grid = StartGridTracker()
        self._anim = SlotAnimator()
        self._clock = time.monotonic  # injetável nos testes
        self._prep: Optional[_Prep] = None
        self._prep_snap = None
        self._prep_key = None
        self._nrg = NrgTracker()  # a coluna NRG existe se alguma categoria da sessão tem energia virtual
        self._had_content = False
        self._fade_t0: Optional[float] = None

    # ---- layout (depende da área disponível) ---------------------------- #
    def _prepare(self, aw: float, ah: float) -> _Prep:
        snap = self.snapshot
        opts = get_standings_options(self.options)
        key = (round(aw, 1), round(ah, 1), opts)
        if self._prep is not None and self._prep_snap is snap and self._prep_key == key:
            return self._prep
        cols = fit_columns(opts, aw)  # colunas que cabem SEM encolher a fonte
        if snap is None or not snap.connected:
            self._grid.reset()
            self._anim.reset()
            self._nrg.reset()
            prep = _Prep(opts, cols, message="SEM DADOS")
        else:
            view = build_standings(snap, opts, self._grid.update(snap), self.ctx.flag_resolver)
            if view.hidden:
                self._anim.reset()
                prep = _Prep(opts, cols, view, message=tr("Aparece quando alguém fizer um tempo de volta"), hidden=True)
            elif not view.groups:
                self._anim.reset()
                prep = _Prep(opts, cols, view, message=tr("AGUARDANDO CLASSIFICAÇÃO"))
            else:
                if not self._nrg.visible(snap):  # nenhuma categoria da sessão tem NRG: a coluna some
                    cols = fit_columns(replace(opts, columns=opts.columns - {"nrg"}), aw)
                lines = select_lines(view.groups, fit_rows(opts, ah))  # linhas que cabem na altura
                used_h = TOP_H + len(lines) * ROW_H + (FOOTER_H if opts.show_profile else 0.0) + PAD_BOTTOM
                prep = _Prep(opts, cols, view, lines, columns_width(cols), used_h)
        self._prep, self._prep_snap, self._prep_key = prep, snap, key
        return prep

    def frame_alpha(self, w: float, h: float) -> float:
        """Fade-in quando a classificação passa a ter conteúdo (primeira volta em treino/qualy, início da corrida...).

        Só a CHEGADA do conteúdo dispara o fade; redimensionar a janela ou trocar de linhas não repete."""
        scale = self.fixed_scale_px()
        prep = self._prepare(w / scale, h / scale)
        now = self._clock()
        has_content = bool(prep.lines)
        if has_content and not self._had_content:
            self._fade_t0 = now
        self._had_content = has_content
        if self._fade_t0 is None:
            return 1.0
        t = (now - self._fade_t0) / FADE_IN_S
        if t >= 1.0:
            self._fade_t0 = None
            return 1.0
        return ease_out_cubic(t)

    def layout_size(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        prep = self._prepare(avail_w, avail_h)
        if prep.hidden and not self._edit:
            return 0.0, 0.0  # nada a mostrar: nem o painel aparece
        return min(prep.used_w, max(avail_w, 1.0)), prep.used_h

    # ---- desenho -------------------------------------------------------- #
    def paint_content(self, p: QPainter, aw: float, ah: float) -> None:
        prep = self._prepare(aw, ah)
        w = prep.used_w
        if prep.message:
            self.is_animating = False
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(20, True))
            p.drawText(QRectF(0, TOP_H, w, prep.used_h - TOP_H), Qt.AlignCenter, prep.message)
            return
        view, opts, cols = prep.view, prep.opts, prep.cols
        self._top_bar(p, w, view, cols)

        lines = prep.lines
        now = self._clock()
        self._anim.enabled = opts.animations
        keys = self._keys(lines)
        self._anim.set_targets([(key, rank) for key, rank in keys], now)
        order = []
        for k, line in enumerate(lines):
            an = self._anim.sample(keys[k][0], now)
            order.append((an.moving, k, line, an))
        order.sort(key=lambda t: t[0])  # quem está se movendo é desenhado por último (fica por cima)
        for _moving, k, line, an in order:
            y = TOP_H + (k + an.dy_rows) * ROW_H
            if isinstance(line, HeaderLine):
                self._group_header(p, w, y, line, an)
            elif line is None:
                self._separator(p, w, y)
            else:
                self._row(p, w, y, line, cols, k, an)
        self.is_animating = self._anim.active(now) or self._fade_t0 is not None  # o fade também pede repintura
        if opts.show_profile:
            self._footer(p, w, TOP_H + len(lines) * ROW_H, view)

    @staticmethod
    def _keys(lines: list) -> list[tuple]:
        """Chave estável e posição na classe de cada linha (base da animação de ultrapassagem)."""
        out, seps = [], 0
        for ln in lines:
            if isinstance(ln, HeaderLine):
                out.append((("h", ln.label), 0))
            elif ln is None:
                out.append((("sep", seps), 0))
                seps += 1
            else:
                out.append((ln.car.idx, int(ln.pos_text) if ln.pos_text.isdigit() else 0))
        return out

    # ---- barra superior -------------------------------------------------- #
    @staticmethod
    def _text(p: QPainter, x: float, text: str, px: int, color: str, bold: bool = True) -> float:
        """Desenha um texto na linha de cima da barra e devolve a posição logo depois dele."""
        p.setPen(QColor(color))
        p.setFont(make_font(px, bold))
        tw = p.fontMetrics().horizontalAdvance(text)
        p.drawText(QRectF(x, 1, tw + 4, 24), Qt.AlignLeft | Qt.AlignVCenter, text)
        return x + tw

    def _top_bar(self, p: QPainter, w: float, view: StandingsView, cols: list[ColumnSpec]) -> None:
        bar = view.bar
        icons.session_badge(p, 14 + INFO_BADGE_R, 13, INFO_BADGE_R, bar.letter)
        # os itens fluem da esquerda para a direita conforme a largura real de cada texto
        x = self._text(p, 14 + 2 * INFO_BADGE_R + 8, bar.time_text or bar.name, INFO_FONT_PX, theme.WHITE) + 24
        if bar.incidents_text:  # X tomados / limite: ícone colado ao número, número em branco
            icons.x_icon(p, x + 7, 13, 12, theme.RED)
            x = self._text(p, x + 19, bar.incidents_text, INFO_FONT_PX, theme.WHITE) + 24
        if bar.lap_text:  # "Lap" colado ao valor (volta atual / total ou estimado)
            p.setFont(make_font(INFO_LABEL_PX))
            lap_w = p.fontMetrics().horizontalAdvance("Lap")
            self._text(p, x, "Lap", INFO_LABEL_PX, theme.GRAY, bold=False)
            x = self._text(p, x + lap_w + 4, bar.lap_text, INFO_FONT_PX, theme.WHITE) + 24
        icons.helmet(p, x, 2, INFO_HELMET_PX, theme.GRAY)  # pilotos na corrida
        self._text(p, x + INFO_HELMET_PX * 1.2 + 6, str(bar.cars_count), INFO_FONT_PX, theme.WHITE)
        # títulos das colunas: maiores (17), encolhem só se a coluna for estreita demais (ex.: "Tire")
        p.setPen(QColor(theme.GRAY))
        for c in cols:
            title = _TITLES.get(c.key)
            if title:
                shift = NRG_ICON_X if c.key == "nrg" else 0.0  # o título fica sobre a bateria
                avail = c.w - 4 - shift
                p.setFont(fit_font(p, title, TITLE_FONT_PX, avail, True, 12.0))
                p.drawText(QRectF(c.x + shift, TITLE_ROW_Y, avail, TITLE_ROW_H), _ALIGN[c.align], title)

    # ---- linhas ---------------------------------------------------------- #
    def _group_header(self, p: QPainter, w: float, y: float, line: HeaderLine, an: RowAnim) -> None:
        base = self.effective_opacity
        p.setOpacity(base * an.alpha * an.content_alpha)
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.9)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 2, w, ROW_H - 2))
        p.setBrush(QColor(line.color))
        p.drawRect(QRectF(0, y + ROW_H - 2, w, 2))  # linha na cor da classe
        # selo da classe: [capacete] quantidade de pilotos da classe + nome. O texto e o capacete usam a
        # cor de maior contraste com a classe; a viseira "vazada" mostra a cor da classe por trás.
        icons.pill(p, QRectF(8, y + 4, 128, ROW_H - 8), line.color, "", radius=3)
        fg = text_on(line.color)
        icons.helmet(p, 16, y + ROW_H / 2 - 8, 16, fg, visor=line.color)
        p.setPen(QColor(fg))
        p.setFont(make_font(17, True))
        p.drawText(QRectF(42, y + 4, 30, ROW_H - 8), Qt.AlignLeft | Qt.AlignVCenter, str(line.count))
        p.drawText(QRectF(72, y + 4, 62, ROW_H - 8), Qt.AlignLeft | Qt.AlignVCenter, line.label)
        p.setOpacity(base)

    @staticmethod
    def _separator(p: QPainter, w: float, y: float) -> None:
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(16, True))
        p.drawText(QRectF(0, y, w, ROW_H), Qt.AlignCenter, "···")

    def _row(self, p: QPainter, w: float, y: float, row: StandingsRow, cols: list[ColumnSpec], k: int,
             an: RowAnim) -> None:
        base = self.effective_opacity
        p.setOpacity(base * _DIM[row.dim] * an.alpha * an.content_alpha)
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.78 if k % 2 == 0 else 0.5)
        if row.is_player:
            bg = QColor(icons.GOLD)
            bg.setAlphaF(0.62)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 1, w, ROW_H - 2))
        if an.flash:  # ultrapassagem: destaque verde (ganhou) ou vermelho (perdeu) que some em ~1 s
            flash = QColor(theme.GREEN if an.flash > 0 else theme.RED)
            flash.setAlphaF(0.42 * abs(an.flash))
            p.setBrush(flash)
            p.drawRect(QRectF(0, y + 1, w, ROW_H - 2))
            edge = QColor(theme.GREEN if an.flash > 0 else theme.RED)
            edge.setAlphaF(min(1.0, abs(an.flash) * 1.4))
            p.setBrush(edge)
            p.drawRect(QRectF(0, y + 1, 4, ROW_H - 2))
        for c in cols:
            self._cell(p, c, y, row)
        p.setOpacity(base)

    def _cell(self, p: QPainter, c: ColumnSpec, y: float, row: StandingsRow) -> None:
        key = c.key
        rect = QRectF(c.x + 2, y, c.w - 4, ROW_H)
        white, gray = QColor(theme.WHITE), QColor(theme.GRAY)
        cy = y + ROW_H / 2
        if key == "pos":
            p.setPen(white)
            p.setFont(make_font(20, True))
            p.drawText(rect, Qt.AlignCenter, row.pos_text)
        elif key == "num":
            icons.slash(p, c.x + 3, y + 6, 6, ROW_H - 12, row.class_color)
            p.setPen(white)
            p.setFont(make_font(19, True))
            p.drawText(QRectF(c.x + 17, y, c.w - 18, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, row.number_text or "?")
        elif key == "flag":
            if row.country and self.ctx.flags is not None:  # bandeira do país (nada se o arquivo não existir)
                self.ctx.flags.draw(p, row.country, c.x + (c.w - FLAG_W) / 2, cy - FLAG_H / 2, FLAG_W, FLAG_H)
            elif row.badge:  # sem bandeira (LMU): o selo de contato ocupa o lugar dela
                icons.contact_badge(p, c.x + c.w / 2, cy, row.badge, self.ctx.badges, ROW_H - 8)
        elif key == "name":
            tag = row.status_tag
            reserve = 38 if tag else 0
            avail = c.w - reserve - 4
            p.save()
            p.setClipRect(QRectF(c.x, y, c.w - reserve, ROW_H))
            p.setPen(white)
            # nome COMPLETO: sem abreviar nem cortar; se for muito longo, a fonte encolhe até caber
            p.setFont(fit_font(p, row.name, NAME_FONT_PX, avail, True))
            p.drawText(QRectF(c.x + 2, y, avail + 2, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, row.name)
            p.restore()
            if tag:
                icons.pill(p, QRectF(c.x + c.w - 36, y + 6, 34, ROW_H - 12), _TAG_BG.get(tag, "#5a5a63"),
                           tag, px=12, radius=3)
        elif key == "license":
            prof = self.snapshot.profile if self.snapshot else None
            if row.is_player and not row.license_class and not row.irating_text and prof is not None:
                x = c.x + 2  # LMU: seus ranks [DR | B2] [SR | S3] (só o seu é conhecido)
                for label, value in (("DR", prof.driver_rank), ("SR", prof.safety_rank)):
                    if value:
                        x += icons.rank_chip(p, x, cy, label, str(value), badges.tier_color(value), h=ROW_H - 8,
                                             px=12, compact=True) + 4
            if row.license_class:
                icons.pill(p, QRectF(c.x + 2, y + 4, 26, ROW_H - 8), license_color(row.license_class),
                           row.license_class, px=17, radius=3)
            if row.irating_text:
                icons.pill(p, QRectF(c.x + 33, y + 4, 66, ROW_H - 8), "#f4f4f5", row.irating_text,
                           fg="#111111", px=16, radius=3)
        elif key == "brand":
            logos = self.ctx.logos
            if row.brand is not None:  # logo REAL da marca (nada é desenhado se o arquivo não existir)
                icons.brand_logo(p, c.x + c.w / 2, cy, row.brand, logos, LOGO_SIZE)
            elif logos is not None:
                logos.note_unrecognized(row.car.team_name, row.car.vehicle_raw, row.car.class_name)
        elif key == "delta":
            if row.pos_change is not None:
                icons.pos_change(p, rect, row.pos_change)
        elif key == "tire":
            if row.tire:
                icons.tire(p, c.x + c.w / 2, cy, row.tire)
        elif key == "laps":
            p.setPen(white)
            p.setFont(fit_font(p, row.laps_text, NUM2_FONT_PX, c.w - 8, True))  # encolhe só se não couber
            p.drawText(rect, Qt.AlignCenter, row.laps_text)
        elif key == "nrg":
            if row.energy_pct is not None:
                icons.battery(p, c.x + NRG_ICON_X, cy - 8, row.energy_pct)
                p.setPen(white)
                pct = f"{row.energy_pct:.0f}%"
                p.setFont(fit_font(p, pct, NUM2_FONT_PX, c.w - NRG_TEXT_X - 4, True))
                p.drawText(QRectF(c.x + NRG_TEXT_X, y, c.w - NRG_TEXT_X, ROW_H), Qt.AlignLeft | Qt.AlignVCenter, pct)
        else:  # int, gap, best, last
            text = {"int": row.int_text, "gap": row.gap_text, "best": row.best_text, "last": row.last_text}[key]
            if key == "best" and row.best_flag == "class" and text != "—":
                icons.pill(p, QRectF(c.x + 2, y + 2, c.w - 4, ROW_H - 4), icons.PURPLE_BG, text,
                           fg=icons.PURPLE_FG, px=NUM_FONT_PX, radius=3, fit=True)
                return
            p.setPen(gray if text == "—" else white)
            px = NUM_FONT_PX if key in ("best", "last") else NUM2_FONT_PX
            p.setFont(fit_font(p, text, px, c.w - 8, True))  # encolhe só se não couber
            p.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, text)

    # ---- rodapé: meu perfil ------------------------------------------------ #
    def _footer(self, p: QPainter, w: float, y: float, view: StandingsView) -> None:
        bg = QColor(theme.PANEL_ALT)
        bg.setAlphaF(0.9)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRect(QRectF(0, y + 2, w, FOOTER_H - 2))
        x = 12.0
        for chip in view.chips:
            if chip.rank:  # LMU: chip colorido [DR | B2]; o "*" avisa que o valor é manual
                x += icons.rank_chip(p, x, y + 1 + FOOTER_H / 2, chip.rank, chip.value, badges.tier_color(chip.value))
                if chip.label.endswith("*"):
                    p.setPen(QColor(theme.GRAY))
                    p.setFont(make_font(13, True))
                    p.drawText(QRectF(x + 2, y + 2, 12, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, "*")
                    x += 12
                x += 22
                continue
            p.setPen(QColor(theme.GRAY))
            p.setFont(make_font(13, True))
            p.drawText(QRectF(x, y + 2, 70, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, chip.label)
            x += 10 + 9 * len(chip.label)
            if chip.badge and icons.contact_badge(p, x + 15, y + 1 + FOOTER_H / 2, chip.badge, self.ctx.badges, 30.0):
                x += 44 + 22  # selo de contato: o ícone no lugar do texto
                continue
            p.setPen(QColor(chip.color if chip.available else theme.GRAY))
            p.setFont(make_font(20 if chip.available else 16, True))
            p.drawText(QRectF(x, y + 2, 110, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, chip.value)
            x += 14 + 11 * len(chip.value)
            if chip.delta is not None:  # variação projetada de iRating (estimativa)
                good = chip.delta >= 0
                icons.triangle(p, x + 5, y + FOOTER_H / 2 + 1, good, theme.GREEN if good else theme.RED)
                p.setPen(QColor(theme.GREEN if good else theme.RED))
                p.setFont(make_font(18, True))
                p.drawText(QRectF(x + 14, y + 2, 56, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter,
                           f"{abs(chip.delta)}")
                p.setPen(QColor(theme.GRAY))
                p.setFont(make_font(12))
                p.drawText(QRectF(x + 56, y + 2, 44, FOOTER_H - 2), Qt.AlignLeft | Qt.AlignVCenter, "est.")
                x += 100
            x += 22
