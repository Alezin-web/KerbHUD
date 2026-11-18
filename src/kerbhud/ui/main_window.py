"""Janela principal (estilo TinyPedal): barra de menus, abas Módulos/Layouts e rodapé de estado.

Fechar a janela só a esconde: o KerbHUD continua na bandeja (o item "Sair" encerra de verdade).
A janela não guarda lógica: cada ação chama o gerenciador, o motor ou o `Tray`, que já fazem o trabalho.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget)

from .. import __version__
from ..core.i18n import get_language, module_title, tr
from ..core import visibility
from ..core.layout import MODULES
from ..core.settings_schema import SIMULATOR_LABELS, SIMULATORS, UNIT_LABELS, UNITS
from ..providers.demo import SCENARIOS
from ..core.module_options import has_options
from ..core.changelog import load_changelog
from .changelog_dialog import WelcomeDialog
from .settings_dialog import LayoutsPanel, ModuleConfigDialog



def _act(text, *args, **kwargs):
    """QAction com o texto traduzido para o idioma escolhido."""
    return QAction(tr(text), *args, **kwargs)


class ModulesPanel(QWidget):
    """Uma linha por módulo: liga/desliga e regra de visibilidade (seguir a geral, sempre, só pista, só garagem)."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.m = manager
        self.rows: dict[str, tuple[QCheckBox, QComboBox]] = {}
        outer = QVBoxLayout(self)
        inner = QWidget()
        col = QVBoxLayout(inner)
        for mid, spec in MODULES.items():
            row = QHBoxLayout()
            cb = QCheckBox(module_title(mid, spec.title).title())
            cb.toggled.connect(lambda on, k=mid: self._toggle(k, on))
            combo = QComboBox()
            for mode, label in ((visibility.GLOBAL, "Regra geral"), *visibility.MODE_LABELS.items()):
                combo.addItem(tr(label), mode)
            combo.currentIndexChanged.connect(lambda _i, k=mid, c=combo: self._show_when(k, c.currentData()))
            cfg = QPushButton(tr("Config"))
            cfg.setEnabled(has_options(mid))
            cfg.clicked.connect(lambda _c=False, k=mid: self._config(k))
            row.addWidget(cb, 1)
            row.addWidget(cfg)
            row.addWidget(combo)
            col.addLayout(row)
            self.rows[mid] = (cb, combo)
        col.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._busy = False
        self.refresh()

    def _config(self, mid: str) -> None:
        dlg = ModuleConfigDialog(self.m, mid, self)
        self._dlg = dlg  # mantém viva
        dlg.show()

    def refresh(self) -> None:
        """Relê o layout ativo (ele pode ter mudado por atalho, bandeja ou outra aba)."""
        self._busy = True
        try:
            for mid, (cb, combo) in self.rows.items():
                st = self.m.layout.modules[mid]
                cb.setChecked(bool(st.visible))
                combo.setCurrentIndex(max(0, combo.findData(st.options.get("show_when", visibility.GLOBAL))))
        finally:
            self._busy = False

    def _toggle(self, mid: str, on: bool) -> None:
        if not self._busy:
            self.m.set_module_visible(mid, on)

    def _show_when(self, mid: str, mode) -> None:
        if not self._busy and mode:
            self.m.set_module_show_when(mid, mode)


