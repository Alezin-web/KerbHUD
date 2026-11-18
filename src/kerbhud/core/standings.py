"""Lógica do módulo STANDINGS (sem Qt, testável).

Visual de referência: tabela AGRUPADA POR CLASSE (cabeçalho com a quantidade de carros),
posição dentro da classe, Int/Gap relativos à classe, melhor volta da classe em roxo,
ganho/perda de posições desde a largada, pneu, energia (LMU) e licença/iRating.

Decisões baseadas em dados reais (nada inventado; sem dado, a célula fica vazia):

* **Corrida:** Int/Gap vêm do atraso publicado pelo simulador (`gap_leader`) e de voltas de
  atraso, sempre em relação ao carro à frente e ao líder DA CLASSE.
* **Treino/classificação:** os "gaps" publicados não são diferença de tempo útil; o Int/Gap é a
  diferença de MELHOR VOLTA dentro da classe, calculada dos tempos reais.
* O iRating projetado é uma ESTIMATIVA (ver `irating.py`); só aparece em corrida.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Optional, Sequence, TypeVar, Union

from . import badges
from .brands import Brand, brand_for_car
from .flags import FlagResolver
from .classes import class_style, license_color
from .irating import format_ir, projected_changes
from .model import CarState, CarStatus, Sim, Snapshot
from .sessioninfo import SessionBar, build_session_bar
from .textfmt import format_gap, format_laptime, format_remaining, is_race  # noqa: F401 (reexportados)

T = TypeVar("T")

# ---- opções ------------------------------------------------------------- #
COLUMN_KEYS = ("flag", "license", "brand", "delta", "tire", "laps", "int", "gap", "best", "last", "nrg")
COLUMN_LABELS = {"flag": "Bandeira (país)", "license": "Licença / iRating", "brand": "Marca do carro", "delta": "Posições ganhas",
                 "tire": "Pneu", "laps": "Voltas completadas", "int": "Int (para o da frente)", "gap": "Gap (para o líder)",
                 "best": "Melhor volta", "last": "Última volta", "nrg": "Energia (NRG)"}
DEFAULT_COLUMNS = frozenset(COLUMN_KEYS)
ROW_CHOICES = (0, 10, 14, 18, 22, 26)  # 0 = automático (preenche a altura da janela); conta os cabeçalhos
DEFAULT_ROWS = 18
SCOPES = ("all", "class")

# ---- geometria (unidades de projeto) ------------------------------------ #
TOP_H, ROW_H, FOOTER_H, PAD_BOTTOM, PAD = 44.0, 30.0, 34.0, 6.0, 8.0
NAME_W = 244.0  # cabe um nome completo de ~24 letras sem encolher a fonte
NAME_FONT_PX = 18.0  # tamanho do nome do piloto (referência de legibilidade)
NUM_FONT_PX = 23.0  # melhor volta e última volta: negrito e grande (preenche ~80% de uma coluna de 100)
NUM2_FONT_PX = 21.0  # voltas, Int, Gap e NRG: colunas mais estreitas, um pouco menores para não ficarem coladas
# A soma continua <= 1108: layouts salvos têm a janela ajustada à largura anterior; se o desenho ficasse mais
# largo, a última coluna sumiria sozinha nessas janelas. Os números maiores ganharam espaço (Int/Gap) à custa do nome
# (que ainda comporta ~24 letras) e da licença.
WIDTHS = {"pos": 34.0, "num": 62.0, "flag": 36.0, "license": 100.0, "brand": 40.0, "delta": 46.0, "tire": 36.0,
          "laps": 44.0, "int": 76.0, "gap": 76.0, "best": 100.0, "last": 100.0, "nrg": 112.0}
INFO_FONT_PX = 21.0  # barra superior: tempo, incidentes, volta e quantidade de pilotos
INFO_LABEL_PX = 18.0  # "Lap"
INFO_BADGE_R, INFO_HELMET_PX = 12.5, 22.0  # inicial da sessão (R/Q/P) e capacete
TITLE_FONT_PX = 17.0  # títulos das colunas (Tire, Laps, Int, Gap, Fastest, Last, NRG)
TITLE_ROW_Y, TITLE_ROW_H = 24.0, 20.0  # faixa dos títulos: ocupa o fim da barra superior (TOP_H = 44)
NRG_ICON_X = 14.0  # bateria afastada do texto da coluna Last (que termina colado na borda esquerda do NRG)
NRG_TEXT_X = 56.0  # porcentagem logo depois da bateria (34 de largura + polo)
ALIGN = {"pos": "center", "num": "center", "flag": "center", "name": "left", "license": "left", "brand": "center",
         "delta": "center", "tire": "center", "laps": "center", "int": "right", "gap": "right", "best": "right",
         "last": "right", "nrg": "left"}
ORDER = ("pos", "num", "flag", "name", "license", "brand", "delta", "tire", "laps", "int", "gap", "best", "last", "nrg")
ALWAYS = ("pos", "num", "name")
# Colunas que somem PRIMEIRO quando a janela fica estreita (a fonte nunca encolhe): da menos à mais essencial.
DROP_ORDER = ("nrg", "laps", "tire", "delta", "brand", "license", "flag", "last", "best", "int", "gap")
MIN_ROWS = 4
MAX_AUTO_ROWS = 40


@dataclass(frozen=True)
class StandingsOptions:
    scope: str = "all"
    rows: int = DEFAULT_ROWS
    columns: frozenset = DEFAULT_COLUMNS
    show_profile: bool = True
    animations: bool = True  # linhas deslizam e piscam em ultrapassagens


def get_standings_options(options: dict) -> StandingsOptions:
    o = options if isinstance(options, dict) else {}
    scope = o.get("scope") if o.get("scope") in SCOPES else "all"
    try:
        rows = int(o.get("rows", DEFAULT_ROWS))
    except (TypeError, ValueError):
        rows = DEFAULT_ROWS
    rows = 0 if rows <= 0 else min(max(rows, 6), 40)  # 0 = automático
    raw = o.get("columns") if isinstance(o.get("columns"), dict) else {}
    cols = frozenset(k for k in COLUMN_KEYS
                     if (raw[k] if isinstance(raw.get(k), bool) else (k in DEFAULT_COLUMNS)))
    return StandingsOptions(scope, rows, cols, o.get("show_profile", True) is not False,
                            o.get("animations", True) is not False)


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    x: float
    w: float
    align: str


def column_layout(opts: StandingsOptions) -> list[ColumnSpec]:
    """Posição de cada coluna. Ligar colunas alarga o módulo em vez de espremer o nome."""
    x = PAD
    out: list[ColumnSpec] = []
    for key in ORDER:
        if key == "name":
            w = NAME_W
        elif key in ALWAYS or key in opts.columns:
            w = WIDTHS[key]
        else:
            continue
        out.append(ColumnSpec(key, x, w, ALIGN[key]))
        x += w
    return out


def standings_design_size(options: dict) -> tuple[float, float]:
    opts = get_standings_options(options)
    cols = column_layout(opts)
    width = cols[-1].x + cols[-1].w + PAD
    rows = opts.rows or DEFAULT_ROWS  # automático: o tamanho "natural" usa as linhas padrão
    height = TOP_H + rows * ROW_H + (FOOTER_H if opts.show_profile else 0.0) + PAD_BOTTOM
    return width, height


def columns_width(cols: list[ColumnSpec]) -> float:
    return cols[-1].x + cols[-1].w + PAD


def fit_columns(opts: StandingsOptions, avail_w: float) -> list[ColumnSpec]:
    """Colunas que cabem em `avail_w` SEM encolher a fonte: tira as menos importantes (`DROP_ORDER`)."""
    cols = set(opts.columns)
    while True:
        layout = column_layout(replace(opts, columns=frozenset(cols)))
        if columns_width(layout) <= avail_w:
            return layout
        for key in DROP_ORDER:
            if key in cols:
                cols.discard(key)
                break
        else:
            return layout  # só sobraram as obrigatórias


def fit_rows(opts: StandingsOptions, avail_h: float) -> int:
    """Quantas linhas (cabeçalhos de classe incluídos) cabem na altura disponível; `opts.rows` é o teto."""
    footer = FOOTER_H if opts.show_profile else 0.0
    fit = int((avail_h - TOP_H - footer - PAD_BOTTOM) // ROW_H)
    cap = opts.rows if opts.rows > 0 else MAX_AUTO_ROWS
    return max(MIN_ROWS, min(cap, fit))


# ---- modelo ------------------------------------------------------------- #
@dataclass
class StandingsRow:
    car: CarState
    pos_text: str
    class_label: str
    class_color: str
    number_text: str
    name: str
    model: str
    license_class: str  # "" se desconhecido
    license_sr_text: str  # "3.4" ou ""
    irating_text: str  # "1.8k" ou ""
    laps_text: str  # voltas completadas
    ir_delta: Optional[int]  # variação projetada de iRating (corrida)
    brand: Optional[Brand]
    country: Optional[str]  # código ISO da bandeira (ou None)
    pos_change: Optional[int]  # + subiu, - desceu (desde a largada)
    tire: Optional[str]
    int_text: str
    gap_text: str
    best_text: str
    last_text: str
    energy_pct: Optional[float]
    status_tag: str  # "", PIT, OUT, DSQ, FIN, GAR
    is_player: bool
    dim: str  # "none" | "other_class" | "pit" | "out"
    best_flag: str  # "" | "class"  (melhor volta da classe)
    badge: Optional[str] = None  # selo de contato (LMU) do piloto; aparece onde ficaria a bandeira


@dataclass
class HeaderLine:
    label: str
    color: str
    count: int


@dataclass
class Group:
    label: str
    color: str
    rows: list[StandingsRow] = field(default_factory=list)
    total: Optional[int] = None  # pilotos da classe na sessão (em treino/qualy, mais que as linhas com tempo)

    @property
    def count(self) -> int:
        return len(self.rows)

    @property
    def header_count(self) -> int:
        return self.total if self.total is not None else len(self.rows)


Line = Union[StandingsRow, HeaderLine, None]  # None = corte (reticências)


@dataclass
class Chip:
    label: str
    value: str
    color: str
    available: bool = True
    delta: Optional[int] = None  # variação projetada (iRating)
    badge: Optional[str] = None  # chave do selo de contato (LMU): a interface desenha o ÍCONE; sem ícone cai no texto
    rank: Optional[str] = None  # "DR" | "SR": a interface desenha o chip colorido [DR | B2] em vez do texto


@dataclass
class StandingsView:
    groups: list[Group] = field(default_factory=list)
    player: Optional[StandingsRow] = None
    total: int = 0
    mode: str = "race"  # "race" | "best"
    scope: str = "all"
    bar: SessionBar = field(default_factory=SessionBar)
    chips: list[Chip] = field(default_factory=list)
    #: True em treino/qualy enquanto NINGUÉM fez tempo de volta: o módulo não aparece
    hidden: bool = False

    @property
    def rows(self) -> list[StandingsRow]:
        return [r for g in self.groups for r in g.rows]


_TAGS = {CarStatus.PITS: "PIT", CarStatus.OUT: "OUT", CarStatus.DISQUALIFIED: "DSQ",
         CarStatus.FINISHED: "FIN", CarStatus.GARAGE: "GAR"}


def _delta_text(car: CarState, ref: CarState) -> str:
    """Atraso de `car` em relação a `ref` (voltas ou segundos), usando só dados da corrida."""
    laps = max(0, (car.laps_behind_leader or 0) - (ref.laps_behind_leader or 0))
    if laps > 0:
        return format_gap(None, laps)
    if car.gap_leader is None or ref.gap_leader is None:
        return "—"
    return format_gap(car.gap_leader - ref.gap_leader)


def ir_deltas(cars: Sequence[CarState]) -> dict[int, int]:
    """Variação projetada de iRating por carro, calculada classe a classe (como o iRacing)."""
    by_class: dict[Optional[str], list[tuple[int, float, int]]] = {}
    for c in cars:
        if c.irating is not None and c.position:
            by_class.setdefault(c.class_name, []).append((c.idx, float(c.irating), c.position))
    out: dict[int, int] = {}
    for entries in by_class.values():
        out.update(projected_changes(entries))
    return out


def profile_chips(snap: Snapshot, my_delta: Optional[int]) -> list[Chip]:
    p = snap.profile
    manual = p.source.value == "manual" and snap.sim.value != "demo"
    star = "*" if manual else ""
    chips: list[Chip] = []
    if p.license_class:
        sr = f" {p.license_sr:.2f}" if p.license_sr is not None else ""
        chips.append(Chip("LIC", f"{p.license_class}{sr}", license_color(p.license_class)))
    if p.irating is not None:
        chips.append(Chip("iR", f"{p.irating}", "#f4f4f5", delta=my_delta))
    if p.driver_rank:
        chips.append(Chip("DRIVER" + star, str(p.driver_rank), "#f4f4f5", rank="DR"))
    if p.safety_rank:
        chips.append(Chip("SAFETY" + star, str(p.safety_rank), "#f4f4f5", rank="SR"))
    if p.contact_badge:
        chips.append(Chip("BADGE" + star, str(p.contact_badge), "#f4f4f5", badge=badges.slug(p.contact_badge)))
    if not chips:
        chips.append(Chip("RANK", "n/d", "#8b8b95", available=False))
    return chips


class NrgTracker:
    """Decide se a coluna NRG aparece: quando a sessão tem ALGUMA categoria com energia virtual.

    O NRG é por categoria: a coluna aparece se algum carro presente tem energia, e só as linhas das categorias que
    têm NRG mostram o valor (as outras ficam em branco). Uma categoria "com NRG" é lembrada, então a leitura falhar
    por um instante num carro (ex.: energia em 0%) não faz a coluna piscar. A memória vale por sessão.
    """

    def __init__(self) -> None:
        self._sig: Optional[tuple] = None
        self._classes: set = set()

    def reset(self) -> None:
        self._sig = None
        self._classes = set()

    def visible(self, snap: Snapshot) -> bool:
        sig = (snap.sim, snap.session.track_name, snap.session.session_type)
        if sig != self._sig:
            self._sig, self._classes = sig, set()
        for c in snap.cars:
            if c.energy_pct is not None:
                self._classes.add(c.class_name)
        return any(c.class_name in self._classes for c in snap.cars)


def lap_time(c: CarState) -> Optional[float]:
    """Tempo de volta que classifica o carro em treino/qualy (melhor volta, senão a última)."""
    return c.best_lap or c.last_lap or None


def ranked_by_time(cars: Sequence[CarState]) -> list[CarState]:
    """Só quem já fez tempo, do mais rápido ao mais lento, com posição geral e da classe RECALCULADAS.

    Em treino e qualificação a posição publicada pelo simulador não é confiável antes de existirem tempos;
    a classificação é, por definição, a ordem dos melhores tempos.
    """
    timed = sorted((c for c in cars if lap_time(c)), key=lambda c: lap_time(c))
    per_class: dict[Optional[str], int] = {}
    out: list[CarState] = []
    for i, c in enumerate(timed, start=1):
        per_class[c.class_name] = per_class.get(c.class_name, 0) + 1
        out.append(replace(c, position=i, class_position=per_class[c.class_name]))
    return out


def build_standings(snap: Snapshot, opts: StandingsOptions, pos_changes: Optional[dict[int, int]] = None,
                    flags: Optional[FlagResolver] = None) -> StandingsView:
    race = is_race(snap.session.session_type)
    view = StandingsView(scope=opts.scope, mode="race" if race else "best", bar=build_session_bar(snap))
    pos_changes = pos_changes or {}
    if race:
        # corrida: TODOS os pilotos. Quem ainda não tem posição (fora do mundo, saiu) vem depois, apagado.
        positioned = sorted((c for c in snap.cars if c.position), key=lambda c: c.position or 0)
        all_cars = positioned + [c for c in snap.cars if not c.position]
    else:
        all_cars = ranked_by_time(snap.cars)  # treino/qualy: só quem fez tempo
    view.total = len(all_cars)
    me = snap.player()
    deltas = ir_deltas(all_cars) if race else {}
    view.chips = profile_chips(snap, deltas.get(me.idx) if me else None)
    if not all_cars:
        view.hidden = not race  # sem tempos ainda: o módulo nem aparece
        return view
    class_totals = Counter(c.class_name for c in snap.cars if c.in_session)

    # agrupa por classe; a ordem dos grupos segue a posição do líder de cada classe
    by_class: dict[Optional[str], list[CarState]] = {}
    for c in all_cars:
        by_class.setdefault(c.class_name, []).append(c)
    ordered = sorted(by_class.items(), key=lambda kv: kv[1][0].position or 10 ** 6)
    if opts.scope == "class" and me is not None:
        ordered = [(k, v) for k, v in ordered if k == me.class_name]
    single = len(ordered) == 1

    for class_name, cars in ordered:
        style = class_style(class_name, next((c.class_color for c in cars if c.class_color), None), snap.sim)
        group = Group(style.label, style.color, total=None if race else class_totals.get(class_name))
        ref_best = min((c.best_lap for c in cars if c.best_lap), default=None)
        for i, c in enumerate(cars):
            prev = cars[i - 1] if i > 0 else None
            if race:
                gap = "—" if i == 0 else _delta_text(c, cars[0])
                inter = "—" if prev is None else _delta_text(c, prev)
                if prev is not None and inter == "—" and single and c.gap_ahead is not None:
                    inter = format_gap(c.gap_ahead)
            else:
                gap = inter = "—"
                if c.best_lap and ref_best is not None and c.best_lap > ref_best + 1e-9:
                    gap = format_gap(c.best_lap - ref_best)
                if prev is not None and prev.best_lap and c.best_lap and c.best_lap >= prev.best_lap:
                    inter = format_gap(c.best_lap - prev.best_lap)
            flag = "class" if (c.best_lap and ref_best is not None and abs(c.best_lap - ref_best) < 1e-9) else ""
            if c.status in (CarStatus.OUT, CarStatus.DISQUALIFIED, CarStatus.GARAGE) or not c.in_session:
                dim = "out"  # fora da pista ou fora da sessão: linha apagada
            elif c.status == CarStatus.PITS:
                dim = "pit"
            elif me is not None and not c.is_player and c.class_name != me.class_name:
                dim = "other_class"
            else:
                dim = "none"
            group.rows.append(StandingsRow(
                car=c, pos_text="—" if not c.position else str(c.class_position or (i + 1)), class_label=style.label,
                class_color=style.color, number_text=c.car_number or "", name=c.driver_name,
                model=c.car_model or "", license_class=c.license_class or "",
                license_sr_text=f"{c.license_sr:.1f}" if c.license_sr is not None else "",
                irating_text=format_ir(c.irating) if c.irating is not None else "",
                ir_delta=deltas.get(c.idx), brand=brand_for_car(c.car_model, c.vehicle_raw, c.team_name, c.class_name, snap.sim),
                country=flags.code_for(c) if flags else c.country,
                laps_text="" if c.laps_completed is None else str(c.laps_completed),
                pos_change=pos_changes.get(c.idx), tire=c.tire, int_text=inter, gap_text=gap,
                best_text=format_laptime(c.best_lap), last_text=format_laptime(c.last_lap),
                energy_pct=c.energy_pct, status_tag=_TAGS.get(c.status, ""), is_player=c.is_player,
                dim=dim, best_flag=flag,
                badge=(badges.slug(snap.profile.contact_badge) if c.is_player and snap.profile.contact_badge
                       and not (flags.code_for(c) if flags else c.country) else None),
            ))
        view.groups.append(group)
    view.player = next((r for r in view.rows if r.is_player), None)
    return view


# ---- seleção de linhas --------------------------------------------------- #
def select_rows(rows: Sequence[T], player_index: Optional[int], max_rows: int,
                top: int = 3) -> list[Optional[T]]:
    """Escolhe quais linhas mostrar: os `top` primeiros + janela em volta do piloto.

    `None` na saída marca um corte (reticências) entre o topo e a janela do piloto.
    """
    n = len(rows)
    if max_rows <= 0:
        return []
    if n <= max_rows:
        return list(rows)
    if player_index is None or player_index < max_rows:
        return list(rows[:max_rows])  # piloto já está na primeira página (ou não existe)
    if max_rows < 4:  # orçamento minúsculo: só a janela em volta do piloto
        a = min(max(player_index - max_rows // 2, 0), n - max_rows)
        return list(rows[a:a + max_rows])
    top = min(top, max_rows - 2)
    k = max_rows - top - 1  # reserva uma vaga para o separador
    a = min(max(player_index - k // 2, top), n - k)
    return list(rows[:top]) + [None] + list(rows[a:a + k])


def select_lines(groups: list[Group], max_lines: int, top: int = 3) -> list[Line]:
    """Linhas visíveis, SEMPRE com um cabeçalho por classe (também em corridas de uma classe só).

    Classes que não são a do piloto mostram só o topo (`top` carros); a classe do piloto usa o
    orçamento restante: topo + janela em volta dele. Se faltar espaço, o topo das outras classes
    encolhe antes de espremer a classe do piloto; se sobrar, as outras classes mostram mais carros.
    """
    if not groups or max_lines <= 0:
        return []

    def player_index(g: Group) -> Optional[int]:
        return next((i for i, r in enumerate(g.rows) if r.is_player), None)

    budget = max_lines - len(groups)  # uma linha de cabeçalho por classe
    pg = next((i for i, g in enumerate(groups) if player_index(g) is not None), None)
    others = [i for i in range(len(groups)) if i != pg]
    shown: dict[int, list[Optional[StandingsRow]]] = {}
    if pg is None:  # sem piloto: divide o orçamento igualmente
        base, extra = divmod(max(budget, 0), len(groups))
        for k, g in enumerate(groups):
            shown[k] = list(g.rows[: max(1, base + (1 if k < extra else 0))])
    else:
        t = top
        while True:
            used = sum(min(groups[i].count, t) for i in others)
            room = budget - used
            if room >= min(groups[pg].count, 5) or t <= 1:
                break
            t -= 1
        counts = {i: min(groups[i].count, t) for i in others}
        pg_room = min(max(room, 1), groups[pg].count)
        leftover = room - pg_room
        while leftover > 0:  # sobrou espaço: as outras classes mostram mais carros
            grew = False
            for i in others:
                if leftover > 0 and counts[i] < groups[i].count:
                    counts[i] += 1
                    leftover -= 1
                    grew = True
            if not grew:
                break
        for i in others:
            shown[i] = list(groups[i].rows[: counts[i]])
        shown[pg] = select_rows(groups[pg].rows, player_index(groups[pg]), pg_room, min(top, t))
    lines: list[Line] = []
    for k, g in enumerate(groups):
        lines.append(HeaderLine(g.label, g.color, g.header_count))
        lines.extend(shown[k])
    while len(lines) > max_lines:  # último recurso: corta do fim, preservando a linha do piloto
        idx = next((i for i in range(len(lines) - 1, -1, -1)
                    if not (isinstance(lines[i], StandingsRow) and lines[i].is_player)), None)
        if idx is None:
            break
        lines.pop(idx)
    return lines
