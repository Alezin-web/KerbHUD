"""Janela de boas-vindas do KerbHUD: abas **Guia de uso** e **Novidades**, com a identidade visual (logo + zebra).

O conteúdo vem de `GUIDE.md` e `CHANGELOG.md` (Markdown restrito -> HTML seguro, ver core/changelog).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QDialog, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout

from ..core import brand
from ..core.changelog import (PAGE_CSS, Entry, branded_page, entries_to_html, guide_html, hotkeys_md, load_guide,
                              resource_root)
from ..core.i18n import get_language, tr
from ..core.settings_schema import HOTKEY_LABELS


def _browser(html_text: str, images: Path) -> QTextBrowser:
    view = QTextBrowser()
    view.setOpenLinks(False)  # nada de abrir endereços; é só leitura
    view.setSearchPaths([str(images)])
    view.setStyleSheet(f"QTextBrowser {{ background-color: {brand.ASPHALT}; color: {brand.WHITE}; border: none; }}")
    view.document().setDefaultStyleSheet(PAGE_CSS)
    view.setHtml(html_text)
    return view


class WelcomeDialog(QDialog):
    def __init__(self, entries: list[Entry], hotkeys: Optional[dict] = None, title: str = "", initial: str = "news",
                 first_run: bool = False, parent=None, root: Optional[Path] = None):
        super().__init__(parent)
        self.setWindowTitle(title or tr("Novidades do KerbHUD"))
        base = root or resource_root()
        images = base / "changelog"
        tagline = brand.TAGLINE_EN if get_language() == "en" else brand.TAGLINE_PT
        hk = hotkeys_md(hotkeys or {}, lambda a: tr(HOTKEY_LABELS.get(a, a)))
        guide = guide_html(load_guide(base, get_language()), hk, images)
        news = entries_to_html(entries, images)
        self.tabs = QTabWidget()
        self.tabs.addTab(_browser(branded_page(guide, tagline, images), images), tr("Guia de uso"))
        self.tabs.addTab(_browser(branded_page(news, tagline, images), images), tr("Novidades"))
        self.tabs.setCurrentIndex(0 if initial == "guide" else 1)
        close = QPushButton(tr("Começar") if first_run else tr("Fechar"))
        close.clicked.connect(self.accept)
        col = QVBoxLayout(self)
        col.addWidget(self.tabs, 1)
        col.addWidget(close)
        self.resize(640, 700)


ChangelogDialog = WelcomeDialog  # nome antigo