class UpdateBar(QWidget):
    """Faixa fixa no topo da janela: versão instalada + botão de verificar/baixar a atualização."""

    def __init__(self, controller_getter: Callable[[], object], parent=None):
        super().__init__(parent)
        self._ctl = controller_getter
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel(f"KerbHUD {__version__}")
        self.button = QPushButton(tr("Verificar atualizações"))
        self.button.clicked.connect(self._click)
        row.addWidget(self.label, 1)
        row.addWidget(self.button)
        self.refresh()

    def _click(self) -> None:
        ctl = self._ctl()
        if ctl is not None:
            ctl.check()

    def refresh(self) -> None:
        ctl = self._ctl()
        state, msg = (ctl.state, ctl.message) if ctl is not None else ("idle", "")
        info = getattr(ctl, "available", None) if ctl is not None else None
        text = f"KerbHUD {__version__}"
        btn, enabled, style = tr("Verificar atualizações"), True, ""
        if state == "checking":
            text, btn, enabled = f"{text}  ·  {tr('verificando...')}", tr("Verificando..."), False
        elif state == "available" and info is not None:
            text = f"{text}  ·  " + tr("nova versão {} disponível").format(info.version)
            btn, style = tr("Baixar e instalar {}").format(info.version), "font-weight: bold; background: #1f8f3a; color: white; padding: 4px 10px;"
        elif state == "installing":
            text, btn, enabled = f"{text}  ·  {msg}", tr("Atualizando..."), False
        elif state in ("uptodate", "error") and msg:
            text = f"{text}  ·  {msg}"
        self.label.setText(text)
        self.button.setText(btn)
        self.button.setEnabled(enabled)
        self.button.setStyleSheet(style)


