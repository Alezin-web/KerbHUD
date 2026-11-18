"""Módulos da Etapa 2.

* `StatusModule`, `InputsModule`, `TelemetryModule`, `StandingsModule` e
  `RelativeModule`: módulos reais.
* `PlaceholderModule`: moldura provisória do Track Map (Etapa 5). Mostra alguns
  dados reais só para provar que o fluxo de dados até a janela funciona.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter

from .. import __version__
from ..core.layout import MODULES, ModuleSpec
from ..core.model import Sim, Snapshot
from . import theme
from .context import ModuleContext
from .inputs_module import InputsModule
from .module_base import ModuleWindow, fit_font, make_font
from .relative_module import RelativeModule
from .standings_module import StandingsModule
from .damage_module import DamageModule
from .digflag_module import DigFlagModule
from .fuel_module import FuelModule
from .radar_module import RadarModule
from .spotter_module import SpotterModule
from .tires_module import TiresModule
from .telemetry_module import TelemetryModule
from .trackmap_module import TrackMapModule

_STAGE: dict = {}


def _draw_demo_badge(p: QPainter, right: float, y: float) -> None:
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(theme.YELLOW))
    p.drawRoundedRect(QRectF(right - 54, y, 50, 18), 3, 3)
    p.setPen(QColor("#111111"))
    p.setFont(make_font(12, True))
    p.drawText(QRectF(right - 54, y, 50, 18), Qt.AlignCenter, "DEMO")


class StatusModule(ModuleWindow):
    """Conexão com o simulador, selo DEMO e a VERSÃO do app (numa captura de tela dá para saber qual
    código está rodando)."""

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        s: Snapshot | None = self.snapshot
        connected = bool(s and s.connected)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.GREEN if connected else theme.GRAY))
        p.drawEllipse(QPointF(16, h / 2), 5, 5)
        p.setPen(QColor(theme.WHITE))
        name = {Sim.IRACING: "iRACING", Sim.LMU: "LE MANS ULTIMATE", Sim.DEMO: "DEMO",
                Sim.NONE: "SEM SIMULADOR"}[s.sim if s else Sim.NONE]
        avail = w - 30 - 122
        p.setFont(fit_font(p, name, 15, avail, True))
        p.drawText(QRectF(30, 0, avail, h), Qt.AlignVCenter | Qt.AlignLeft, name)
        if s and s.is_demo:
            _draw_demo_badge(p, w - 66, (h - 18) / 2)
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(12, True))
        p.drawText(QRectF(w - 64, 0, 58, h), Qt.AlignVCenter | Qt.AlignRight, f"v{__version__}")


class PlaceholderModule(ModuleWindow):
    def _lines(self, s: Snapshot | None) -> list[str]:
        if s is None or not s.connected:
            return ["Aguardando simulador..."]
        mid = self.module_id
        if mid == "inputs" and s.inputs:
            i = s.inputs
            return [f"{i.speed_kmh:5.0f} km/h   marcha {i.gear:+d}   {i.rpm:5.0f} rpm",
                    f"acel {i.throttle * 100:3.0f}%  freio {i.brake * 100:3.0f}%  emb {i.clutch * 100:3.0f}%"]
        if mid == "standings":
            ordered = sorted((c for c in s.cars if c.position), key=lambda c: c.position)[:6]
            return [f"P{c.position:<2} #{c.car_number or '?':<3} {c.driver_name[:20]}" for c in ordered] or ["sem classificação"]
        if mid == "relative":
            me = s.player()
            return [f"Posição: P{me.position}" if me and me.position else "Posição: --",
                    f"Carros na pista: {len(s.cars)}"]
        if mid == "trackmap":
            return [f"{s.session.track_name or '--'}", f"{len(s.cars)} carros"]
        return [f"Fonte: {s.sim.value}"]

    def paint_content(self, p: QPainter, w: float, h: float) -> None:
        # cabeçalho
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.RED))
        p.drawRect(QRectF(0, 0, 4, 30))
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(16, True))
        p.drawText(QRectF(14, 0, w - 80, 30), Qt.AlignVCenter | Qt.AlignLeft, self.spec.title)
        if self.snapshot and self.snapshot.is_demo:
            _draw_demo_badge(p, w, 6)
        # corpo
        p.setPen(QColor(theme.GRAY))
        p.setFont(make_font(12))
        stage = _STAGE.get(self.module_id, "?")
        p.drawText(QRectF(14, 34, w - 20, 18), Qt.AlignVCenter, f"pré-visualização — módulo completo na Etapa {stage}")
        p.setPen(QColor(theme.WHITE))
        p.setFont(make_font(14))
        y = 62
        for line in self._lines(self.snapshot):
            if y > h - 14:
                break
            p.drawText(QRectF(14, y, w - 20, 20), Qt.AlignVCenter, line)
            y += 22


def create_module(module_id: str, ctx: ModuleContext | None = None) -> ModuleWindow:
    spec: ModuleSpec = MODULES[module_id]
    cls = {"status": StatusModule, "inputs": InputsModule, "telemetry": TelemetryModule,
           "standings": StandingsModule, "relative": RelativeModule, "trackmap": TrackMapModule,
           "fuel": FuelModule, "damage": DamageModule, "tires": TiresModule,
           "spotter": SpotterModule, "radar": RadarModule, "digflag": DigFlagModule}.get(module_id, PlaceholderModule)
    return cls(spec, ctx)
