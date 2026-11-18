"""Lógica do módulo RELATIVE (sem Qt, testável).

Calcula, a cada snapshot, os carros mais próximos à frente e atrás NA PISTA (não na
classificação), com:

* distância em metros (se o tamanho da pista for conhecido) e tempo estimado;
* tendência (aproximando / afastando) medida ao longo do tempo;
* cor do estado (favorável, atenção, alerta, neutro) e destaque de disputa direta.

Como o tempo é estimado (não é publicado pelo simulador para cada par de carros):
  - carro à frente: tempo = fração da volta que nos separa × meu tempo de volta;
  - carro atrás:    tempo = fração da volta × tempo de volta DELE (quanto ele leva
    para chegar em mim). Sem tempo de volta conhecido, mostramos só a distância.
O tempo de volta de referência é a estimativa do simulador, senão a melhor volta,
senão a última volta; nunca um valor inventado.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from .model import CarState, CarStatus, Snapshot
from .sessioninfo import SessionBar, build_session_bar
from .standings import ir_deltas
from .textfmt import is_race

AHEAD_CHOICES = (1, 2, 3, 4, 5)
FIGHT_CHOICES = (0.5, 1.0, 1.5)
DEFAULT_AHEAD, DEFAULT_BEHIND, DEFAULT_FIGHT_S = 3, 3, 1.0
FIGHT_DISTANCE_M = 25.0  # usado quando não há tempo de volta para estimar segundos
ALERT_S = 8.0  # alerta de tráfego multiclasse dentro desta janela
TREND_EPS_S = 0.03  # s/s: abaixo disso consideramos "estável"
TREND_EPS_M = 1.0  # m/s (quando só há distância)
TREND_WINDOW_S = 2.0
LAP_DIFF_CONFIRM = 3  # atualizações seguidas até aceitar mudança de volta (evita piscar na linha)

STATE_FAVORABLE, STATE_DANGER, STATE_ALERT, STATE_NEUTRAL = "favorable", "danger", "alert", "neutral"
EXCLUDED = (CarStatus.OUT, CarStatus.GARAGE, CarStatus.DISQUALIFIED)


@dataclass(frozen=True)
class RelativeOptions:
    ahead: int = DEFAULT_AHEAD
    behind: int = DEFAULT_BEHIND
    fight_s: float = DEFAULT_FIGHT_S
    show_irating: bool = True
    animations: bool = True  # linhas deslizam e piscam em ultrapassagens


def get_relative_options(options: dict) -> RelativeOptions:
    o = options if isinstance(options, dict) else {}

    def _int(key: str, default: int) -> int:
        try:
            return min(max(int(o.get(key, default)), 0), 6)
        except (TypeError, ValueError):
            return default

    try:
        fight = float(o.get("fight_s", DEFAULT_FIGHT_S))
        fight = min(max(fight, 0.1), 5.0) if fight == fight else DEFAULT_FIGHT_S
    except (TypeError, ValueError):
        fight = DEFAULT_FIGHT_S
    return RelativeOptions(_int("ahead", DEFAULT_AHEAD), _int("behind", DEFAULT_BEHIND), fight,
                           o.get("show_irating", True) is not False, o.get("animations", True) is not False)


# ---- geometria do módulo ------------------------------------------------- #
HEADER_H, ROW_H, FOOTER_H, DESIGN_W = 36.0, 30.0, 34.0, 650.0
NAME_FONT_PX = 18.0  # tamanho do nome do piloto (referência de legibilidade)


def relative_design_size(options: dict) -> tuple[float, float]:
    o = get_relative_options(options)
    return DESIGN_W, HEADER_H + (o.ahead + 1 + o.behind) * ROW_H + FOOTER_H


# ---- modelo -------------------------------------------------------------- #
@dataclass
class RelativeEntry:
    car: CarState
    side: str  # "ahead" | "behind"
    delta_pct: float  # fração da volta na pista (positivo = à frente)
    distance_m: Optional[float]
    gap_s: Optional[float]  # sempre positivo (módulo); o sinal vem de `side`
    lap_diff: int  # voltas à frente (+) ou atrás (-) de mim na corrida
    trend: Optional[str]  # "closing" | "receding" | "steady" | None
    state: str  # favorable | danger | alert | neutral
    fight: bool
    same_class: bool
    faster_class: bool
    in_pit: bool
    present: bool = True  # False: carro fora da pista/da sessão, mostrado apagado e sem tempo (dado antigo)

    @property
    def box(self) -> str:
        """Cor da caixa de gap: voltas de diferença têm prioridade (vermelho = uma volta à frente,
        azul = uma volta atrás), como nos relatives do iRacing; senão vale o estado da disputa."""
        if self.lap_diff > 0:
            return "lap_ahead"
        if self.lap_diff < 0:
            return "lap_behind"
        return self.state

    @property
    def gap_text(self) -> str:
        if not self.present:
            return "—"  # o último valor conhecido não vale mais: não mostramos número velho
        sign = "-" if self.side == "ahead" else "+"
        if self.gap_s is not None:
            return f"{sign}{self.gap_s:.1f}" if self.gap_s >= 10 else f"{sign}{self.gap_s:.2f}"
        if self.distance_m is not None:
            return f"{sign}{abs(self.distance_m):.0f} m"
        return "—"


@dataclass
class RelativeView:
    me: Optional[CarState] = None
    ahead: list[RelativeEntry] = field(default_factory=list)  # do mais distante ao mais próximo
    behind: list[RelativeEntry] = field(default_factory=list)  # do mais próximo ao mais distante
    uses_time: bool = False
    message: str = ""  # explica por que o painel está vazio
    bar: SessionBar = field(default_factory=SessionBar)  # SOF/incidentes (topo) e sessão/voltas (rodapé)
    ir_deltas: dict[int, int] = field(default_factory=dict)  # iRating projetado por carro (corrida)


def wrap_delta(delta: float) -> float:
    """Diferença de fração de volta no intervalo [-0.5, 0.5)."""
    return ((delta + 0.5) % 1.0) - 0.5


def class_pace(cars: list[CarState]) -> dict[Optional[str], float]:
    """Melhor volta real de cada classe, para saber qual é a mais rápida."""
    pace: dict[Optional[str], float] = {}
    for c in cars:
        if c.best_lap:
            pace[c.class_name] = min(c.best_lap, pace.get(c.class_name, c.best_lap))
    return pace


def _ref_lap(car: CarState) -> Optional[float]:
    return car.est_lap_time or car.best_lap or car.last_lap


class RelativeTracker:
    """Mantém o histórico necessário para tendência e para estabilizar a diferença de voltas."""

    def __init__(self) -> None:
        self._hist: dict[int, deque] = {}
        self._side: dict[int, str] = {}
        self._lap: dict[int, tuple[int, int, int]] = {}  # idx -> (valor estável, candidato, contagem)

    def reset(self) -> None:
        self._hist.clear()
        self._side.clear()
        self._lap.clear()

    # ---- API ------------------------------------------------------------ #
    def update(self, snap: Snapshot, opts: RelativeOptions, now: Optional[float] = None) -> RelativeView:
        view = RelativeView()
        me = snap.player()
        if not snap.connected or me is None:
            view.message = "Aguardando dados"
            return view
        view.me = me
        view.bar = build_session_bar(snap)
        if is_race(snap.session.session_type):
            view.ir_deltas = ir_deltas(snap.cars)
        if me.lap_dist_pct is None:
            view.message = "Sem posição na pista"
            return view
        t = snap.timestamp if now is None else now
        length = snap.session.track_length_m
        pace = class_pace(snap.cars)
        my_pace = pace.get(me.class_name)
        my_ref = _ref_lap(me)

        on_track: list[tuple[float, CarState]] = []
        off_track: list[tuple[float, CarState]] = []  # garagem, abandono, saiu da sessão
        for c in snap.cars:
            if c.idx == me.idx or c.lap_dist_pct is None:
                continue
            d = wrap_delta(c.lap_dist_pct - me.lap_dist_pct)
            (off_track if (c.status in EXCLUDED or not c.in_session) else on_track).append((d, c))
        ahead = sorted((x for x in on_track if x[0] >= 0), key=lambda x: x[0])[: opts.ahead]
        behind = sorted((x for x in on_track if x[0] < 0), key=lambda x: -x[0])[: opts.behind]
        # Quem está na pista tem prioridade. Os espaços que sobrariam em branco são preenchidos com os carros
        # que não estão na pista, apagados (a lista não fica vazia, por exemplo quando todos saem da sessão).
        fill_a = sorted((x for x in off_track if x[0] >= 0), key=lambda x: x[0])[: opts.ahead - len(ahead)]
        fill_b = sorted((x for x in off_track if x[0] < 0), key=lambda x: -x[0])[: opts.behind - len(behind)]

        shown: set[int] = set()
        entries_a = [self._entry(c, d, "ahead", me, length, my_ref, my_pace, pace, opts, t) for d, c in ahead]
        entries_b = [self._entry(c, d, "behind", me, length, my_ref, my_pace, pace, opts, t) for d, c in behind]
        for e in entries_a + entries_b:
            shown.add(e.car.idx)
        entries_a = sorted(entries_a + [self._absent(c, d, "ahead", me) for d, c in fill_a], key=lambda e: e.delta_pct)
        entries_b = sorted(entries_b + [self._absent(c, d, "behind", me) for d, c in fill_b],
                           key=lambda e: -e.delta_pct)
        # esquece o histórico de carros que saíram da janela
        for idx in list(self._hist):
            if idx not in shown:
                self._hist.pop(idx, None)
                self._side.pop(idx, None)
        view.ahead = list(reversed(entries_a))
        view.behind = entries_b
        view.uses_time = any(e.gap_s is not None for e in entries_a + entries_b)
        if not entries_a and not entries_b:
            view.message = "Sem outros carros na pista"
        return view

    # ---- internos ------------------------------------------------------- #
    @staticmethod
    def _absent(c: CarState, d: float, side: str, me: CarState) -> RelativeEntry:
        """Carro fora da pista ou da sessão: sem tempo, sem tendência, sem disputa; só presença apagada."""
        return RelativeEntry(c, side, d, None, None, 0, None, STATE_NEUTRAL, False, c.class_name == me.class_name,
                             False, False, present=False)

    def _stable_lap_diff(self, idx: int, raw: int) -> int:
        stable, cand, count = self._lap.get(idx, (raw, raw, LAP_DIFF_CONFIRM))
        if raw == stable:
            self._lap[idx] = (stable, raw, 0)
            return stable
        count = count + 1 if raw == cand else 1
        if count >= LAP_DIFF_CONFIRM:
            self._lap[idx] = (raw, raw, 0)
            return raw
        self._lap[idx] = (stable, raw, count)
        return stable

    def _trend(self, idx: int, side: str, magnitude: float, t: float, eps: float) -> Optional[str]:
        if self._side.get(idx) != side:  # ultrapassagem: o histórico antigo deixa de valer
            self._hist.pop(idx, None)
            self._side[idx] = side
        h = self._hist.setdefault(idx, deque())
        h.append((t, magnitude))
        while h and t - h[0][0] > TREND_WINDOW_S + 0.5:
            h.popleft()
        old = next((s for s in h if t - s[0] >= 0.6), None)  # amostra mais antiga com idade suficiente
        if old is None or t - old[0] <= 0:
            return None
        rate = (old[1] - magnitude) / (t - old[0])  # positivo = diminuindo (aproximando)
        if rate > eps:
            return "closing"
        if rate < -eps:
            return "receding"
        return "steady"

    def _entry(self, c: CarState, d: float, side: str, me: CarState, length: Optional[float],
               my_ref: Optional[float], my_pace: Optional[float], pace: dict, opts: RelativeOptions,
               t: float) -> RelativeEntry:
        mag = abs(d)
        distance = d * length if length else None
        if side == "ahead":
            ref = my_ref or _ref_lap(c)
        else:
            ref = _ref_lap(c) or my_ref
        gap_s = mag * ref if ref else None

        total_c = (c.laps_completed or 0) + (c.lap_dist_pct or 0.0)
        total_me = (me.laps_completed or 0) + (me.lap_dist_pct or 0.0)
        raw = round(total_c - total_me - d) if (c.laps_completed is not None and me.laps_completed is not None) else 0
        lap_diff = self._stable_lap_diff(c.idx, int(raw))

        if gap_s is not None:
            trend = self._trend(c.idx, side, gap_s, t, TREND_EPS_S)
        else:
            trend = self._trend(c.idx, side, abs(distance) if distance is not None else mag, t,
                                TREND_EPS_M if distance is not None else TREND_EPS_M / 1000.0)

        same_class = c.class_name == me.class_name
        c_pace = pace.get(c.class_name)
        faster = bool(not same_class and c_pace and my_pace and c_pace < my_pace)
        slower = bool(not same_class and c_pace and my_pace and c_pace > my_pace)
        in_pit = c.status == CarStatus.PITS

        limit_ok = (gap_s is not None and gap_s <= opts.fight_s) or (gap_s is None and distance is not None
                                                                     and abs(distance) <= FIGHT_DISTANCE_M)
        fight = bool(same_class and lap_diff == 0 and limit_ok and not in_pit and me.status != CarStatus.PITS)

        state = STATE_NEUTRAL
        if side == "ahead":
            if trend == "closing":
                state = STATE_FAVORABLE
            if slower and trend == "closing" and gap_s is not None and gap_s <= ALERT_S:
                state = STATE_ALERT  # chegando em tráfego mais lento
        else:
            threat = lap_diff >= 0
            if threat and trend == "closing":
                state = STATE_DANGER
            elif trend == "receding":
                state = STATE_FAVORABLE
            if faster and gap_s is not None and gap_s <= ALERT_S and trend in ("closing", "steady"):
                state = STATE_ALERT  # carro de classe mais rápida vindo por trás
        return RelativeEntry(c, side, d, distance, gap_s, lap_diff, trend, state, fight, same_class,
                             faster, in_pit)
