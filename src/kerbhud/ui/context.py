"""Contexto compartilhado entre o gerenciador e os módulos (sem Qt)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..core.history import TelemetryHistory


@dataclass
class ModuleContext:
    settings: dict = field(default_factory=lambda: {"units": "kmh"})
    history: TelemetryHistory = field(default_factory=TelemetryHistory)
    #: pasta dos logotipos de marcas (`bmw.png`, `porsche.png`...) e cache compartilhado entre módulos
    logos_dir: Optional[Path] = None
    logos: Any = None  # ui.icons.LogoCache (criado pelo app; None = sem logos)
    tracks_dir: Optional[Path] = None  # onde ficam os traçados gravados (um arquivo por pista)
    badges: Any = None  # ui.icons.BadgeCache: ícones de DR/SR do LMU (None = só texto)
    flags: Any = None  # ui.icons.FlagCache (None = sem bandeiras)
    flag_resolver: Any = None  # core.flags.FlagResolver: país de cada piloto (None = só o dado do simulador)
    #: persiste uma chave de settings.json (ex.: "units"); recebe (chave, valor)
    save_setting: Callable[[str, object], None] = lambda key, value: None

    @property
    def units(self) -> str:
        return "mph" if self.settings.get("units") == "mph" else "kmh"
