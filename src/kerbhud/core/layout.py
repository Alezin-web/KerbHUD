"""Layouts de módulos: modelo, geometria, presets e persistência (sem Qt).

As posições são salvas como FRAÇÕES da tela (x, y, largura, altura entre 0 e 1)
junto com o nome do monitor. Assim o layout continua coerente se a resolução
mudar ou se o monitor não existir mais (cai no principal).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 4  # 2/3: Standings/Relative legíveis; 4: escala de texto fixa (Standings/Inputs) (`migrate_layout`)
GRID = 8  # px do snap


@dataclass(frozen=True)
class ModuleSpec:
    id: str
    title: str
    design_w: int  # tamanho de projeto: o conteúdo é desenhado nessa grade e escalado
    design_h: int
    min_w: int = 120
    min_h: int = 40


MODULES: dict[str, ModuleSpec] = {m.id: m for m in (
    ModuleSpec("standings", "STANDINGS", 1122, 624, 540, 260),
    ModuleSpec("relative", "RELATIVE", 650, 280, 360, 150),
    ModuleSpec("inputs", "INPUTS", 620, 112, 310, 56),
    ModuleSpec("telemetry", "TELEMETRIA", 640, 200, 280, 100),
    ModuleSpec("trackmap", "TRACK MAP", 360, 300, 160, 140),
    ModuleSpec("fuel", "COMBUSTÍVEL", 580, 330, 300, 190),
    ModuleSpec("damage", "CAR DAMAGE", 220, 290, 130, 160),
    ModuleSpec("tires", "PNEUS", 330, 240, 260, 190),
    ModuleSpec("spotter", "SPOTTER", 520, 190, 200, 90),
    ModuleSpec("radar", "RADAR", 240, 240, 140, 140),
    ModuleSpec("digflag", "DIGFLAG", 240, 240, 110, 110),
    ModuleSpec("status", "STATUS", 300, 36, 150, 24),
)}


def design_size(module_id: str, options: dict) -> tuple[float, float]:
    """Tamanho de projeto do módulo; Standings e Relative variam com as opções (linhas/colunas)."""
    if module_id == "standings":
        from .standings import standings_design_size
        return standings_design_size(options)
    if module_id == "relative":
        from .relative import relative_design_size
        return relative_design_size(options)
    spec = MODULES[module_id]
    return float(spec.design_w), float(spec.design_h)


#: Módulos com TAMANHO DE TEXTO FIXO: redimensionar a janela muda a área visível (mais/menos linhas e colunas,
#: gráfico mais longo), nunca o tamanho do texto. O tamanho do texto é `options["scale"]`.
FIXED_SCALE_MODULES = ("standings", "inputs")
SCREEN_ASPECT = 16 / 9


def natural_scale(module_id: str, rect: tuple, options: dict) -> float:
    """Escala (fração da LARGURA DA TELA por unidade de desenho) que a janela `rect` tinha no modo antigo,
    em que o conteúdo era ajustado à janela. Usada para que layouts existentes fiquem com o mesmo texto."""
    dw, dh = design_size(module_id, options)
    _fx, _fy, fw, fh = rect
    return min(fw / dw, fh / (dh * SCREEN_ASPECT))


@dataclass(frozen=True)
class ScreenInfo:
    name: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class ModuleState:
    visible: bool = True
    rect: tuple = (0.0, 0.0, 0.2, 0.2)  # fx, fy, fw, fh
    screen: Optional[str] = None
    opacity: float = 1.0
    options: dict = field(default_factory=dict)  # reservado para canais/cores dos módulos


@dataclass
class Layout:
    name: str
    modules: dict[str, ModuleState]
    always_on_top: bool = True
    version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version, "name": self.name, "always_on_top": self.always_on_top,
            "modules": {
                mid: {"visible": s.visible, "rect": [round(v, 5) for v in s.rect], "screen": s.screen,
                      "opacity": round(s.opacity, 3), "options": s.options}
                for mid, s in self.modules.items()
            },
        }

    @staticmethod
    def from_dict(d: dict, fallback: Optional["Layout"] = None) -> "Layout":
        """Valida e normaliza. Módulos ausentes/ inválidos vêm do `fallback`/padrão."""
        if not isinstance(d, dict) or not isinstance(d.get("name"), str) or not d["name"].strip():
            raise ValueError("layout sem nome")
        base = fallback or preset_corrida()
        mods: dict[str, ModuleState] = {}
        raw = d.get("modules") if isinstance(d.get("modules"), dict) else {}
        for mid in MODULES:
            r = raw.get(mid)
            default = base.modules[mid]
            if not isinstance(r, dict):
                mods[mid] = ModuleState(default.visible, default.rect, default.screen, default.opacity, {})
                continue
            rect = r.get("rect")
            try:
                fx, fy, fw, fh = (float(v) for v in rect)
                if not all(map(_finite, (fx, fy, fw, fh))):
                    raise ValueError
            except (TypeError, ValueError):
                fx, fy, fw, fh = default.rect
            fw, fh = min(max(fw, 0.02), 1.0), min(max(fh, 0.02), 1.0)
            fx, fy = min(max(fx, 0.0), 1.0 - fw), min(max(fy, 0.0), 1.0 - fh)
            try:
                op = min(max(float(r.get("opacity", 1.0)), 0.1), 1.0)
            except (TypeError, ValueError):
                op = 1.0
            scr = r.get("screen")
            mods[mid] = ModuleState(
                visible=bool(r.get("visible", True)), rect=(fx, fy, fw, fh),
                screen=scr if isinstance(scr, str) else None, opacity=op,
                options=r.get("options") if isinstance(r.get("options"), dict) else {},
            )
        try:
            version = int(d.get("version", 1))
        except (TypeError, ValueError):
            version = 1
        return Layout(name=d["name"].strip(), modules=mods, always_on_top=bool(d.get("always_on_top", True)),
                      version=version)


def _finite(v: float) -> bool:
    return v == v and abs(v) != float("inf")


# --------------------------------------------------------------------------- #
# Geometria
# --------------------------------------------------------------------------- #
def _pick_screen(name: Optional[str], screens: list[ScreenInfo], primary: Optional[str]) -> ScreenInfo:
    if not screens:
        raise ValueError("nenhuma tela")
    for s in screens:
        if name and s.name == name:
            return s
    for s in screens:
        if s.name == primary:
            return s
    return screens[0]


pick_screen = _pick_screen


def rect_to_pixels(state: ModuleState, spec: ModuleSpec, screens: list[ScreenInfo],
                   primary: Optional[str] = None) -> tuple[int, int, int, int]:
    """Fração -> pixels absolutos, garantindo tamanho mínimo e módulo dentro da tela."""
    s = _pick_screen(state.screen, screens, primary)
    fx, fy, fw, fh = state.rect
    w = int(round(fw * s.w)); h = int(round(fh * s.h))
    w = min(max(w, spec.min_w), s.w); h = min(max(h, spec.min_h), s.h)
    x = int(round(s.x + fx * s.w)); y = int(round(s.y + fy * s.h))
    x = min(max(x, s.x), s.x + s.w - w); y = min(max(y, s.y), s.y + s.h - h)
    return x, y, w, h


def pixels_to_rect(px: tuple[int, int, int, int], screens: list[ScreenInfo]) -> tuple[tuple, str]:
    """Pixels absolutos -> (fração, nome do monitor com maior interseção)."""
    x, y, w, h = px

    def overlap(s: ScreenInfo) -> int:
        ox = max(0, min(x + w, s.x + s.w) - max(x, s.x))
        oy = max(0, min(y + h, s.y + s.h) - max(y, s.y))
        return ox * oy

    s = max(screens, key=lambda sc: (overlap(sc), -abs(sc.x - x)))
    fw, fh = w / s.w, h / s.h
    fx, fy = (x - s.x) / s.w, (y - s.y) / s.h
    fw, fh = min(max(fw, 0.0), 1.0), min(max(fh, 0.0), 1.0)
    fx, fy = min(max(fx, 0.0), 1.0 - fw), min(max(fy, 0.0), 1.0 - fh)
    return (fx, fy, fw, fh), s.name


def snap(v: float, grid: int = GRID) -> int:
    return int(round(v / grid) * grid)


def compute_drag(mode: str, start: tuple[int, int, int, int], dx: int, dy: int,
                 min_size: tuple[int, int], grid: Optional[int] = GRID) -> tuple[int, int, int, int]:
    """Calcula o novo (x, y, w, h) durante arraste/redimensionamento.

    mode: "move" ou combinação de "l", "r", "t", "b" (bordas arrastadas).
    grid: None desliga o snap (ex.: segurando Alt).
    """
    x1, y1 = start[0], start[1]
    x2, y2 = start[0] + start[2], start[1] + start[3]
    mw, mh = min_size
    if mode == "move":
        x1 += dx; x2 += dx; y1 += dy; y2 += dy
        if grid:
            sx = snap(x1, grid) - x1; sy = snap(y1, grid) - y1
            x1 += sx; x2 += sx; y1 += sy; y2 += sy
        return x1, y1, x2 - x1, y2 - y1
    if "l" in mode:
        x1 += dx
    if "r" in mode:
        x2 += dx
    if "t" in mode:
        y1 += dy
    if "b" in mode:
        y2 += dy
    if grid:
        if "l" in mode: x1 = snap(x1, grid)
        if "r" in mode: x2 = snap(x2, grid)
        if "t" in mode: y1 = snap(y1, grid)
        if "b" in mode: y2 = snap(y2, grid)
    if x2 - x1 < mw:
        if "l" in mode: x1 = x2 - mw
        else: x2 = x1 + mw
    if y2 - y1 < mh:
        if "t" in mode: y1 = y2 - mh
        else: y2 = y1 + mh
    return x1, y1, x2 - x1, y2 - y1


def scale_about_topleft(px: tuple[int, int, int, int], factor: float,
                        min_size: tuple[int, int]) -> tuple[int, int, int, int]:
    """Redimensiona mantendo a proporção (roda do mouse no modo de edição)."""
    x, y, w, h = px
    f = max(factor, min_size[0] / w, min_size[1] / h)
    return x, y, int(round(w * f)), int(round(h * f))


def hit_test(px: int, py: int, w: int, h: int, margin: int = 10) -> str:
    """Região do mouse dentro da janela: "move" ou bordas ("l", "tr", ...)."""
    mode = ""
    if py <= margin: mode += "t"
    elif py >= h - margin: mode += "b"
    if px <= margin: mode += "l"
    elif px >= w - margin: mode += "r"
    return mode or "move"


# --------------------------------------------------------------------------- #
# Migração de layouts salvos
# --------------------------------------------------------------------------- #
LEGIBLE_WIDTH = {"standings": 0.53, "relative": 0.32}  # fração da largura da tela (16:9) para texto confortável


def fit_height(module_id: str, fw: float, options: dict, screen_aspect: float = 16 / 9) -> float:
    """Altura (fração da tela) que mantém a proporção do desenho do módulo para a largura `fw`."""
    dw, dh = design_size(module_id, options)
    return fw * screen_aspect / (dw / dh)


def migrate_layout(layout: Layout) -> bool:
    """Leva um layout salvo por uma versão antiga ao formato atual (roda uma vez por layout).

    1. Standings e Relative recebem o tamanho legível (a janela de layouts antigos ficou pequena para o
       desenho atual), mantendo a posição do canto superior esquerdo; tamanhos maiores são mantidos.
    2. Standings e Inputs passam a ter TEXTO DE TAMANHO FIXO: gravamos em `options["scale"]` o tamanho que
       eles têm hoje, então nada muda visualmente; a partir daí redimensionar não mexe no texto.
    """
    if layout.version >= SCHEMA_VERSION:
        return False
    for mid, target in LEGIBLE_WIDTH.items():
        st = layout.modules.get(mid)
        if st is None:
            continue
        fx, fy, fw, _fh = st.rect
        nfw = min(max(fw, target), 1.0)
        nfh = min(fit_height(mid, nfw, st.options), 1.0)
        st.rect = (min(max(fx, 0.0), 1.0 - nfw), min(max(fy, 0.0), 1.0 - nfh), nfw, nfh)
    _avoid_overlap(layout)
    for mid in FIXED_SCALE_MODULES:
        st = layout.modules.get(mid)
        if st is not None and not isinstance(st.options.get("scale"), (int, float)):
            st.options["scale"] = round(natural_scale(mid, st.rect, st.options), 9)
    layout.version = SCHEMA_VERSION
    return True


def _avoid_overlap(layout: Layout) -> None:
    """Se o Standings ampliado passou a cobrir o Relative, empurra o Relative para baixo dele."""
    a, b = layout.modules.get("standings"), layout.modules.get("relative")
    if a is None or b is None or not (a.visible and b.visible):
        return
    ax, ay, aw, ah = a.rect
    bx, by, bw, bh = b.rect
    horizontal = ax < bx + bw and bx < ax + aw
    vertical = ay < by + bh and by < ay + ah
    if horizontal and vertical:
        b.rect = (bx, min(ay + ah + 0.01, 1.0 - bh), bw, bh)


# --------------------------------------------------------------------------- #
# Presets
# --------------------------------------------------------------------------- #
def _layout(name: str, vis: dict[str, bool], rects: dict[str, tuple],
            options: Optional[dict[str, dict]] = None) -> Layout:
    options = options or {}
    layout = Layout(name, {mid: ModuleState(vis.get(mid, False), rects[mid], options=dict(options.get(mid, {})))
                           for mid in MODULES})
    for mid in FIXED_SCALE_MODULES:
        st = layout.modules[mid]
        st.options.setdefault("scale", round(natural_scale(mid, st.rect, st.options), 9))
    return layout


_R_CORRIDA = {
    "standings": (0.010, 0.07, 0.530, 0.5240), "relative": (0.010, 0.615, 0.320, 0.2451),
    "inputs": (0.360, 0.880, 0.280, 0.090), "telemetry": (0.300, 0.62, 0.40, 0.20),
    "trackmap": (0.800, 0.10, 0.19, 0.30), "status": (0.425, 0.005, 0.150, 0.032),
    "fuel": (0.715, 0.42, 0.275, 0.278), "damage": (0.715, 0.70, 0.12, 0.28),
    "tires": (0.835, 0.70, 0.155, 0.27), "spotter": (0.36, 0.41, 0.28, 0.17),
    "radar": (0.57, 0.20, 0.12, 0.213), "digflag": (0.575, 0.03, 0.09, 0.16),
}


def preset_corrida() -> Layout:
    return _layout("Corrida", {"standings": True, "relative": True, "inputs": True,
                               "trackmap": True, "fuel": True, "damage": True, "tires": True, "spotter": True,
                               "radar": True, "digflag": True, "status": True}, _R_CORRIDA)


def preset_treino() -> Layout:
    r = dict(_R_CORRIDA)
    r.update({"relative": (0.010, 0.10, 0.320, 0.2451), "telemetry": (0.300, 0.66, 0.40, 0.18),
              "inputs": (0.010, 0.60, 0.280, 0.090)})
    return _layout("Treino", {"relative": True, "inputs": True, "telemetry": True,
                              "trackmap": True, "tires": True, "digflag": True, "status": True}, r)


def preset_telemetria() -> Layout:
    r = dict(_R_CORRIDA)
    r.update({"telemetry": (0.250, 0.72, 0.50, 0.26), "inputs": (0.300, 0.56, 0.400, 0.128),
              "trackmap": (0.800, 0.05, 0.19, 0.30), "damage": (0.76, 0.40, 0.12, 0.28),
              "tires": (0.88, 0.42, 0.11, 0.18)})
    return _layout("Telemetria", {"telemetry": True, "inputs": True, "trackmap": True, "damage": True,
                                  "tires": True, "status": True}, r)


def preset_broadcast() -> Layout:
    r = dict(_R_CORRIDA)
    r.update({"standings": (0.010, 0.06, 0.530, 0.7256), "trackmap": (0.780, 0.06, 0.21, 0.34)})
    return _layout("Broadcast", {"standings": True, "trackmap": True, "digflag": True, "status": True}, r,
                   options={"standings": {"rows": 26}})


PRESETS = (preset_corrida, preset_treino, preset_telemetria, preset_broadcast)


# --------------------------------------------------------------------------- #
# Persistência
# --------------------------------------------------------------------------- #
MAX_IMPORT_BYTES = 1_000_000  # um layout tem poucos KB; mais que isso não é um layout
_BAD = re.compile(r"[^\w \-]", re.UNICODE)


def slug(name: str) -> str:
    s = _BAD.sub("", name).strip().replace(" ", "_")[:60]
    if not s or set(s) <= {"."}:
        raise ValueError("nome de layout inválido")
    return s


class LayoutStore:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._state = self.dir.parent / "state.json"

    def _path(self, name: str) -> Path:
        return self.dir / f"{slug(name)}.json"

    def ensure_defaults(self) -> None:
        """Cria os presets que faltam. Nunca sobrescreve arquivos do usuário."""
        for make in PRESETS:
            lay = make()
            if not self._path(lay.name).exists():
                self.save(lay)

    def reset_defaults(self) -> None:
        """Restaura os 4 layouts padrão (sobrescreve só os que têm o nome dos presets)."""
        for make in PRESETS:
            self.save(make())

    def list_names(self) -> list[str]:
        names = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                names.append(json.loads(p.read_text(encoding="utf-8"))["name"])
            except (OSError, ValueError, KeyError, TypeError):
                continue  # arquivo corrompido não derruba a lista
        order = [make().name for make in PRESETS]
        return sorted(names, key=lambda n: (order.index(n) if n in order else len(order), n.lower()))

    def load(self, name: str) -> Layout:
        data = json.loads(self._path(name).read_text(encoding="utf-8"))
        layout = Layout.from_dict(data)
        if migrate_layout(layout):
            self.save(layout)  # grava já migrado: a migração acontece uma única vez
        return layout

    def save(self, layout: Layout) -> None:
        path = self._path(layout.name)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(layout.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # escrita atômica

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def duplicate(self, src: str, new_name: str) -> Layout:
        lay = self.load(src)
        lay.name = new_name.strip()
        self.save(lay)
        return lay

    def unique_name(self, base: str) -> str:
        """`base`, ou `base (2)`, `base (3)`... se já existir um layout com esse nome."""
        base = base.strip() or "Layout"
        taken = {n.lower() for n in self.list_names()}
        name, n = base, 2
        while name.lower() in taken:
            name = f"{base} ({n})"
            n += 1
        slug(name)  # levanta ValueError se o nome não der um arquivo válido
        return name

    def rename(self, old: str, new: str) -> Layout:
        """Renomeia um layout (arquivo e nome interno). Levanta ValueError se o novo nome já existe ou é inválido."""
        new = new.strip()
        slug(new)
        if new.lower() != old.lower() and new.lower() in {n.lower() for n in self.list_names()}:
            raise ValueError(f"já existe um layout chamado '{new}'")
        lay = self.load(old)
        lay.name = new
        self.save(lay)
        if self._path(old) != self._path(new):
            self._path(old).unlink(missing_ok=True)
        if self.get_active() == old:
            self.set_active(new)
        return lay

    def export_layout(self, name: str, path: Path) -> None:
        """Grava uma cópia do layout em `path` (para compartilhar ou guardar)."""
        lay = self.load(name)
        Path(path).write_text(json.dumps(lay.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def import_layout(self, path: Path) -> Layout:
        """Importa um layout exportado. Valida o arquivo e nunca sobrescreve: nome repetido vira `nome (2)`."""
        p = Path(path)
        if p.stat().st_size > MAX_IMPORT_BYTES:
            raise ValueError("arquivo grande demais para ser um layout")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"arquivo inválido: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("modules"), dict):
            raise ValueError("não parece um layout do KerbHUD")
        lay = Layout.from_dict(data)
        migrate_layout(lay)
        try:
            lay.name = self.unique_name(_BAD.sub("", str(data.get("name") or p.stem)).strip(". "))
        except ValueError:  # nome só com símbolos
            lay.name = self.unique_name("Importado")
        self.save(lay)
        return lay

    def get_active(self) -> Optional[str]:
        try:
            return json.loads(self._state.read_text(encoding="utf-8")).get("active_layout")
        except (OSError, ValueError, AttributeError):
            return None

    def set_active(self, name: str) -> None:
        self._state.write_text(json.dumps({"active_layout": name}, ensure_ascii=False), encoding="utf-8")
