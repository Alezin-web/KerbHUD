"""Aplicativo: ícone de bandeja, atalhos globais e ciclo de vida."""
from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QAbstractNativeEventFilter, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMenu, QMessageBox, QSystemTrayIcon

from .. import __version__
from ..core.i18n import get_language, module_title, resolve_language, set_language, tr
from ..core import brand, winapi
from ..core.engine import Engine, load_settings, update_settings_file, write_settings_file
from ..core import visibility
from ..providers.demo import SCENARIOS
from ..core.history import TelemetryHistory
from ..core.layout import MODULES, LayoutStore
from ..core.logos import fetch_logos, installed_logos
from ..core.flags import FlagResolver, fetch_flags
from ..core.log import get_logger, install_excepthooks, setup_logging
from ..core.fuel import RESERVE_CHOICES, get_reserve
from ..core.radar import RANGE_CHOICES, get_range
from ..core.tireview import PRESSURE_UNITS, get_pressure_unit
from ..core.settings_schema import apply_patch
from ..core.paths import data_dir, migrate_legacy_assets, migrate_legacy_config, badges_dir, config_dir, flags_dir, layouts_dir, logos_dir, tracks_dir
from ..core.relative import AHEAD_CHOICES, FIGHT_CHOICES, get_relative_options
from ..core.standings import (COLUMN_KEYS, COLUMN_LABELS, get_standings_options)
from ..core.viewmodel import (CHANNEL_LABELS, CHANNELS, HISTORY_CHOICES, TRACE_CHOICES,
                              get_channels, get_history_s, get_trace_s)
from . import icons
from .context import ModuleContext
from .main_window import MainWindow
from .overlay_manager import OverlayManager
from .update_ui import UpdateController
from .settings_dialog import SettingsDialog



def _act(text, *args, **kwargs):
    """QAction com o texto traduzido para o idioma escolhido."""
    return QAction(tr(text), *args, **kwargs)


def _draw_icon(size: int) -> QPixmap:
    """O logo do KerbHUD (K de cantos cortados sobre a zebra) no tamanho pedido; geometria em core/brand."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    tile = QPainterPath()
    r = brand.TILE_RADIUS * size
    tile.addRoundedRect(0.0, 0.0, float(size), float(size), r, r)
    p.setClipPath(tile)
    p.fillRect(0, 0, size, size, QColor(brand.ASPHALT))
    for pts, color in (*brand.kerb_stripes(), *brand.k_parts()):
        path = QPainterPath()
        path.moveTo(pts[0][0] * size, pts[0][1] * size)
        for x, y in pts[1:]:
            path.lineTo(x * size, y * size)
        path.closeSubpath()
        p.fillPath(path, QColor(color))
    p.end()
    return pm


def app_icon() -> QIcon:
    """Ícone do KerbHUD (logo K + zebra) em vários tamanhos: janela, barra de tarefas e bandeja."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(_draw_icon(size))
    return icon


_tray_icon = app_icon  # nome antigo


class _HotkeyFilter(QAbstractNativeEventFilter):
    """Recebe WM_HOTKEY da fila de mensagens do Qt (somente Windows)."""

    def __init__(self, registry: winapi.HotkeyRegistry, handler):
        super().__init__()
        self._registry = registry
        self._handler = handler

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if winapi.IS_WIN and bytes(event_type) == b"windows_generic_MSG":
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == winapi.WM_HOTKEY:
                action = self._registry.action_for(int(msg.wParam))
                if action:
                    self._handler(action)
                    return True, 0
        return False, 0


