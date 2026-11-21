"""Opções de cada módulo, descritas como dados (sem Qt): a janela "Config" do módulo é montada a partir daqui.

Cada opção lê o valor atual com os mesmos `get_*` que o módulo usa; assim a janela e o desenho nunca discordam.
`apply`: "option" -> OverlayManager.set_option(mid, key, valor); "column"/"channel" -> um liga/desliga por item.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from .fuel import RESERVE_CHOICES, get_reserve
from .radar import RANGE_CHOICES, get_range
from .relative import AHEAD_CHOICES, FIGHT_CHOICES, get_relative_options
from .standings import COLUMN_KEYS, AROUND_ROW_RANGE, COLUMN_LABELS, OTHER_RANGE, SIZE_CHOICES, TOP_ROW_RANGE, get_standings_options
from .tireview import PRESSURE_UNITS, get_pressure_unit
from .viewmodel import (CHANNEL_LABELS, CHANNELS, HISTORY_CHOICES, TRACE_CHOICES, get_channels, get_history_s,
                        get_trace_s)


@dataclass(frozen=True)
class Opt:
    key: str
    label: str
    kind: str  # "bool" | "choice" | "multi" | "int" (número digitado; choices = (mínimo, máximo)) | "font"
    get: Callable[[dict], Any]  # (options do módulo) -> valor atual (bool / valor da escolha / conjunto de itens ligados)
    choices: tuple = ()  # kind="choice": ((valor, rótulo), ...)  |  kind="multi": ((item, rótulo), ...)
    apply: str = "option"  # "option" | "column" | "channel"
    cast: Optional[Callable[[Any], Any]] = None


def _near(value, choices):
    """Valor da lista de escolhas mais próximo de `value` (os get_* podem devolver 29.99 em vez de 30)."""
    try:
        return min((c for c, _l in choices), key=lambda c: abs(float(c) - float(value)))
    except (TypeError, ValueError):
        return choices[0][0]


def _bool(key, label, default):
    return Opt(key, label, "bool", lambda o, k=key, d=default: (o.get(k, d) is not False) if d else (o.get(k) is True))


_COUNT = tuple((n, str(n)) for n in AHEAD_CHOICES)

SPECS: dict[str, tuple[Opt, ...]] = {
    "standings": (
        Opt("scope", "Mostrar", "choice", lambda o: get_standings_options(o).scope,
            (("all", "Todas as classes"), ("class", "Só a minha classe"))),
        Opt("top_rows", "Linhas do topo (minha classe)", "int", lambda o: get_standings_options(o).top_rows,
            TOP_ROW_RANGE, cast=int),
        Opt("around_rows", "Linhas em volta de mim", "int", lambda o: get_standings_options(o).around_rows,
            AROUND_ROW_RANGE, cast=int),
        Opt("other_top", "Outras classes: carros do topo (0 e 0 = não mostrar)", "int",
            lambda o: get_standings_options(o).other_top, OTHER_RANGE, cast=int),
        Opt("other_around", "Outras classes: carros perto de mim", "int", lambda o: get_standings_options(o).other_around,
            OTHER_RANGE, cast=int),
        Opt("header_size", "Tamanho do cabeçalho (barra do topo)", "choice", lambda o: get_standings_options(o).header_size,
            tuple((s, s) for s in SIZE_CHOICES)),
        Opt("driver_size", "Tamanho dos pilotos (linhas)", "choice", lambda o: get_standings_options(o).driver_size,
            tuple((s, s) for s in SIZE_CHOICES)),
        Opt("font", "Fonte", "font", lambda o: get_standings_options(o).font),
        Opt("animations", "Animações de ultrapassagem", "bool", lambda o: get_standings_options(o).animations),
        Opt("hide_until_timed", "Treino/Qualy: esconder até alguém fazer um tempo", "bool",
            lambda o: get_standings_options(o).hide_until_timed),
        Opt("show_profile", "Meu perfil no rodapé", "bool", lambda o: get_standings_options(o).show_profile),
        Opt("columns", "Colunas", "multi", lambda o: set(get_standings_options(o).columns),
            tuple((k, COLUMN_LABELS[k]) for k in COLUMN_KEYS), apply="column"),
    ),
    "relative": (
        Opt("ahead", "Carros à frente", "choice", lambda o: get_relative_options(o).ahead, _COUNT, cast=int),
        Opt("behind", "Carros atrás", "choice", lambda o: get_relative_options(o).behind, _COUNT, cast=int),
        Opt("fight_s", "Disputa direta até", "choice", lambda o: _near(get_relative_options(o).fight_s, [(f, "") for f in FIGHT_CHOICES]),
            tuple((f, f"{f:.1f} s") for f in FIGHT_CHOICES), cast=float),
        Opt("animations", "Animações de ultrapassagem", "bool", lambda o: get_relative_options(o).animations),
        Opt("show_irating", "Mostrar iRating", "bool", lambda o: get_relative_options(o).show_irating),
    ),
    "telemetry": (
        Opt("channels", "Canais", "multi", lambda o: {c for c, on in get_channels(o).items() if on},
            tuple((c, CHANNEL_LABELS[c]) for c in CHANNELS), apply="channel"),
        Opt("history_s", "Histórico", "choice", lambda o: _near(get_history_s(o), [(h, "") for h in HISTORY_CHOICES]),
            tuple((h, f"{h} s") for h in HISTORY_CHOICES), cast=float),
    ),
    "inputs": (
        _bool("show_clutch", "Mostrar embreagem", True),
        _bool("trace_steering", "Mostrar direção no gráfico", False),
        Opt("trace_s", "Gráfico", "choice", lambda o: _near(get_trace_s(o), [(t, "") for t in TRACE_CHOICES]),
            tuple((t, f"{t} s") for t in TRACE_CHOICES), cast=float),
    ),
    "fuel": (
        Opt("reserve_laps", "Reserva", "choice", lambda o: _near(get_reserve(o), [(r, "") for r in RESERVE_CHOICES]),
            tuple((r, f"{r:g} volta(s)") for r in RESERVE_CHOICES), cast=float),
    ),
    "radar": (
        Opt("range_m", "Alcance", "choice", lambda o: _near(get_range(o), [(r, "") for r in RANGE_CHOICES]),
            tuple((r, f"{r:g} m") for r in RANGE_CHOICES), cast=float),
        _bool("auto_hide", "Só aparecer quando há carro perto", True),
    ),
    "tires": (
        Opt("pressure_unit", "Pressão em", "choice", lambda o: get_pressure_unit(o),
            tuple((u, "PSI" if u == "psi" else "kPa") for u in PRESSURE_UNITS)),
    ),
    "trackmap": (
        _bool("mirror", "Espelhar o traçado", False),
        Opt("label", "Texto nos carros", "choice", lambda o: o.get("label", "class_pos"),
            (("class_pos", "Posição na classe"), ("number", "Número do carro"), ("none", "Sem texto"))),
    ),
}


def specs_for(mid: str) -> tuple[Opt, ...]:
    return SPECS.get(mid, ())


def has_options(mid: str) -> bool:
    return bool(SPECS.get(mid))
