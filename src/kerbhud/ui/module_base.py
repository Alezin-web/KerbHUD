"""Janela base de um módulo do overlay (PySide6, QPainter).

Cada módulo é UMA janela própria: sem borda, fundo translúcido, sempre no topo,
sem roubar foco e, fora do modo de edição, transparente a cliques (o mouse
atravessa o overlay e vai para o simulador).

O conteúdo é desenhado numa grade de projeto (`spec.design_w x design_h`) e
escalado uniformemente para o tamanho real da janela; por isso redimensionar o
módulo nunca deforma o desenho.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..core import winapi
from ..core.layout import GRID, ModuleSpec, compute_drag, design_size, hit_test, scale_about_topleft
from ..core.model import Snapshot
from ..core.textfmt import fit_font_px
from . import theme
from .context import ModuleContext

_CURSORS = {
    "l": Qt.SizeHorCursor, "r": Qt.SizeHorCursor, "t": Qt.SizeVerCursor, "b": Qt.SizeVerCursor,
    "tl": Qt.SizeFDiagCursor, "br": Qt.SizeFDiagCursor, "tr": Qt.SizeBDiagCursor, "bl": Qt.SizeBDiagCursor,
    "lt": Qt.SizeFDiagCursor, "rb": Qt.SizeFDiagCursor, "rt": Qt.SizeBDiagCursor, "lb": Qt.SizeBDiagCursor,
}


_FONT_CACHE: dict = {}
_FIT_CACHE: dict = {}
_CACHE_LIMIT = 4000


def clear_font_caches() -> None:
    """Esvazia os caches de fonte e de ajuste de tamanho (os testes usam isso entre cenários)."""
    _FONT_CACHE.clear()
    _FIT_CACHE.clear()


def make_font(px: float, bold: bool = False, semibold: bool = False) -> QFont:
    """Fonte esportiva (Bahnschrift). `semibold` = peso intermediário. Objetos são reaproveitados:
    criar um QFont a cada texto, 30 vezes por segundo, é desperdício."""
    key = (px, bold, semibold)
    f = _FONT_CACHE.get(key)
    if f is None:
        f = QFont()
        f.setFamilies(theme.FONT_FAMILIES)
        f.setPixelSize(max(1, int(px)))
        if bold:
            f.setBold(True)
        elif semibold:
            f.setWeight(QFont.DemiBold)
        if len(_FONT_CACHE) >= _CACHE_LIMIT:
            _FONT_CACHE.clear()
        _FONT_CACHE[key] = f
    return f


def fit_font(p: QPainter, text: str, max_px: float, avail: float, bold: bool = True,
             min_px: float = 11.0) -> QFont:
    """Fonte do maior tamanho (até `max_px`) em que `text` cabe em `avail` unidades de desenho.

    Usada nos nomes e nos números: eles aparecem inteiros e a fonte encolhe se for preciso. O
    resultado é guardado por (texto, tamanho, espaço): o texto de um piloto raramente muda.
    """
    key = (text, max_px, avail, bold, min_px)
    px = _FIT_CACHE.get(key)
    if px is None:
        def measure(candidate: float) -> float:
            p.setFont(make_font(candidate, bold))
            return float(p.fontMetrics().horizontalAdvance(text))

        px = fit_font_px(max_px, avail, measure, min_px)
        if len(_FIT_CACHE) >= _CACHE_LIMIT:
            _FIT_CACHE.clear()
        _FIT_CACHE[key] = px
    return make_font(px, bold)


class ModuleWindow(QWidget):
    #: raio dos cantos em unidades de projeto (escala junto com o módulo)
    CORNER = 6.0
    #: True = desenho ancorado no canto superior esquerdo (módulos de altura variável)
    ANCHOR_TOPLEFT = False
    #: True enquanto o módulo tem uma animação em curso (o gerenciador pede novo desenho)
    is_animating = False
    #: True = TEXTO DE TAMANHO FIXO: a janela só define a área visível (mais/menos linhas e colunas); o
    #: tamanho do texto vem de `options["scale"]` e só muda com a roda do mouse / menu "Tamanho do texto".
    FIXED_SCALE = False
    PANEL_BG = True  # False = sem quadro de fundo (só o conteúdo, como o Track Map)
    SCALE_PX_MIN, SCALE_PX_MAX = 0.35, 3.0  # limites de px reais por unidade de desenho

    #: emitido ao soltar o mouse após mover/redimensionar/alterar opacidade
    geometry_committed = Signal(str)

    def __init__(self, spec: ModuleSpec, ctx: Optional[ModuleContext] = None):
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                 | Qt.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.spec = spec
        self.module_id = spec.id
        self.ctx = ctx or ModuleContext()
        #: opções do módulo no layout ativo (mesmo dict do Layout: alterar persiste)
        self.options: dict = {}
        self.snapshot: Optional[Snapshot] = None
        self._edit = False
        self._always_on_top = True
        self._ref_width = 1920.0  # largura (px) do monitor de referência da escala de texto
        self._fade = 1.0  # fator de aparecimento (fade-in) do quadro atual
        self._opacity = 1.0
        self._drag_mode: Optional[str] = None
        self._drag_origin = None
        self._drag_start = (0, 0, 0, 0)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle(f"KerbHUD - {spec.title}")
        self.resize(spec.design_w, spec.design_h)

    # ---- API para o gerenciador ---------------------------------------- #
    def update_snapshot(self, snap: Snapshot) -> None:
        self.snapshot = snap
        if self.isVisible():
            self.update()

    def set_opacity(self, value: float) -> None:
        self._opacity = min(max(value, 0.1), 1.0)
        self.update()

    @property
    def opacity(self) -> float:
        """Transparência escolhida pelo usuário (é a que fica salva no layout)."""
        return self._opacity

    @property
    def effective_opacity(self) -> float:
        """Transparência do usuário vezes o fade-in em curso: use esta ao desenhar."""
        return self._opacity * self._fade

    def frame_alpha(self, w: float, h: float) -> float:
        """Fator 0..1 aplicado a TODO o desenho do quadro (fade-in). Módulos com fade sobrescrevem."""
        return 1.0

    def set_edit_mode(self, on: bool) -> None:
        self._edit = on
        self._drag_mode = None
        self.unsetCursor()
        self._apply_click_through()
        self.update()

    def apply_native_flags(self) -> None:
        """Chamar depois de show(): o HWND só existe a partir daí."""
        hwnd = int(self.winId())
        winapi.set_no_activate(hwnd)
        winapi.set_topmost(hwnd, self._always_on_top)
        self._apply_click_through()

    def set_always_on_top(self, on: bool) -> None:
        self._always_on_top = on
        if self.isVisible():
            winapi.set_topmost(int(self.winId()), on)

    def lower_below_shell(self) -> None:
        """Sai do "sempre no topo" por um momento (barra de tarefas/bandeja em uso); `reassert_topmost` volta."""
        if self.isVisible():
            winapi.set_topmost(int(self.winId()), False)

    def reassert_topmost(self) -> None:
        if self.isVisible() and self._always_on_top:
            winapi.set_topmost(int(self.winId()), True)

    def _apply_click_through(self) -> None:
        through = not self._edit
        if winapi.IS_WIN:
            winapi.set_click_through(int(self.winId()), through)
        # Fallback para outros SOs (desenvolvimento): ignora eventos do mouse.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, through)

    # ---- desenho -------------------------------------------------------- #
    def design_size(self) -> tuple[float, float]:
        """Tamanho de projeto atual (pode depender das opções do módulo)."""
        return design_size(self.module_id, self.options)

    # ---- escala de texto fixa ----------------------------------------------- #
    def set_reference_width(self, px: float) -> None:
        """Largura do monitor em que o módulo está: a escala é guardada como fração dela (independe de resolução)."""
        self._ref_width = float(px) if px and px > 0 else 1920.0

    def fixed_scale_px(self) -> float:
        """Pixels reais por unidade de desenho. Sem `options["scale"]` (módulo criado fora de um layout),
        cai no comportamento antigo: ajustar o conteúdo à janela."""
        k = self.options.get("scale")
        if isinstance(k, (int, float)) and k > 0:
            return min(max(k * self._ref_width, self.SCALE_PX_MIN), self.SCALE_PX_MAX)
        dw, dh = self.design_size()
        return max(min(self.width() / dw, self.height() / dh), 0.01)

    def layout_size(self, avail_w: float, avail_h: float) -> tuple[float, float]:
        """Área (em unidades de desenho) que o conteúdo realmente usa dentro da área disponível; o painel de
        fundo cobre só isso. Módulos de escala fixa sobrescrevem."""
        return avail_w, avail_h

    def zoom(self, factor: float) -> None:
        """Aumenta/diminui o conteúdo. Em módulos de escala fixa muda o tamanho do TEXTO (e a janela acompanha
        na mesma proporção, para o que aparece continuar igual); nos demais, escala a janela mantendo a proporção."""
        f = factor
        if self.FIXED_SCALE:
            cur = self.fixed_scale_px()
            new = min(max(cur * factor, self.SCALE_PX_MIN), self.SCALE_PX_MAX)
            f = new / cur
            self.options["scale"] = new / self._ref_width
        x, y, w, h = scale_about_topleft(self._geom(), f, (self.spec.min_w, self.spec.min_h))
        self.setGeometry(x, y, w, h)
        self.update()

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        """Subclasses desenham aqui, em coordenadas de projeto (0..w, 0..h)."""

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)  # logos reduzidas com suavização
        w, h = self.width(), self.height()
        self._fade = self.frame_alpha(w, h)
        p.setOpacity(self.effective_opacity)
        if self.FIXED_SCALE:
            self._paint_fixed(p, w, h)
            p.end()
            return
        dw, dh = self.design_size()
        s = min(w / dw, h / dh)
        radius = self.CORNER * s

        # O painel de fundo abraça a área de projeto (e não a janela inteira): se a
        # janela tiver outra proporção, sobra margem transparente em vez de um painel gordo.
        ox, oy = (0.0, 0.0) if self.ANCHOR_TOPLEFT else ((w - dw * s) / 2, (h - dh * s) / 2)
        uw, uh = self.layout_size(dw, dh)  # área realmente usada (o painel não cobre linhas que não existem)
        bg = QColor(theme.PANEL)
        bg.setAlphaF(theme.PANEL_BG_ALPHA)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        if self.PANEL_BG and uw > 0 and uh > 0:
            p.drawRoundedRect(QRectF(ox + 0.5, oy + 0.5, uw * s - 1, uh * s - 1), radius, radius)

        p.save()
        p.translate(ox, oy)
        p.scale(s, s)
        p.setClipRect(QRectF(0, 0, dw, dh))
        self.paint_content(p, dw, dh)
        p.restore()

        if self._edit:
            self._paint_edit_chrome(p, w, h, radius)
        p.end()

    def _paint_fixed(self, p: QPainter, w: float, h: float) -> None:
        """Módulos de escala fixa: o texto tem tamanho constante e a janela define a área visível."""
        s = self.fixed_scale_px()
        aw, ah = w / s, h / s  # área disponível em unidades de desenho
        uw, uh = self.layout_size(aw, ah)
        radius = self.CORNER * s
        if uw <= 0 or uh <= 0:  # módulo sem nada para mostrar agora: não desenha nada (só a moldura no modo de edição)
            if self._edit:
                self._paint_edit_chrome(p, w, h, radius)
            return
        bg = QColor(theme.PANEL)
        bg.setAlphaF(theme.PANEL_BG_ALPHA)
        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5, 0.5, uw * s - 1, uh * s - 1), radius, radius)  # só a área usada
        p.save()
        p.scale(s, s)
        p.setClipRect(QRectF(0, 0, aw, ah))
        self.paint_content(p, aw, ah)
        p.restore()
        if self._edit:
            self._paint_edit_chrome(p, w, h, radius)

    def _paint_edit_chrome(self, p: QPainter, w: int, h: int, radius: float = 6.0) -> None:
        pen = QPen(QColor(theme.RED), 1.5, Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)
        # etiqueta com nome e tamanho
        label = f"{self.spec.title}  {w}x{h}  op {int(self._opacity * 100)}%"
        p.setFont(make_font(11, True))
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(label) + 12
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawRoundedRect(QRectF(0, 0, min(tw, w), 18), 4, 4)
        p.setPen(QColor(theme.WHITE))
        p.drawText(QPointF(6, 13), label)
        # cantos de redimensionamento
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        for hx, hy in ((w - 8, 0), (0, h - 8), (w - 8, h - 8)):
            p.drawRect(QRectF(hx, hy, 8, 8))

    # ---- mouse (apenas no modo de edição) ------------------------------ #
    def _geom(self) -> tuple[int, int, int, int]:
        g = self.geometry()
        return g.x(), g.y(), g.width(), g.height()

    def mousePressEvent(self, e) -> None:  # noqa: N802
        if not self._edit or e.button() != Qt.LeftButton:
            return
        pos = e.position().toPoint()
        self._drag_mode = hit_test(pos.x(), pos.y(), self.width(), self.height())
        self._drag_origin = e.globalPosition().toPoint()
        self._drag_start = self._geom()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if not self._edit:
            return
        if self._drag_mode is None:
            mode = hit_test(e.position().toPoint().x(), e.position().toPoint().y(),
                            self.width(), self.height())
            if mode == "move":
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(_CURSORS.get(mode, Qt.ArrowCursor))
            return
        d = e.globalPosition().toPoint() - self._drag_origin
        grid = None if (e.modifiers() & Qt.AltModifier) else GRID
        x, y, w, h = compute_drag(self._drag_mode, self._drag_start, d.x(), d.y(),
                                  (self.spec.min_w, self.spec.min_h), grid)
        self.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, e) -> None:  # noqa: N802
        if self._edit and self._drag_mode is not None and e.button() == Qt.LeftButton:
            self._drag_mode = None
            self.geometry_committed.emit(self.module_id)

    def wheelEvent(self, e) -> None:  # noqa: N802
        """Roda = zoom (tamanho do texto no Standings/Inputs). Ctrl + roda = transparência."""
        if not self._edit:
            return
        steps = e.angleDelta().y() / 120.0
        if steps == 0:
            return
        if e.modifiers() & Qt.ControlModifier:
            self.set_opacity(self._opacity + 0.05 * steps)
        else:
            self.zoom(1.0 + 0.05 * steps)  # tamanho do texto (módulos de escala fixa) ou da janela inteira
        self.geometry_committed.emit(self.module_id)