class Tray:
    def __init__(self, app: QApplication, manager: OverlayManager, engine: Engine, hotkeys_errors: list[str],
                 apply_settings=None):
        self.app, self.m, self.engine = app, manager, engine
        self._apply_settings = apply_settings
        self._dialog = None
        self.window = None  # MainWindow (definida depois pelo run())
        self.updates = None  # UpdateController (definido pelo run())
        self.tray = QSystemTrayIcon(_tray_icon(), app)
        self.menu = QMenu()
        self.menu.aboutToShow.connect(self.rebuild)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.setToolTip(f"KerbHUD {__version__}")
        self.tray.show()
        self.hotkey_errors = hotkeys_errors
        self.rebuild()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        if self.window is not None:
            self.window.show_and_raise()

    def quit(self) -> None:
        if self.window is not None:
            self.window.quit()
        else:
            self.app.quit()

    def notify_hotkey_errors(self) -> None:
        if self.hotkey_errors:
            self.tray.showMessage(tr("KerbHUD: atalhos"), "\n".join(self.hotkey_errors),
                                  QSystemTrayIcon.Warning, 8000)

    def rebuild(self) -> None:
        m = self.m
        menu = self.menu
        menu.clear()

        hk = self.engine.settings.get("hotkeys", {})

        def hint(action: str) -> str:
            return f"  ({hk[action]})" if hk.get(action) else ""

        menu.addAction(tr("Abrir janela principal"), self.show_window)
        menu.addAction(tr("Configurações..."), self._open_settings)
        menu.addSeparator()
        act = _act(tr("Modo de edição") + hint("toggle_edit"), menu, checkable=True)
        act.setChecked(m.edit_mode)
        act.toggled.connect(m.set_edit_mode)
        menu.addAction(act)

        act = _act(tr("Overlay visível") + hint("toggle_overlay"), menu, checkable=True)
        act.setChecked(m.overlay_visible)
        act.toggled.connect(lambda _on: m.toggle_overlay())
        menu.addAction(act)

        act = QAction(tr("Sempre no topo"), menu, checkable=True)
        act.setChecked(m.layout.always_on_top)
        act.toggled.connect(m.set_always_on_top)
        menu.addAction(act)

        menu.addSeparator()
        lay_menu = menu.addMenu(tr("Layouts"))
        group = QActionGroup(lay_menu)
        group.setExclusive(True)
        for name in m.store.list_names():
            a = _act(name, lay_menu, checkable=True)
            a.setChecked(name == m.layout.name)
            a.triggered.connect(lambda _c=False, n=name: m.switch_layout(n))
            group.addAction(a)
            lay_menu.addAction(a)
        lay_menu.addSeparator()
        lay_menu.addAction(tr("Salvar como novo layout..."), self._save_as)
        lay_menu.addAction(tr("Renomear layout atual..."), self._rename_current)
        lay_menu.addAction(tr("Duplicar layout atual"), self._duplicate_current)
        lay_menu.addAction(tr("Exportar layout atual..."), self._export_current)
        lay_menu.addAction(tr("Importar layout..."), self._import_layout)
        lay_menu.addAction(tr("Excluir layout atual..."), self._delete_current)
        lay_menu.addAction(tr("Restaurar layouts padrão..."), self._reset_defaults)

        mod_menu = menu.addMenu(tr("Módulos"))
        for mid, spec in MODULES.items():
            a = _act(module_title(mid, spec.title).title(), mod_menu, checkable=True)
            a.setChecked(m.layout.modules[mid].visible)
            a.toggled.connect(lambda on, k=mid: m.set_module_visible(k, on))
            mod_menu.addAction(a)

        vis_menu = menu.addMenu(tr("Mostrar o overlay"))
        vis_group = QActionGroup(vis_menu)
        for mode in visibility.MODES:
            a = _act(visibility.MODE_LABELS[mode], vis_menu, checkable=True)
            a.setChecked(visibility.normalize(self.engine.settings.get("visibility")) == mode)
            a.triggered.connect(lambda _c=False, k=mode: m.set_global_visibility(k))
            vis_group.addAction(a)
            vis_menu.addAction(a)
        vis_menu.addSeparator()
        for mid, spec in MODULES.items():
            sub_m = vis_menu.addMenu(module_title(mid, spec.title).title())
            grp = QActionGroup(sub_m)
            cur = m.layout.modules[mid].options.get("show_when", visibility.GLOBAL)
            for mode, label in ((visibility.GLOBAL, "Seguir a regra geral"), *visibility.MODE_LABELS.items()):
                a = _act(label, sub_m, checkable=True)
                a.setChecked(cur == mode)
                a.triggered.connect(lambda _c=False, k=mid, v=mode: m.set_module_show_when(k, v))
                grp.addAction(a)
                sub_m.addAction(a)

        st_menu = menu.addMenu(tr("Standings"))
        so = get_standings_options(m.layout.modules["standings"].options)
        scope_group = QActionGroup(st_menu)
        for key, label in (("all", "Todas as classes"), ("class", "Só a minha classe")):
            a = _act(label, st_menu, checkable=True)
            a.setChecked(so.scope == key)
            a.triggered.connect(lambda _c=False, k=key: m.set_option("standings", "scope", k))
            scope_group.addAction(a)
            st_menu.addAction(a)
        st_menu.addSeparator()
        st_menu.addAction(tr("Aumentar o texto (+10%)"), lambda: m.zoom_module("standings", 1.10))
        st_menu.addAction(tr("Diminuir o texto (-10%)"), lambda: m.zoom_module("standings", 1 / 1.10))
        st_menu.addSeparator()
        a = QAction(tr("Animações de ultrapassagem"), st_menu, checkable=True)
        a.setChecked(so.animations)
        a.toggled.connect(lambda on: m.set_option("standings", "animations", bool(on)))
        st_menu.addAction(a)
        a = QAction(tr("Mostrar meu perfil no rodapé"), st_menu, checkable=True)
        a.setChecked(so.show_profile)
        a.toggled.connect(lambda on: m.set_option("standings", "show_profile", bool(on)))
        st_menu.addAction(a)
        st_menu.addSeparator()
        for key in COLUMN_KEYS:
            a = _act(COLUMN_LABELS[key], st_menu, checkable=True)
            a.setChecked(key in so.columns)
            a.toggled.connect(lambda on, k=key: m.set_column("standings", k, on))
            st_menu.addAction(a)

        rel_menu = menu.addMenu(tr("Relative"))
        ro = get_relative_options(m.layout.modules["relative"].options)
        for title, key, cur in (("Carros à frente", "ahead", ro.ahead), ("Carros atrás", "behind", ro.behind)):
            sub = rel_menu.addMenu(tr(title))
            grp = QActionGroup(sub)
            for n in AHEAD_CHOICES:
                a = _act(str(n), sub, checkable=True)
                a.setChecked(cur == n)
                a.triggered.connect(lambda _c=False, k=key, v=n: m.set_option("relative", k, v))
                grp.addAction(a)
                sub.addAction(a)
        fight = rel_menu.addMenu(tr("Disputa direta até"))
        fgrp = QActionGroup(fight)
        for secs in FIGHT_CHOICES:
            a = _act(f"{secs:.1f} s", fight, checkable=True)
            a.setChecked(abs(ro.fight_s - secs) < 0.05)
            a.triggered.connect(lambda _c=False, v=secs: m.set_option("relative", "fight_s", float(v)))
            fgrp.addAction(a)
            fight.addAction(a)
        a = QAction(tr("Animações de ultrapassagem"), rel_menu, checkable=True)
        a.setChecked(ro.animations)
        a.toggled.connect(lambda on: m.set_option("relative", "animations", bool(on)))
        rel_menu.addAction(a)
        a = QAction(tr("Mostrar iRating"), rel_menu, checkable=True)
        a.setChecked(ro.show_irating)
        a.toggled.connect(lambda on: m.set_option("relative", "show_irating", bool(on)))
        rel_menu.addAction(a)

        tel_menu = menu.addMenu(tr("Telemetria"))
        tel_opts = m.layout.modules["telemetry"].options
        chans = get_channels(tel_opts)
        for ch in CHANNELS:
            a = _act(CHANNEL_LABELS[ch], tel_menu, checkable=True)
            a.setChecked(chans[ch])
            a.toggled.connect(lambda on, c=ch: m.set_channel(c, on))
            tel_menu.addAction(a)
        tel_menu.addSeparator()
        hist_group = QActionGroup(tel_menu)
        cur = get_history_s(tel_opts)
        for secs in HISTORY_CHOICES:
            a = QAction(tr("Histórico: {} s").format(secs), tel_menu, checkable=True)
            a.setChecked(abs(cur - secs) < 0.5)
            a.triggered.connect(lambda _c=False, v=secs: m.set_option("telemetry", "history_s", float(v)))
            hist_group.addAction(a)
            tel_menu.addAction(a)

        inp_menu = menu.addMenu(tr("Inputs"))
        inp_menu.addAction(tr("Aumentar o texto (+10%)"), lambda: m.zoom_module("inputs", 1.10))
        inp_menu.addAction(tr("Diminuir o texto (-10%)"), lambda: m.zoom_module("inputs", 1 / 1.10))
        inp_menu.addSeparator()
        inp_opts = m.layout.modules["inputs"].options
        a = QAction(tr("Mostrar embreagem"), inp_menu, checkable=True)
        a.setChecked(inp_opts.get("show_clutch", True) is not False)
        a.toggled.connect(lambda on: m.set_option("inputs", "show_clutch", bool(on)))
        inp_menu.addAction(a)
        a = QAction(tr("Mostrar direção no gráfico"), inp_menu, checkable=True)
        a.setChecked(inp_opts.get("trace_steering") is True)
        a.toggled.connect(lambda on: m.set_option("inputs", "trace_steering", bool(on)))
        inp_menu.addAction(a)
        inp_menu.addSeparator()
        trace_group = QActionGroup(inp_menu)
        cur_trace = get_trace_s(inp_opts)
        for secs in TRACE_CHOICES:
            a = QAction(tr("Gráfico: {} s").format(secs), inp_menu, checkable=True)
            a.setChecked(abs(cur_trace - secs) < 0.5)
            a.triggered.connect(lambda _c=False, v=secs: m.set_option("inputs", "trace_s", float(v)))
            trace_group.addAction(a)
            inp_menu.addAction(a)

        fuel_menu = menu.addMenu(tr("Combustível"))
        fuel_group = QActionGroup(fuel_menu)
        cur_res = get_reserve(m.layout.modules["fuel"].options)
        for laps in RESERVE_CHOICES:
            a = QAction(tr("Reserva: {} volta(s)").format(f"{laps:g}"), fuel_menu, checkable=True)
            a.setChecked(abs(cur_res - laps) < 0.01)
            a.triggered.connect(lambda _c=False, v=laps: m.set_option("fuel", "reserve_laps", float(v)))
            fuel_group.addAction(a)
            fuel_menu.addAction(a)

        radar_menu = menu.addMenu(tr("Radar"))
        radar_group = QActionGroup(radar_menu)
        cur_rng = get_range(m.layout.modules["radar"].options)
        for rng in RANGE_CHOICES:
            a = QAction(tr("Alcance: {} m").format(f"{rng:g}"), radar_menu, checkable=True)
            a.setChecked(abs(cur_rng - rng) < 0.01)
            a.triggered.connect(lambda _c=False, v=rng: m.set_option("radar", "range_m", float(v)))
            radar_group.addAction(a)
            radar_menu.addAction(a)
        radar_menu.addSeparator()
        hide_on = bool(m.layout.modules["radar"].options.get("auto_hide", True))
        a = QAction(tr("Só aparecer quando há carro perto"), radar_menu, checkable=True)
        a.setChecked(hide_on)
        a.triggered.connect(lambda c=False: m.set_option("radar", "auto_hide", not hide_on))
        radar_menu.addAction(a)

        tire_menu = menu.addMenu(tr("Pneus"))
        tire_group = QActionGroup(tire_menu)
        cur_pu = get_pressure_unit(m.layout.modules["tires"].options)
        for unit in PRESSURE_UNITS:
            a = QAction(tr("Pressão em {}").format("PSI" if unit == "psi" else "kPa"), tire_menu, checkable=True)
            a.setChecked(cur_pu == unit)
            a.triggered.connect(lambda _c=False, v=unit: m.set_option("tires", "pressure_unit", v))
            tire_group.addAction(a)
            tire_menu.addAction(a)

        map_menu = menu.addMenu(tr("Track Map"))
        map_opts = m.layout.modules["trackmap"].options
        a = QAction(tr("Espelhar o traçado"), map_menu, checkable=True)
        a.setChecked(bool(map_opts.get("mirror", False)))
        a.toggled.connect(lambda on: m.set_option("trackmap", "mirror", bool(on)))
        map_menu.addAction(a)
        lab_group = QActionGroup(map_menu)
        cur_lab = map_opts.get("label", "class_pos")
        for key, text in (("class_pos", "Nos carros: posição na classe"), ("number", "Nos carros: número do carro"),
                          ("none", "Nos carros: sem texto")):
            a = _act(text, map_menu, checkable=True)
            a.setChecked(cur_lab == key)
            a.triggered.connect(lambda _c=False, k=key: m.set_option("trackmap", "label", k))
            lab_group.addAction(a)
            map_menu.addAction(a)
        map_menu.addAction(tr("Regravar o traçado desta pista"), self._regravar_tracado)

        unit_menu = menu.addMenu(tr("Unidades"))
        unit_group = QActionGroup(unit_menu)
        for key, label in (("kmh", "km/h"), ("mph", "mph")):
            a = _act(label, unit_menu, checkable=True)
            a.setChecked(m.ctx.units == key)
            a.triggered.connect(lambda _c=False, k=key: m.set_units(k))
            unit_group.addAction(a)
            unit_menu.addAction(a)

        sim_menu = menu.addMenu(tr("Simulador"))
        sim_group = QActionGroup(sim_menu)
        for key, label in (("auto", "Automático"), ("iracing", "iRacing"),
                           ("lmu", "Le Mans Ultimate"), ("demo", "DEMO (dados sintéticos)")):
            a = _act(label, sim_menu, checkable=True)
            a.setChecked(self.engine.settings.get("simulator") == key)
            a.triggered.connect(lambda _c=False, k=key: self.engine.set_simulator(k))
            sim_group.addAction(a)
            sim_menu.addAction(a)

        demo_menu = menu.addMenu(tr("DEMO: cenário"))
        demo_group = QActionGroup(demo_menu)
        cur_sc = self.engine.settings.get("demo_scenario", "tour")
        for key, label in SCENARIOS.items():
            a = _act(label, demo_menu, checkable=True)
            a.setChecked(cur_sc == key)
            a.triggered.connect(lambda _c=False, k=key: self._pick_demo(k))
            demo_group.addAction(a)
            demo_menu.addAction(a)
        demo_menu.addSeparator()
        demo_menu.addAction(tr("Pular para a próxima etapa"), self.engine.demo_next_stage)

        menu.addSeparator()
        about = menu.addAction(f"KerbHUD {__version__}")  # confirma qual versão está rodando
        about.setEnabled(False)
        menu.addAction(tr("Verificar atualizações..."), lambda: self.updates.check() if self.updates else None)
        menu.addAction(tr("Abrir pasta de dados (logos, flags, layouts...)"), self._open_data)
        menu.addAction(tr("Abrir pasta de configuração"), self._open_config)
        menu.addAction(tr("Baixar bandeiras dos países (internet)..."), self._download_flags)
        menu.addAction(tr("Abrir pasta de bandeiras"), self._open_flags)
        menu.addAction(tr("Abrir pasta de ícones de rank (LMU)"), self._open_badges)
        menu.addAction(tr("Baixar logos de carros (internet)..."), self._download_logos)
        menu.addAction(tr("Logos que faltam..."), self._show_missing_logos)
        menu.addAction(tr("Abrir pasta de logos de carros"), self._open_logos)
        menu.addAction(tr("Recarregar logos (depois de copiar arquivos)"), m.reload_logos)
        a = QAction(tr("Mostrar o nome da fabricante quando não houver logo"), menu, checkable=True)
        a.setChecked(bool(m.ctx.logos is not None and m.ctx.logos.wordmark))
        a.toggled.connect(self._set_logo_wordmark)
        menu.addAction(a)
        menu.addAction(tr("Sair"), self.quit)

    def _regravar_tracado(self) -> None:
        win = self.m.windows.get("trackmap")
        if win is not None and hasattr(win, "regravar"):
            win.regravar()

    def _pick_demo(self, key: str) -> None:
        """Escolher um cenário do DEMO já liga o modo DEMO (é o que a pessoa quer ver)."""
        self.engine.set_demo_scenario(key)
        if self.engine.settings.get("simulator") != "demo":
            self.engine.set_simulator("demo")

    def _save_as(self) -> None:
        name, ok = QInputDialog.getText(None, tr("Salvar layout"), tr("Nome do novo layout:"))
        if ok and name.strip():
            try:
                self.m.save_as(name)
            except ValueError as exc:
                QMessageBox.warning(None, tr("Nome inválido"), str(exc))

    def _open_settings(self) -> None:
        if self._dialog is not None and self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return
        self._dialog = SettingsDialog(self.engine.settings, self.m, self._apply_settings,
                                      self.updates.check if self.updates else None)
        self._dialog.show()

    def _rename_current(self) -> None:
        old = self.m.layout.name
        new, ok = QInputDialog.getText(None, tr("Renomear layout"), tr("Novo nome:"), text=old)
        if ok and new.strip() and new.strip() != old:
            try:
                self.m.rename_layout(old, new)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(None, tr("Renomear layout"), str(exc))

    def _duplicate_current(self) -> None:
        try:
            new = self.m.duplicate_layout(self.m.layout.name)
            self.tray.showMessage(tr("KerbHUD"), tr("Layout duplicado: {}").format(new), QSystemTrayIcon.Information, 4000)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(None, tr("Duplicar layout"), str(exc))

    def _export_current(self) -> None:
        name = self.m.layout.name
        path, _ = QFileDialog.getSaveFileName(None, tr("Exportar layout"), f"{name}.json", "Layout (*.json)")
        if path:
            try:
                self.m.export_layout(name, path)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(None, tr(tr("Exportar layout")), str(exc))

    def _import_layout(self) -> None:
        path, _ = QFileDialog.getOpenFileName(None, tr("Importar layout"), "", "Layout (*.json)")
        if path:
            try:
                new = self.m.import_layout(path)
                self.tray.showMessage(tr("KerbHUD"), tr("Layout importado: {}").format(new), QSystemTrayIcon.Information, 4000)
            except (OSError, ValueError) as exc:
                QMessageBox.warning(None, tr(tr("Importar layout")), str(exc))

    def _delete_current(self) -> None:
        name = self.m.layout.name
        if len(self.m.store.list_names()) <= 1:
            QMessageBox.information(None, tr("Excluir layout"), tr("Mantenha ao menos um layout."))
            return
        if QMessageBox.question(None, tr("Excluir layout"), tr("Excluir o layout '{}'?").format(name)) == QMessageBox.Yes:
            self.m.delete_layout(name)

    def _reset_defaults(self) -> None:
        ok = QMessageBox.question(
            None, tr("Restaurar layouts padrão"),
            tr("Isto recria Corrida, Treino, Telemetria e Broadcast com as posições originais, "
            "descartando suas alterações nesses quatro. Layouts com outros nomes não são afetados."))
        if ok == QMessageBox.Yes:
            self.m.reset_default_layouts()

    def _download_logos(self) -> None:
        ok = QMessageBox.question(
            None, tr("Baixar logos de carros"),
            tr("Isto baixa os logotipos das marcas (PNGs públicos do repositório GitHub 'car-logos-dataset') "
            "para a pasta de logos do KerbHUD. Os logotipos pertencem aos fabricantes e servem só para "
            "identificar os carros no seu overlay. Continuar?"))
        if ok != QMessageBox.Yes:
            return
        self._logo_result = None

        def work() -> None:
            self._logo_result = fetch_logos(logos_dir(), overwrite=False)  # nunca sobrescreve logos que você colocou

        threading.Thread(target=work, name="kerbhud-logos", daemon=True).start()
        self.tray.showMessage(tr("KerbHUD"), tr("Baixando logos de carros..."), QSystemTrayIcon.Information, 3000)
        self._poll_logo_download()

    def _set_logo_wordmark(self, on: bool) -> None:
        if self.m.ctx.logos is not None:
            self.m.ctx.logos.wordmark = bool(on)
        self.m.ctx.save_setting("logo_wordmark", bool(on))
        self.m.reload_logos()

    def _show_missing_logos(self) -> None:
        """Diz exatamente quais logos faltam e com que nome copiar o arquivo."""
        from ..core.logos import logos_status
        seen = dict(self.m.ctx.logos.missing_seen) if self.m.ctx.logos is not None else {}
        status = logos_status(logos_dir())
        absent = [s for s in status if s.path is None]
        parts = []
        if seen:
            parts.append(tr("Marcas dos carros desta sessão que estão SEM logo (arquivo a criar):") + "\n"
                         + "\n".join(f"   •  {b.display_name}   →   {b.key}.png" for b in seen.values()))
        else:
            parts.append(tr("Nenhuma marca dos carros desta sessão está sem logo."))
        if absent:
            parts.append(tr("No catálogo inteiro faltam {} de {} logos:").format(len(absent), len(status)) + "\n   "
                         + ", ".join(f"{s.name} ({s.key}.png)" for s in absent))
        unk = list(self.m.ctx.logos.unrecognized_seen) if self.m.ctx.logos is not None else []
        if unk:
            lines = []
            for t, r, cls in unk[:12]:
                name = (r or t or "?").split(":", 1)[0]  # "DKR Engineering #4:ELMS25..." -> "DKR Engineering #4"
                name = re.sub(r"\s*#\d+\s*$", "", name)
                lines.append(f'   •  {{"match": "{name}", "class": "{cls}", "brand": "???"}}')
            parts.append(tr("Carros desta sessão cuja MARCA não foi reconhecida (no LMU o nome do carro não cita a "
                             "fabricante). Para cada um, copie a linha para o arquivo brand_overrides.json (bandeja → "
                             "Abrir pasta de configuração), troque ??? pela marca (ex.: adess, mclaren, lamborghini) e use "
                             "\"Recarregar logos\":") + "\n" + "\n".join(lines))
        parts.append(tr("Para adicionar: copie a imagem (png, webp, jpg ou svg) para a pasta de logos com o nome indicado "
                        "(ex.: adess.png) e use \"Recarregar logos\". Logos que você colocar NUNCA são sobrescritos pelo download."))
        QMessageBox.information(None, tr("Logos que faltam"), "\n\n".join(parts))

    def _poll_logo_download(self) -> None:
        res = getattr(self, "_logo_result", None)
        if res is None:
            QTimer.singleShot(500, self._poll_logo_download)
            return
        self.m.reload_logos()
        self.tray.showMessage(tr("KerbHUD: logos"), res.summary, QSystemTrayIcon.Information, 8000)

    def _download_flags(self) -> None:
        ok = QMessageBox.question(
            None, tr("Baixar bandeiras dos países"),
            tr("Isto baixa as bandeiras (PNGs públicos do FlagCDN, cerca de 250 arquivos pequenos) para a pasta de "
            "bandeiras do KerbHUD. No iRacing as bandeiras aparecem sozinhas; no Le Mans Ultimate o jogo não "
            "informa o país, então elas dependem do que você escrever em settings.json (my_country e "
            "driver_flags). Continuar?"))
        if ok != QMessageBox.Yes:
            return
        self._flag_result = None

        def work() -> None:
            self._flag_result = fetch_flags(flags_dir(), overwrite=False)

        threading.Thread(target=work, name="kerbhud-flags", daemon=True).start()
        self.tray.showMessage(tr("KerbHUD"), tr("Baixando bandeiras..."), QSystemTrayIcon.Information, 3000)
        self._poll_flag_download()

    def _poll_flag_download(self) -> None:
        res = getattr(self, "_flag_result", None)
        if res is None:
            QTimer.singleShot(500, self._poll_flag_download)
            return
        self.m.reload_flags()
        self.tray.showMessage(tr("KerbHUD: bandeiras"), res.summary, QSystemTrayIcon.Information, 8000)

    @staticmethod
    def _open_badges() -> None:
        if winapi.IS_WIN:
            import os
            os.startfile(str(badges_dir()))  # noqa: S606

    @staticmethod
    def _open_flags() -> None:
        if winapi.IS_WIN:
            import os
            os.startfile(str(flags_dir()))  # noqa: S606

    @staticmethod
    def _open_logos() -> None:
        if winapi.IS_WIN:
            import os
            os.startfile(str(logos_dir()))  # noqa: S606

    @staticmethod
    def _open_data() -> None:
        if winapi.IS_WIN:
            import os
            os.startfile(str(data_dir()))  # noqa: S606

    @staticmethod
    def _open_log() -> None:
        if winapi.IS_WIN:
            import os
            from ..core.log import log_path
            target = log_path()
            os.startfile(str(target if target.exists() else target.parent))  # noqa: S606

    @staticmethod
    def _open_config() -> None:
        if winapi.IS_WIN:
            import os
            os.startfile(str(config_dir()))  # noqa: S606


