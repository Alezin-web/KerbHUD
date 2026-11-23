"""Gerencia as janelas dos módulos, o layout ativo e o modo de edição."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QGuiApplication

from ..core import brands, visibility, winapi
from ..core.log import get_logger
from ..core.paths import config_dir
from ..core.engine import Engine
from ..core.layout import (MODULES, Layout, LayoutStore, ScreenInfo, pick_screen, pixels_to_rect,
                           preset_corrida, rect_to_pixels)
from ..core.model import Snapshot
from .context import ModuleContext
from .modules import create_module


def current_screens() -> tuple[list[ScreenInfo], Optional[str]]:
    screens = []
    for s in QGuiApplication.screens():
        g = s.geometry()
        screens.append(ScreenInfo(s.name(), g.x(), g.y(), g.width(), g.height()))
    primary = QGuiApplication.primaryScreen()
    return screens, (primary.name() if primary else None)


class OverlayManager(QObject):
    def __init__(self, engine: Engine, store: LayoutStore, settings: dict,
                 ctx: Optional[ModuleContext] = None):
        super().__init__()
        self.engine = engine
        self.store = store
        self.settings = settings
        self.ctx = ctx or ModuleContext(settings=settings)
        self.windows = {mid: create_module(mid, self.ctx) for mid in MODULES}
        for mid, w in self.windows.items():
            w.geometry_committed.connect(self._on_geometry)
        self.layout: Layout = preset_corrida()
        self.edit_mode = False
        self.overlay_visible = True
        self._last_snap: Optional[Snapshot] = None

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(max(5, int(1000 / max(1, int(settings.get("ui_hz", 30))))))

        self._topmost = QTimer(self)  # reafirma o topo (o jogo pode reorganizar o z-order) sem cobrir a barra de tarefas
        self._topmost.timeout.connect(self._reassert_topmost)
        self._topmost.start(400)
        self._topmost_ticks = 0
        self._shell_lowered = False
        self.external_menu_open = lambda: False  # o app informa se o menu da bandeja está aberto

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._flush_save)

    # ---- layouts -------------------------------------------------------- #
    def load_active(self) -> None:
        names = self.store.list_names()
        name = self.store.get_active()
        if name not in names:
            name = names[0] if names else None
        if name is None:
            self.apply_layout(preset_corrida())
            return
        try:
            self.apply_layout(self.store.load(name))
        except (OSError, ValueError):
            self.apply_layout(preset_corrida())

    def apply_layout(self, layout: Layout) -> None:
        self.layout = layout
        screens, primary = current_screens()
        for mid, w in self.windows.items():
            st = layout.modules[mid]
            x, y, wd, ht = rect_to_pixels(st, MODULES[mid], screens, primary)
            w.setGeometry(x, y, wd, ht)
            w.set_opacity(st.opacity)
            w.options = st.options  # mesmo dict do layout: mudanças são persistidas
            w.set_reference_width(pick_screen(st.screen, screens, primary).w)  # base da escala de texto fixa
            w.set_always_on_top(layout.always_on_top)
        self._sync_visibility()
        self.store.set_active(layout.name)

    def switch_layout(self, name: str) -> None:
        self._flush_save()
        try:
            self.apply_layout(self.store.load(name))
        except (OSError, ValueError):  # arquivo do layout sumiu ou foi corrompido: fica no layout atual
            get_logger().warning("Não foi possível abrir o layout %r", name, exc_info=True)

    def switch_layout_by_index(self, index: int) -> None:
        names = self.store.list_names()
        if 0 <= index < len(names):
            self.switch_layout(names[index])

    def save_as(self, name: str) -> None:
        self._capture_all()
        self.layout.name = name.strip()
        self.store.save(self.layout)
        self.store.set_active(self.layout.name)

    def reset_default_layouts(self) -> None:
        """Restaura os 4 presets e reaplica o layout ativo."""
        active = self.layout.name
        self.store.reset_defaults()
        names = self.store.list_names()
        self.apply_layout(self.store.load(active if active in names else names[0]))

    def next_layout(self, step: int = 1) -> None:
        """Passa para o próximo (step=1) ou o anterior (step=-1) layout da lista, em círculo."""
        names = self.store.list_names()
        if len(names) < 2:
            return
        cur = names.index(self.layout.name) if self.layout.name in names else -1
        self.switch_layout(names[(cur + step) % len(names)])

    def rename_layout(self, old: str, new: str) -> None:
        self._flush_save()
        if old == self.layout.name:
            self._capture_all()
            self.store.save(self.layout)
        lay = self.store.rename(old, new)
        if old == self.layout.name:
            self.layout.name = lay.name

    def duplicate_layout(self, name: str) -> str:
        """Copia um layout para `nome (2)` e devolve o nome novo (não ativa a cópia)."""
        self._flush_save()
        if name == self.layout.name:
            self._capture_all()
            self.store.save(self.layout)
        new = self.store.unique_name(name)
        self.store.duplicate(name, new)
        return new

    def export_layout(self, name: str, path) -> None:
        self._flush_save()
        if name == self.layout.name:
            self._capture_all()
            self.store.save(self.layout)
        self.store.export_layout(name, path)

    def import_layout(self, path) -> str:
        """Importa um arquivo de layout (valida e nunca sobrescreve) e devolve o nome criado."""
        return self.store.import_layout(path).name

    def set_ui_hz(self, hz: int) -> None:
        self.settings["ui_hz"] = int(hz)
        self._tick.start(max(5, int(1000 / max(1, int(hz)))))

    def delete_layout(self, name: str) -> None:
        self.store.delete(name)
        if name == self.layout.name:
            self.load_active()

    # ---- visibilidade / edição ----------------------------------------- #
    def _sync_visibility(self) -> None:
        for mid, w in self.windows.items():
            want = self.overlay_visible and self.layout.modules[mid].visible
            if want and not self.edit_mode:  # em edição tudo aparece, para poder posicionar
                want = visibility.allowed(self.module_show_mode(mid), self._last_snap)
            if want and not w.isVisible():
                w.begin_fade_in()
                w.show()
                w.apply_native_flags()
                w.set_edit_mode(self.edit_mode)
                if self._last_snap:
                    w.update_snapshot(self._last_snap)
            elif want and w.fading_out:
                w.fade_show()  # voltou a valer no meio do fade-out
            elif not want and w.isVisible():
                w.fade_hide()  # some com fade-out; `_on_tick` esconde a janela quando termina

    def module_show_mode(self, mid: str) -> str:
        return visibility.effective_mode(self.settings.get("visibility"),
                                         self.layout.modules[mid].options.get("show_when"))

    def set_global_visibility(self, mode: str) -> None:
        self.settings["visibility"] = visibility.normalize(mode)
        self.ctx.save_setting("visibility", self.settings["visibility"])
        self._sync_visibility()

    def set_module_show_when(self, mid: str, mode: str) -> None:
        self.layout.modules[mid].options["show_when"] = mode
        self._sync_visibility()
        self._schedule_save()

    def set_module_visible(self, mid: str, visible: bool) -> None:
        self.layout.modules[mid].visible = visible
        self._sync_visibility()
        self._schedule_save()

    def toggle_overlay(self) -> None:
        self.overlay_visible = not self.overlay_visible
        self._sync_visibility()

    def set_edit_mode(self, on: bool) -> None:
        self.edit_mode = on
        if on and not self.overlay_visible:
            self.overlay_visible = True
        self._sync_visibility()
        for w in self.windows.values():
            w.set_edit_mode(on)
        if not on:
            self._flush_save()

    def toggle_edit_mode(self) -> None:
        self.set_edit_mode(not self.edit_mode)

    # ---- opções dos módulos --------------------------------------------- #
    def set_option(self, mid: str, key: str, value) -> None:
        self.layout.modules[mid].options[key] = value
        self.windows[mid].update()
        self._schedule_save()

    def set_column(self, mid: str, key: str, on: bool) -> None:
        """Liga/desliga uma coluna (módulo Standings)."""
        opts = self.layout.modules[mid].options
        cols = opts.get("columns")
        if not isinstance(cols, dict):
            cols = opts["columns"] = {}
        cols[key] = bool(on)
        self.windows[mid].update()
        self._schedule_save()

    def set_channel(self, channel: str, on: bool) -> None:
        opts = self.layout.modules["telemetry"].options
        channels = opts.get("channels")
        if not isinstance(channels, dict):
            channels = opts["channels"] = {}
        channels[channel] = bool(on)
        self.windows["telemetry"].update()
        self._schedule_save()

    def set_units(self, units: str) -> None:
        units = "mph" if units == "mph" else "kmh"
        self.settings["units"] = units
        self.ctx.save_setting("units", units)
        for w in self.windows.values():
            w.update()

    # ---- persistência --------------------------------------------------- #
    def _capture(self, mid: str) -> None:
        w = self.windows[mid]
        g = w.geometry()
        screens, _ = current_screens()
        rect, screen = pixels_to_rect((g.x(), g.y(), g.width(), g.height()), screens)
        st = self.layout.modules[mid]
        st.rect, st.screen, st.opacity = rect, screen, w.opacity

    def _capture_all(self) -> None:
        for mid in self.windows:
            self._capture(mid)

    def _on_geometry(self, mid: str) -> None:
        self._capture(mid)
        self._schedule_save()

    def _schedule_save(self) -> None:
        self._save_timer.start()

    def _flush_save(self) -> None:
        self._save_timer.stop()
        try:
            self.store.save(self.layout)
        except OSError:
            pass  # falha de disco não pode derrubar o overlay

    # ---- dados ---------------------------------------------------------- #
    @staticmethod
    def _vis_key(snap: Optional[Snapshot]):
        """O que decide a visibilidade por regra (se isto muda, os módulos precisam ser reavaliados)."""
        if snap is None:
            return None
        return (snap.connected, snap.in_garage, snap.driving, snap.player() is not None, snap.is_demo)

    def _on_tick(self) -> None:
        snap = self.engine.latest()
        if snap is not self._last_snap:
            before = self._vis_key(self._last_snap)
            self._last_snap = snap
            if self._vis_key(snap) != before:
                self._sync_visibility()  # entrou/saiu da pista, da garagem ou dos menus: "só pista"/"só garagem" aparecem/somem
            for w in self.windows.values():
                if w.isVisible():
                    w.update_snapshot(snap)
        # animações de ultrapassagem continuam mesmo sem snapshot novo (jogo pausado, por exemplo)
        for w in self.windows.values():
            if w.isVisible() and (w.is_animating or w.fading):
                w.update()
            if w.fading_out and w.isVisible() and w.faded_out:
                w.hide()  # fade-out terminou

    def zoom_module(self, mid: str, factor: float) -> None:
        """Aumenta/diminui o texto do módulo (a janela acompanha na mesma proporção) e salva no layout."""
        self.windows[mid].zoom(factor)
        self._on_geometry(mid)

    def reload_flags(self) -> None:
        """Relê as bandeiras da pasta (depois de baixá-las) e redesenha os módulos."""
        if self.ctx.flags is not None:
            self.ctx.flags.clear()
        for w in self.windows.values():
            w.update()

    def reload_logos(self) -> None:
        """Relê os logotipos da pasta (depois de baixá-los) e redesenha os módulos."""
        brands.load_overrides_file(config_dir() / "brand_overrides.json")  # regras de marca do usuário
        if self.ctx.logos is not None:
            self.ctx.logos.clear()
        for w in self.windows.values():
            w.update()

    def _reassert_topmost(self) -> None:
        """Mantém o overlay no topo, EXCETO enquanto a pessoa usa a barra de tarefas, a bandeja, um menu ou o Iniciar:
        aí ele sai do topo (fica por baixo deles) e volta sozinho quando o foco retorna ao jogo."""
        busy = winapi.shell_has_focus() or bool(self.external_menu_open())
        if busy:
            if not self._shell_lowered:
                self._shell_lowered = True
                for w in self.windows.values():
                    w.lower_below_shell()
            return
        self._topmost_ticks += 1
        if self._shell_lowered or self._topmost_ticks % 5 == 0:  # volta na hora; no resto, a cada ~2 s
            self._shell_lowered = False
            for w in self.windows.values():
                w.reassert_topmost()

    def set_always_on_top(self, on: bool) -> None:
        self.layout.always_on_top = on
        for w in self.windows.values():
            w.set_always_on_top(on)
        self._schedule_save()

    def shutdown(self) -> None:
        self._flush_save()
        for w in self.windows.values():
            w.hide()
