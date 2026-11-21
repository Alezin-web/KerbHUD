"""Informações da sessão para as barras superior/inferior dos módulos (sem Qt).

Tudo aqui vem de dados reais do simulador ou é calculado deles. O que o simulador não
publica fica vazio e o módulo esconde o item (por exemplo, incidentes no LMU).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .irating import format_ir, sof
from .model import CarState, Snapshot
from .textfmt import format_clock, format_remaining, format_total, is_race


@dataclass
class SessionBar:
    letter: str = "?"  # R, Q, P, W, T
    name: str = ""  # RACE, QUALIFY, PRACTICE...
    time_text: str = ""  # "00:20:07 / 00:45:00"
    incidents_text: str = ""  # "6/25" ou "6"; vazio = indisponível
    lap_text: str = ""  # "12/~25.3", "12/25" ou "12"
    cars_count: int = 0
    sof_text: str = ""  # "2.8k"; vazio = indisponível


def session_letter(session_type: Optional[str]) -> tuple[str, str]:
    t = (session_type or "").lower()
    if "race" in t:
        return "R", "RACE"
    if "qual" in t:
        return "Q", "QUALIFY"
    if "warm" in t:
        return "W", "WARMUP"
    if "test" in t:
        return "T", "TEST"
    if "practice" in t or "prac" in t:
        return "P", "PRACTICE"
    return ("?", (session_type or "").upper())


def class_sof(cars: list[CarState], class_name: Optional[str]) -> Optional[float]:
    ratings = [c.irating for c in cars if c.irating is not None and c.class_name == class_name]
    return sof(ratings) if len(ratings) >= 2 else None


def estimated_total_laps(snap: Snapshot, me: Optional[CarState]) -> Optional[float]:
    """Voltas totais estimadas numa corrida por tempo: feitas + tempo restante / volta de referência."""
    s = snap.session
    if me is None or s.time_remaining_s is None or me.laps_completed is None:
        return None
    ref = me.est_lap_time or me.best_lap or me.last_lap
    if not ref:
        return None
    done = me.laps_completed + (me.lap_dist_pct or 0.0)
    return done + s.time_remaining_s / ref


def build_session_bar(snap: Snapshot) -> SessionBar:
    s = snap.session
    me = snap.player()
    letter, name = session_letter(s.session_type)
    bar = SessionBar(letter=letter, name=name, cars_count=sum(1 for c in snap.cars if c.in_session))

    if s.elapsed_s is not None and s.total_s:
        bar.time_text = f"{format_clock(s.elapsed_s)} / {format_total(s.total_s)}"
    elif s.elapsed_s is not None:
        bar.time_text = format_clock(s.elapsed_s)
    elif s.time_remaining_s is not None:
        bar.time_text = "-" + format_remaining(s.time_remaining_s)

    if s.incidents is not None:
        bar.incidents_text = f"{s.incidents}/{s.incident_limit}" if s.incident_limit else f"{s.incidents}"

    if me is not None and me.laps_completed is not None:
        current = me.laps_completed + 1
        if s.laps_total:
            bar.lap_text = f"{current}/{s.laps_total}"
        elif is_race(s.session_type):
            est = estimated_total_laps(snap, me)
            bar.lap_text = f"{current}/~{max(est, float(current)):.1f}" if est is not None else f"{current}"
        else:
            bar.lap_text = f"{current}"

    if me is not None:
        v = class_sof(snap.cars, me.class_name)
        if v is not None:
            bar.sof_text = format_ir(v)
    return bar
