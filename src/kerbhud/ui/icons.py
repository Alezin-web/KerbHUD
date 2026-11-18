"""Ícones e selos desenhados em código (sem arquivos de imagem), no estilo dos overlays de
transmissão. Logotipos de marcas só são usados se o próprio usuário os colocar na pasta
`logos/` (ex.: `bmw.png`); nenhum logotipo é distribuído com o app.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt
try:  # SVG é opcional: sem o módulo QtSvg só PNG/WebP/JPG são lidos
    from PySide6.QtSvg import QSvgRenderer
except Exception:  # noqa: BLE001
    QSvgRenderer = None
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from ..core import badges
from ..core.brands import Brand
from ..core.logos import logo_file
from ..core.classes import text_on
from ..core.tires import compound_color
from . import theme
from .module_base import fit_font, make_font

GOLD = "#c9a227"  # destaque da linha do piloto (como nos prints de referência)
PURPLE_BG = "#4b2a73"
PURPLE_FG = "#d9b8ff"


def shade(color: str, factor: float) -> str:
    """Escurece (factor < 1) ou clareia (> 1) uma cor "#rrggbb"."""
    try:
        r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, IndexError):
        return color
    f = max(factor, 0.0)
    return "#{:02x}{:02x}{:02x}".format(*(min(255, int(c * f)) for c in (r, g, b)))


def pill(p: QPainter, rect: QRectF, bg: str, text: str, fg: Optional[str] = None, px: int = 12,
         bold: bool = True, radius: float = 4.0, alpha: float = 1.0, fit: bool = False) -> None:
    """Retângulo arredondado com texto centralizado. `fit` encolhe a fonte se o texto não couber."""
    c = QColor(bg)
    c.setAlphaF(alpha)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawRoundedRect(rect, radius, radius)
    if text:
        p.setPen(QColor(fg or text_on(bg)))
        p.setFont(fit_font(p, text, px, rect.width() - 8, bold) if fit else make_font(px, bold))
        p.drawText(rect, Qt.AlignCenter, text)


def rank_chip(p: QPainter, x: float, cy: float, label: str, value: str, color: str, h: float = 24.0,
              px: int = 15, compact: bool = False) -> float:
    """Chip de rank do LMU: [DR | B2]. O rótulo fica numa faixa mais escura e o valor na cor do nível. Devolve a largura."""
    label_w = (6.0 if compact else 12.0) + 0.62 * px * len(label)
    value_w = (6.0 if compact else 16.0) + 0.62 * px * len(value)
    if not compact:
        value_w = max(34.0, value_w)
    top = cy - h / 2
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, top, label_w + value_w, h), 4, 4)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(path)
    p.setBrush(QColor(shade(color, 0.62)))
    p.drawRoundedRect(QRectF(x, top, label_w, h), 4, 4)
    p.drawRect(QRectF(x + label_w - 4, top, 4, h))  # emenda reta entre as duas partes
    p.setPen(QColor("#f4f4f5"))
    p.setFont(make_font(max(11, px - 3), True))
    p.drawText(QRectF(x, top, label_w, h), Qt.AlignCenter, label)
    p.setFont(make_font(px, True))
    p.drawText(QRectF(x + label_w, top, value_w, h), Qt.AlignCenter, value)
    return label_w + value_w


def slash(p: QPainter, x: float, y: float, w: float, h: float, color: str) -> None:
    """Faixa inclinada da classe, ao lado do número do carro."""
    path = QPainterPath()
    skew = h * 0.28
    path.moveTo(x + skew, y)
    path.lineTo(x + skew + w, y)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.closeSubpath()
    p.fillPath(path, QColor(color))


def triangle(p: QPainter, cx: float, cy: float, up: bool, color: str, size: float = 6.0) -> None:
    path = QPainterPath()
    if up:
        path.moveTo(cx - size, cy + size * 0.6)
        path.lineTo(cx + size, cy + size * 0.6)
        path.lineTo(cx, cy - size * 0.8)
    else:
        path.moveTo(cx - size, cy - size * 0.6)
        path.lineTo(cx + size, cy - size * 0.6)
        path.lineTo(cx, cy + size * 0.8)
    path.closeSubpath()
    p.fillPath(path, QColor(color))


def pos_change(p: QPainter, rect: QRectF, change: int) -> None:
    """Ganho (verde, seta para cima), perda (vermelho, seta para baixo) ou 0 (cinza)."""
    if change > 0:
        color, up = theme.GREEN, True
    elif change < 0:
        color, up = theme.RED, False
    else:
        color, up = theme.GRAY, None
    cy = rect.top() + rect.height() / 2
    if up is None:
        p.setPen(QPen(QColor(color), 2.4))
        p.drawLine(QPointF(rect.left() + 6, cy), QPointF(rect.left() + 16, cy))
    else:
        triangle(p, rect.left() + 11, cy, up, color)
    p.setPen(QColor(color))
    p.setFont(make_font(16, True))
    p.drawText(QRectF(rect.left() + 20, rect.top(), rect.width() - 20, rect.height()),
               Qt.AlignLeft | Qt.AlignVCenter, str(abs(change)))


def x_icon(p: QPainter, cx: float, cy: float, size: float, color: str) -> None:
    """Ícone de incidente (X)."""
    p.setPen(QPen(QColor(color), 2.4, Qt.SolidLine, Qt.RoundCap))
    h = size / 2
    p.drawLine(QPointF(cx - h, cy - h), QPointF(cx + h, cy + h))
    p.drawLine(QPointF(cx - h, cy + h), QPointF(cx + h, cy - h))


def helmet(p: QPainter, x: float, y: float, size: float, color: str, visor: Optional[str] = None) -> None:
    """Capacete de piloto visto de lado (virado para a direita): casco, queixo e viseira.

    `size` é a altura; a largura é 1,2x. A viseira é "vazada" com a cor `visor` (use a cor do fundo
    onde o ícone está), o que faz um capacete escuro continuar legível sobre fundos claros.
    """
    w, h = size * 1.2, size

    def pt(u: float, v: float) -> QPointF:
        return QPointF(x + u * w, y + v * h)

    shell = QPainterPath()
    shell.moveTo(pt(0.04, 0.70))
    shell.cubicTo(pt(0.00, 0.30), pt(0.28, 0.02), pt(0.58, 0.04))  # calota (topo da cabeça)
    shell.cubicTo(pt(0.86, 0.06), pt(1.00, 0.30), pt(0.99, 0.58))  # testa e frente
    shell.lineTo(pt(0.99, 0.78))
    shell.cubicTo(pt(0.99, 0.92), pt(0.92, 0.98), pt(0.82, 0.98))  # queixo
    shell.lineTo(pt(0.30, 0.98))
    shell.cubicTo(pt(0.12, 0.98), pt(0.05, 0.88), pt(0.04, 0.70))  # nuca
    shell.closeSubpath()
    p.fillPath(shell, QColor(color))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(visor or theme.PANEL))
    p.drawRoundedRect(QRectF(x + 0.44 * w, y + 0.34 * h, 0.43 * w, 0.24 * h), size * 0.08, size * 0.08)  # viseira


def session_badge(p: QPainter, cx: float, cy: float, r: float, letter: str) -> None:
    """Círculo com a inicial da sessão (R, Q, P...)."""
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(theme.WHITE), 1.6))
    p.drawEllipse(QPointF(cx, cy), r, r)
    p.setPen(QColor(theme.WHITE))
    p.setFont(make_font(r * 1.15, True))
    p.drawText(QRectF(cx - r, cy - r, 2 * r, 2 * r), Qt.AlignCenter, letter)


def battery(p: QPainter, x: float, y: float, pct: float) -> None:
    """Bateria de 4 segmentos: verde > 50 %, amarelo 20-50 %, vermelho < 20 %."""
    pct = min(max(pct, 0.0), 100.0)
    color = theme.GREEN if pct > 50 else (theme.YELLOW if pct >= 20 else theme.RED)
    w, h = 34.0, 16.0
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(theme.GRAY), 1.4))
    p.drawRoundedRect(QRectF(x, y, w, h), 2, 2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.GRAY))
    p.drawRect(QRectF(x + w, y + 4.5, 2.5, h - 9))  # polo
    lit = max(1, min(4, int(pct / 25.0 + 0.999))) if pct > 0 else 0
    seg = (w - 5.0) / 4.0
    for k in range(4):
        p.setBrush(QColor(color if k < lit else theme.LINE))
        p.drawRect(QRectF(x + 2 + k * seg, y + 2, seg - 1.5, h - 4))


def tire(p: QPainter, cx: float, cy: float, letter: str) -> None:
    """Pneu: anel na cor do composto e a letra dentro."""
    color = compound_color(letter)
    p.setBrush(QColor(theme.BG))
    p.setPen(QPen(QColor(color), 3.2))
    p.drawEllipse(QPointF(cx, cy), 10.5, 10.5)
    p.setPen(QColor(color))
    p.setFont(make_font(12, True))
    p.drawText(QRectF(cx - 10, cy - 10, 20, 20), Qt.AlignCenter, letter[:1])


class LogoCache:
    """Logotipos REAIS das marcas, lidos de `<pasta>/<chave>.<ext>` (png, webp, jpg ou svg).

    Os arquivos vêm do download (`core/logos.py`) ou são colocados pelo usuário. Cada imagem é reduzida uma vez
    (mantendo a proporção) e depois desenhada no tamanho pedido. Sem o arquivo: o NOME da fabricante em texto
    (`wordmark`, desligável) e a marca entra em `missing_seen`, para o app dizer exatamente o que falta.
    """

    SIZE = 96  # resolução do cache: folga para a logo ficar nítida mesmo com o módulo ampliado

    def __init__(self, directory: Optional[Path] = None, wordmark: bool = True):
        self.dir = Path(directory) if directory else None
        self.wordmark = wordmark
        self.missing_seen: dict[str, Brand] = {}  # marcas vistas em carros da sessão que não têm arquivo de logo
        self._cache: dict[str, Optional[QPixmap]] = {}
        self.unrecognized_seen: dict[tuple, bool] = {}  # (equipe, texto do veículo) sem marca reconhecida

    def clear(self) -> None:
        """Esquece o cache (após baixar logos novos ou o usuário colocar arquivos)."""
        self._cache.clear()
        self.missing_seen.clear()
        self.unrecognized_seen.clear()

    def note_unrecognized(self, team: Optional[str], raw: Optional[str], cls: Optional[str] = None) -> None:
        """Carro sem marca reconhecida: anotado para "Logos que faltam"."""
        if team or raw:
            self.unrecognized_seen.setdefault((team or "", raw or "", cls or ""), True)

    def _load(self, path: Path) -> Optional[QPixmap]:
        if path.suffix.lower() == ".svg":
            if QSvgRenderer is None:
                return None
            renderer = QSvgRenderer(str(path))
            if not renderer.isValid():
                return None
            size = renderer.defaultSize()
            scale = self.SIZE / max(size.width(), size.height(), 1)
            pm = QPixmap(max(1, int(size.width() * scale)), max(1, int(size.height() * scale)))
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()
            return pm
        pm = QPixmap(str(path))
        if pm.isNull():
            return None
        return pm.scaled(self.SIZE, self.SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def get(self, key: str, fallback: Optional[str] = None) -> Optional[QPixmap]:
        for k in (key, fallback):
            if not k or self.dir is None:
                continue
            if k not in self._cache:
                path = logo_file(self.dir, k)
                self._cache[k] = self._load(path) if path is not None else None
            if self._cache[k] is not None:
                return self._cache[k]
        return None

    def draw(self, p: QPainter, brand: Brand, cx: float, cy: float, size: float = 30.0) -> bool:
        pm = self.get(brand.key, brand.fallback)
        if pm is None:
            self.missing_seen.setdefault(brand.key, brand)  # anotado: aparece em "Logos que faltam"
            return False
        scale = size / max(pm.width(), pm.height(), 1)
        w, h = pm.width() * scale, pm.height() * scale
        p.drawPixmap(QRectF(cx - w / 2, cy - h / 2, w, h), pm, QRectF(0, 0, pm.width(), pm.height()))
        return True


WORDMARK_COLOR = "#c9ccd3"
WORDMARK_W = 40.0  # largura inteira da coluna de marca


def wordmark(p: QPainter, cx: float, cy: float, name: str, width: float = WORDMARK_W) -> None:
    """Nome da fabricante em texto (sem círculo nem sigla), em até 2 linhas, ajustado à largura da coluna."""
    text = name.upper().replace("-", " ")  # "Mercedes-AMG" -> MERCEDES / AMG
    words = text.split()
    lines = [text] if (len(words) == 1 or len(text) <= 8) else [" ".join(words[:-1]), words[-1]]
    px = 12.0 if len(lines) == 1 else 9.5
    line_h = px + 1.0
    top = cy - line_h * len(lines) / 2
    p.setPen(QColor(WORDMARK_COLOR))
    for i, line in enumerate(lines):
        p.setFont(fit_font(p, line, px, width, True, 7.0))
        p.drawText(QRectF(cx - width / 2, top + i * line_h, width, line_h), Qt.AlignCenter, line)


def brand_logo(p: QPainter, cx: float, cy: float, brand: Brand, logos: Optional[LogoCache],
               size: float = 30.0) -> bool:
    """Desenha a logo real da marca. Sem o arquivo, desenha o nome da fabricante em texto (se `wordmark` ligado)."""
    if logos is None:
        return False
    if logos.draw(p, brand, cx, cy, size):
        return True
    if getattr(logos, "wordmark", False):
        wordmark(p, cx, cy, brand.display_name)
        return True
    return False


class FlagCache:
    """Bandeiras de países/regiões, lidas de `<pasta>/<codigo>.png` (ver `core/flags.py` para baixá-las)."""

    SIZE = 96  # largura máxima do cache

    def __init__(self, directory: Optional[Path] = None):
        self.dir = Path(directory) if directory else None
        self._cache: dict[str, Optional[QPixmap]] = {}

    def clear(self) -> None:
        self._cache.clear()

    def get(self, code: str) -> Optional[QPixmap]:
        if not code or self.dir is None:
            return None
        if code not in self._cache:
            path = self.dir / f"{code}.png"
            pm = QPixmap(str(path)) if path.is_file() else None
            if pm is not None and not pm.isNull():
                pm = pm.scaled(self.SIZE, self.SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                pm = None
            self._cache[code] = pm
        return self._cache[code]

    def draw(self, p: QPainter, code: str, x: float, y: float, w: float = 26.0, h: float = 18.0) -> bool:
        """Desenha a bandeira dentro do retângulo (x, y, w, h), mantendo a proporção, com cantos arredondados."""
        pm = self.get(code)
        if pm is None:
            return False
        scale = min(w / max(pm.width(), 1), h / max(pm.height(), 1))
        fw, fh = pm.width() * scale, pm.height() * scale
        target = QRectF(x + (w - fw) / 2, y + (h - fh) / 2, fw, fh)
        clip = QPainterPath()
        clip.addRoundedRect(target, 2.5, 2.5)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(target, pm, QRectF(0, 0, pm.width(), pm.height()))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 90), 1))
        p.drawRoundedRect(target, 2.5, 2.5)  # contorno discreto: bandeiras brancas não somem no fundo claro
        return True


# --------------------------------------------------------------------------- #
# Ícones de rank do LMU (Driver Rank / Safety Rank / Driver Contact Badge)
class BadgeCache:
    """`<pasta>/<chave>.png` do usuário; sem arquivo, os selos de contato conhecidos são desenhados como losangos."""

    SIZE = 96

    def __init__(self, directory: Optional[Path] = None):
        self.dir = Path(directory) if directory else None
        self._cache: dict[str, Optional[QPixmap]] = {}

    def clear(self) -> None:
        self._cache.clear()

    def available(self, key: Optional[str]) -> bool:
        return badges.has_icon(self.dir, key)

    def pixmap(self, key: str) -> Optional[QPixmap]:
        if key not in self._cache:
            path = badges.badge_file(self.dir, key)
            pm = QPixmap(str(path)) if path is not None and path.suffix.lower() != ".svg" else None
            self._cache[key] = pm.scaled(self.SIZE, self.SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation) \
                if pm is not None and not pm.isNull() else None
        return self._cache[key]


def _diamond_path(cx: float, cy: float, r: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(-r * 0.72, -r * 0.72, r * 1.44, r * 1.44), r * 0.32, r * 0.32)
    from PySide6.QtGui import QTransform
    return QTransform().translate(cx, cy).rotate(45).map(path)


def contact_badge(p: QPainter, cx: float, cy: float, key: str, cache: Optional[BadgeCache], size: float = 30.0) -> bool:
    """Desenha o ícone do rank. True se desenhou (arquivo do usuário ou selo de contato conhecido)."""
    if cache is None or not cache.available(key):
        return False
    pm = cache.pixmap(key)
    if pm is not None:
        scale = size / max(pm.width(), pm.height(), 1)
        w, h = pm.width() * scale, pm.height() * scale
        p.drawPixmap(QRectF(cx - w / 2, cy - h / 2, w, h), pm, QRectF(0, 0, pm.width(), pm.height()))
        return True
    name, fill, ink = badges.CONTACT_BADGES[key]
    r = size / 2
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(fill))
    p.drawPath(_diamond_path(cx, cy, r))
    pen = QPen(QColor(ink), max(2.0, size * 0.09))
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    k = size * 0.2
    if key == "rookie":  # X
        p.drawLine(QPointF(cx - k, cy - k), QPointF(cx + k, cy + k))
        p.drawLine(QPointF(cx - k, cy + k), QPointF(cx + k, cy - k))
    elif key == "good":  # visto
        p.drawPolyline([QPointF(cx - k, cy), QPointF(cx - k * 0.3, cy + k * 0.8), QPointF(cx + k, cy - k * 0.8)])
    elif key == "trusted":  # gema
        p.drawPolygon([QPointF(cx - k, cy - k * 0.4), QPointF(cx - k * 0.5, cy - k), QPointF(cx + k * 0.5, cy - k),
                       QPointF(cx + k, cy - k * 0.4), QPointF(cx, cy + k)])
    elif key == "warning":  # !
        p.drawLine(QPointF(cx, cy - k), QPointF(cx, cy + k * 0.2))
        p.drawPoint(QPointF(cx, cy + k * 0.85))
    elif key == "probation":  # proibido
        p.drawEllipse(QPointF(cx, cy), k, k)
        p.drawLine(QPointF(cx - k * 0.7, cy + k * 0.7), QPointF(cx + k * 0.7, cy - k * 0.7))
    else:  # creator / driver / staff: inicial
        p.setFont(make_font(max(8, int(size * 0.42)), True))
        p.drawText(QRectF(cx - r, cy - r, size, size), Qt.AlignCenter, {"creator": "C", "driver": "D"}.get(key, "S"))
    return True