class MainWindow(QMainWindow):
    def __init__(self, tray, manager, engine, settings: dict, save_setting: Callable[[str, object], None],
                 quit_app: Callable[[], None]):
        super().__init__()
        self.tray, self.m, self.engine, self.settings = tray, manager, engine, settings
        self._save, self._quit_app = save_setting, quit_app
        self._quitting = False
        self._told_tray = False
        self.setWindowTitle(f"KerbHUD {__version__}")
        self.resize(*self._initial_size())

        self.tabs = QTabWidget()
        self.modules_panel = ModulesPanel(manager)
        self.layouts_panel = LayoutsPanel(manager)
        self.tabs.addTab(self.modules_panel, "Widgets")
        self.tabs.addTab(self.layouts_panel, "Layouts")
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        self.updates = None  # UpdateController (ligado depois por set_updates)
        self.update_bar = UpdateBar(lambda: self.updates)
        central = QWidget()
        col = QVBoxLayout(central)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self.update_bar)
        col.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        self._build_menus()
        self._timer = QTimer(self)  # mantém rodapé e abas em dia (atalhos e bandeja mudam o estado por fora)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self.refresh()

    def set_updates(self, controller) -> None:
        self.updates = controller
        controller.listeners.append(self.update_bar.refresh)
        self.update_bar.refresh()

    def show_welcome(self, tab: str = "news", entries=None, title: str = "", first_run: bool = False) -> None:
        """Janela com o Guia de uso e as Novidades (identidade do KerbHUD); `tab`: "guide" ou "news"."""
        entries = load_changelog(language=get_language()) if entries is None else entries
        dlg = WelcomeDialog(entries, self.settings.get("hotkeys"), title or tr("Novidades do KerbHUD"), tab, first_run, self)
        self._welcome = dlg  # mantém viva
        dlg.show()

    show_changelog = show_welcome  # nome antigo

    # ---- tamanho / posição ------------------------------------------------ #
    def _initial_size(self) -> tuple[int, int]:
        g = self.settings.get("window_geometry")
        if self.settings.get("remember_window", True) and isinstance(g, (list, tuple)) and len(g) == 4:
            try:
                return max(360, int(g[2])), max(420, int(g[3]))
            except (TypeError, ValueError):
                pass
        return 460, 560

    def restore_position(self) -> None:
        g = self.settings.get("window_geometry")
        if self.settings.get("remember_window", True) and isinstance(g, (list, tuple)) and len(g) == 4:
            try:
                from PySide6.QtGui import QGuiApplication
                x, y = int(g[0]), int(g[1])
                if any(s.geometry().contains(x + 20, y + 20) for s in QGuiApplication.screens()):  # monitor sumiu?
                    self.move(x, y)
            except (TypeError, ValueError):
                pass

    def _remember(self) -> None:
        if self.settings.get("remember_window", True):
            g = self.geometry()
            val = [g.x(), g.y(), g.width(), g.height()]
            self.settings["window_geometry"] = val
            self._save("window_geometry", val)

    # ---- menus ------------------------------------------------------------ #
    def _build_menus(self) -> None:
        bar = self.menuBar()
        m, t = self.m, self.tray

        ov = bar.addMenu(tr("Overlay"))
        self.act_edit = QAction(tr("Modo de edição"), ov, checkable=True)
        self.act_edit.triggered.connect(lambda on: m.set_edit_mode(bool(on)))
        self.act_visible = QAction(tr("Overlay visível"), ov, checkable=True)
        self.act_visible.triggered.connect(lambda _on: m.toggle_overlay())
        self.act_top = QAction(tr("Sempre no topo"), ov, checkable=True)
        self.act_top.triggered.connect(lambda on: m.set_always_on_top(bool(on)))
        for a in (self.act_edit, self.act_visible, self.act_top):
            ov.addAction(a)
        ov.addSeparator()
        ov.addAction(tr("Recarregar logos e bandeiras"), lambda: (m.reload_logos(), m.reload_flags()))
        ov.addSeparator()
        ov.addAction(tr("Sair"), self.quit)

        sim = bar.addMenu(tr("Simulador"))
        self._sim_group = QActionGroup(sim)
        self._sim_actions: dict[str, QAction] = {}
        for key in SIMULATORS:
            a = _act(SIMULATOR_LABELS[key], sim, checkable=True)
            a.triggered.connect(lambda _c=False, k=key: self.engine.set_simulator(k))
            self._sim_group.addAction(a)
            sim.addAction(a)
            self._sim_actions[key] = a
        sim.addSeparator()
        demo = sim.addMenu(tr("DEMO: cenário"))
        self._demo_group = QActionGroup(demo)
        self._demo_actions: dict[str, QAction] = {}
        for key, label in SCENARIOS.items():
            a = _act(label, demo, checkable=True)
            a.triggered.connect(lambda _c=False, k=key: t._pick_demo(k))
            self._demo_group.addAction(a)
            demo.addAction(a)
            self._demo_actions[key] = a
        demo.addSeparator()
        demo.addAction(tr("Pular para a próxima etapa"), self.engine.demo_next_stage)

        cfg = bar.addMenu(tr("Config"))
        cfg.addAction(tr("Configurações..."), t._open_settings)
        units = cfg.addMenu(tr("Unidades"))
        self._unit_group = QActionGroup(units)
        self._unit_actions: dict[str, QAction] = {}
        for key in UNITS:
            a = _act(UNIT_LABELS[key], units, checkable=True)
            a.triggered.connect(lambda _c=False, k=key: m.set_units(k))
            self._unit_group.addAction(a)
            units.addAction(a)
            self._unit_actions[key] = a
        self.act_wordmark = QAction(tr("Nome da fabricante quando não houver logo"), cfg, checkable=True)
        self.act_wordmark.toggled.connect(t._set_logo_wordmark)
        cfg.addAction(self.act_wordmark)

        tools = bar.addMenu(tr("Ferramentas"))
        tools.addAction(tr("Baixar logos de carros (internet)..."), t._download_logos)
        tools.addAction(tr("Baixar bandeiras dos países (internet)..."), t._download_flags)
        tools.addAction(tr("Logos que faltam..."), t._show_missing_logos)
        tools.addSeparator()
        tools.addAction(tr("Regravar o traçado desta pista"), t._regravar_tracado)
        folders = tools.addMenu(tr("Abrir pasta"))
        folders.addAction(tr("Logos de carros"), t._open_logos)
        folders.addAction(tr("Bandeiras"), t._open_flags)
        folders.addAction(tr("Ícones de rank (LMU)"), t._open_badges)
        folders.addAction(tr("Todos os dados (logos, flags, badges, layouts, tracks)"), t._open_data)
        folders.addAction(tr("Configuração (settings.json)"), t._open_config)

        win = bar.addMenu(tr("Janela"))
        self._flags: dict[str, QAction] = {}
        for key, label in (("show_window_at_startup", "Abrir esta janela ao iniciar"),
                           ("close_to_tray", "Fechar = minimizar para a bandeja"),
                           ("remember_window", "Lembrar posição e tamanho")):
            a = _act(label, win, checkable=True)
            a.setChecked(bool(self.settings.get(key, True)))
            a.toggled.connect(lambda on, k=key: self._set_flag(k, on))
            win.addAction(a)
            self._flags[key] = a
        win.addSeparator()
        win.addAction(tr("Esconder na bandeja"), self.hide)

        helpm = bar.addMenu(tr("Ajuda"))
        helpm.addAction(tr("Verificar atualizações..."), lambda: self.updates.check() if self.updates else None)
        helpm.addAction(tr("Abrir pasta de dados"), t._open_data)
        helpm.addSeparator()
        helpm.addAction(tr("Guia de uso"), lambda: self.show_welcome("guide", load_changelog(language=get_language())[:6]))
        helpm.addAction(tr("Novidades (changelog)"), lambda: self.show_welcome("news", load_changelog(language=get_language())[:6]))
        helpm.addAction(tr("Sobre"), self._about)

    def _set_flag(self, key: str, on: bool) -> None:
        self.settings[key] = bool(on)
        self._save(key, bool(on))

    def _about(self) -> None:
        QMessageBox.information(
            self, tr("Sobre o KerbHUD"),
            f"KerbHUD {__version__}\n\n" + tr("Overlay somente-leitura para iRacing e Le Mans Ultimate. "
            "Não injeta código, não altera arquivos do jogo e não envia comandos.\n\n"
            "Atalhos e demais opções: Config → Configurações..."))

    # ---- estado ------------------------------------------------------------ #
    def refresh(self) -> None:
        m, st = self.m, self.settings
        self.act_edit.setChecked(m.edit_mode)
        self.act_visible.setChecked(m.overlay_visible)
        self.act_top.setChecked(bool(m.layout.always_on_top))
        sim = st.get("simulator", "auto")
        if sim in self._sim_actions:
            self._sim_actions[sim].setChecked(True)
        sc = st.get("demo_scenario", "tour")
        if sc in self._demo_actions:
            self._demo_actions[sc].setChecked(True)
        self._unit_actions[m.ctx.units].setChecked(True)
        logos = m.ctx.logos
        self.act_wordmark.setChecked(bool(logos is not None and logos.wordmark))
        self.status.setText(f"KerbHUD {__version__}   |   {tr('Layout')}: {m.layout.name}   |   "
                            f"{tr('Simulador')}: {tr(SIMULATOR_LABELS.get(sim, sim))}")
        self.modules_panel.refresh()

    def _tick(self) -> None:
        if self.isVisible() and not self.layouts_panel.lay_list.hasFocus():
            self.refresh()
            self.layouts_panel._refresh_layouts()

    # ---- ciclo de vida ----------------------------------------------------- #
    def show_and_raise(self) -> None:
        self.show()
        self.setWindowState(self.windowState() & ~self._minimized_flag())
        self.raise_()
        self.activateWindow()

    @staticmethod
    def _minimized_flag():
        from PySide6.QtCore import Qt
        return Qt.WindowMinimized

    def quit(self) -> None:
        self._quitting = True
        self._remember()
        self._quit_app()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._remember()
        if self._quitting or not self.settings.get("close_to_tray", True):
            event.accept()
            if not self._quitting:  # fechar de vez a janela sem bandeja encerra o programa
                self._quitting = True
                self._quit_app()
            return
        event.ignore()
        self.hide()
        if not self._told_tray:
            self._told_tray = True
            self.tray.tray.showMessage(tr("KerbHUD"), tr("Continua rodando na bandeja. Clique no ícone para abrir "
                                       "a janela; para encerrar use Overlay → Sair."), QSystemTrayIcon.Information, 5000)