def run(sim: str = "auto", edit: bool = False, demo_scenario: str | None = None) -> int:
    winapi.set_app_user_model_id("KerbHUD.App")  # a barra de tarefas usa o nosso ícone, não o do Python
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())  # todas as janelas e diálogos herdam
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("KerbHUD")

    setup_logging()  # erros vão para kerbhud.log (Ajuda → Abrir arquivo de log), em vez de sumirem
    install_excepthooks()
    get_logger().info("KerbHUD %s iniciado", __version__)
    migrate_legacy_config()  # settings.json do nome antigo (SimOverlay), se houver
    migrate_legacy_assets()  # logos/bandeiras/ícones que estavam em %APPDATA% passam a existir na pasta raiz
    settings_path: Path = config_dir() / "settings.json"
    if not settings_path.exists():
        from ..core.engine import DEFAULT_SETTINGS
        write_settings_file(settings_path, DEFAULT_SETTINGS)
    settings = load_settings(settings_path)
    from PySide6.QtCore import QLocale
    set_language(resolve_language(settings.get("language"), QLocale.system().name()))  # antes de criar qualquer janela/menu
    if sim != "auto":
        settings["simulator"] = sim
    if demo_scenario:
        settings["demo_scenario"] = demo_scenario

    engine = Engine(settings)
    history = TelemetryHistory()
    engine.subscribe(history.on_snapshot)
    engine.start()
    store = LayoutStore(layouts_dir())
    store.ensure_defaults()
    ctx = ModuleContext(settings=settings, history=history, logos_dir=logos_dir(), tracks_dir=tracks_dir(),
                        logos=icons.LogoCache(logos_dir(), wordmark=bool(settings.get("logo_wordmark", True))),
                        flags=icons.FlagCache(flags_dir()),
                        badges=icons.BadgeCache(badges_dir()),
                        flag_resolver=FlagResolver(settings),
                        save_setting=lambda k, v: update_settings_file(settings_path, k, v))
    manager = OverlayManager(engine, store, settings, ctx)
    manager.reload_logos()  # lê brand_overrides.json (cria o modelo na 1ª vez)
    manager.load_active()

    manager.external_menu_open = lambda: tray.menu.isVisible()  # menu da bandeja aberto: overlay sai do topo
    registry = winapi.HotkeyRegistry()
    registry.register_all(settings.get("hotkeys", {}))

    def on_hotkey(action: str) -> None:
        if action == "toggle_edit":
            manager.toggle_edit_mode()
        elif action == "toggle_overlay":
            manager.toggle_overlay()
        elif action == "next_layout":
            manager.next_layout(1)
        elif action == "prev_layout":
            manager.next_layout(-1)
        elif action == "demo_next_stage":
            engine.demo_next_stage()
        elif action.startswith("layout_"):
            manager.switch_layout_by_index(int(action.split("_")[1]) - 1)

    def apply_settings(clean: dict) -> list[str]:
        """Valida já foi feito: aplica ao vivo, grava no settings.json e devolve avisos (atalhos que falharam)."""
        changed = apply_patch(settings, clean)
        for key in changed:
            update_settings_file(settings_path, key, settings[key])
        engine.apply_settings(changed)
        if "units" in changed:
            manager.set_units(settings["units"])
        if "ui_hz" in changed:
            manager.set_ui_hz(settings["ui_hz"])
        if "my_country" in changed:
            ctx.flag_resolver.reload(settings)
            manager.reload_flags()
        if "logo_wordmark" in changed:
            if ctx.logos is not None:
                ctx.logos.wordmark = bool(settings["logo_wordmark"])
            manager.reload_logos()
        if "language" in changed:
            warnings_lang = [tr("O idioma muda ao reiniciar o KerbHUD.")]
        else:
            warnings_lang = []
        if "visibility" in changed:
            manager.set_global_visibility(settings["visibility"])
        warnings: list[str] = []
        if "hotkeys" in changed:
            registry.errors.clear()
            registry.register_all(settings.get("hotkeys", {}))
            warnings = list(registry.errors)
        return warnings + warnings_lang

    hk_filter = _HotkeyFilter(registry, on_hotkey)
    app.installNativeEventFilter(hk_filter)

    tray = Tray(app, manager, engine, registry.errors, apply_settings)
    tray.notify_hotkey_errors()
    if not installed_logos(logos_dir()):
        tray.tray.showMessage(tr("KerbHUD"), tr("Logos de carros ainda não instalados. Use o menu da bandeja: Baixar logos de carros."), QSystemTrayIcon.Information, 10000)
    if edit:
        manager.set_edit_mode(True)

    window = MainWindow(tray, manager, engine, settings, ctx.save_setting, app.quit)
    tray.window = window
    window.setWindowIcon(app_icon())
    tray.updates = UpdateController(tray, settings, window.quit, ctx.save_setting)
    window.set_updates(tray.updates)
    if settings.get("check_updates_on_start", True):
        QTimer.singleShot(8000, lambda: tray.updates.check(manual=False))  # avisa na bandeja; não instala sozinho
    window.restore_position()
    if settings.get("show_window_at_startup", True):
        window.show()

    # Guia + novidades: o guia abre na 1ª vez (guide_seen) e as novidades depois de cada atualização
    from ..core.changelog import entries_to_show, load_changelog
    entries = load_changelog(language=get_language())
    news = entries_to_show(entries, settings.get("last_seen_version"), __version__)
    first = not settings.get("guide_seen")
    new_version = settings.get("last_seen_version") != __version__
    if first or (news and new_version):
        title = tr("Bem-vindo ao KerbHUD") if first else tr("KerbHUD atualizado para a {}").format(__version__)
        for key, value in (("guide_seen", True), ("last_seen_version", __version__)):
            ctx.save_setting(key, value)
            settings[key] = value
        if settings.get("show_window_at_startup", True):
            QTimer.singleShot(700, lambda: window.show_welcome("guide" if first else "news", news or entries[:1], title, first))
        else:
            tray.tray.showMessage("KerbHUD", tr("{}. Veja: janela principal → Ajuda → Novidades.").format(title),
                                  QSystemTrayIcon.Information, 8000)
    elif new_version:
        ctx.save_setting("last_seen_version", __version__)

    code = app.exec()
    registry.unregister_all()
    manager.shutdown()
    engine.stop()
    return code
