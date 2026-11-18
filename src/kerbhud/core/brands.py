"""Marca (fabricante/construtor) do carro, inferida do texto do veículo (nome do modelo, arquivo, caminho).

A interface desenha a LOGOTIPO REAL da marca, lida de `<pasta de configuração>/logos/<chave>.png`
(ex.: `bmw.png`; também aceita `.webp`, `.jpg` e `.svg`). Os arquivos não vêm com o app (são marcas registradas
dos fabricantes): baixe-os pelo menu da bandeja ("Baixar logos de carros") ou com `python -m kerbhud fetch-logos`,
e coloque à mão os que o download não encontrar (`python -m kerbhud logos-status` lista quais faltam).

O catálogo cobre os carros do iRacing (lista oficial 2026) e do Le Mans Ultimate. Carros de oval/dirt sem fabricante
identificável (Sprint Car, Late Model, Street Stock, Midget...) ficam SEM marca, de propósito: nada é inventado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Brand:
    key: str  # nome do arquivo de logo (sem extensão): `<key>.png`
    label: str  # sigla curta (diagnóstico)
    color: str  # "#rrggbb" (cor da marca)
    fallback: Optional[str] = None  # logo alternativa se `<key>.png` não existir (ex.: Corvette -> Chevrolet)
    name: str = ""  # nome completo da fabricante (mostrado como texto quando não há arquivo de logo)

    @property
    def display_name(self) -> str:
        return self.name or self.label


# (palavras-chave, chave, sigla, nome, cor). A PRIMEIRA regra que casar vence, então as mais específicas vêm antes.
# Palavra-chave com "~" na frente = palavra INTEIRA (evita "Crawford" casar com FORD ou "Claudio" com AUDI);
# sem "~" = trecho do texto (cobre caminhos como "porsche963gtp"). Tudo em MAIÚSCULAS.
_RULES: tuple[tuple[tuple[str, ...], str, str, str, str], ...] = (
    # --- construtores específicos antes das marcas de motor/carro ---
    # pequenos construtores de corrida primeiro: o nome do carro costuma citar o motor ("Ray ... Formula FORD")
    (("~RAY", "~FF1600", "FORMULA FORD"), "ray", "RAY", "Ray", "#ef4444"),
    (("RADICAL",), "radical", "RAD", "Radical", "#f97316"),
    (("RILEY",), "riley", "RIL", "Riley", "#a855f7"),
    (("SKIP BARBER", "SKIPBARBER"), "skipbarber", "SKB", "Skip Barber", "#dc2626"),
    (("~SABRE",), "sabre", "SAB", "Sabre", "#64748b"),
    (("SHEANE",), "sheane", "SHE", "Sheane", "#64748b"),
    (("CORVETTE", "~C8.R", "~C7.R", "~C6.R"), "corvette", "CRV", "Corvette", "#d4a017"),
    (("WILLIAMS", "~FW31"), "williams", "WIL", "Williams", "#00a0dd"),
    (("MCLAREN", "~720S", "~570S", "~MP4", "~12C"), "mclaren", "MCL", "McLaren", "#ff8000"),
    (("MERCEDES", "~AMG"), "mercedes", "MB", "Mercedes-AMG", "#9aa0a6"),
    (("ASTON", "VALKYRIE", "~DBR9", "~VANTAGE"), "astonmartin", "AM", "Aston Martin", "#00665e"),
    (("BMW", "M HYBRID"), "bmw", "BMW", "BMW", "#1c69d4"),
    (("PORSCHE", "MANTHEY", "~963", "~919", "~911", "~718", "MISSION R", "CAYMAN"), "porsche", "POR", "Porsche", "#b31b1b"),
    (("FERRARI", "AF CORSE", "AFCORSE", "~499P", "~296", "~488"), "ferrari", "FER", "Ferrari", "#dc0000"),
    (("~AUDI", "AUDIR", "~R8 LMS"), "audi", "AUDI", "Audi", "#bb0a30"),
    (("TOYOTA", "GR010", "TUNDRA", "CAMRY", "SUPRA", "~GR86", "COROLLA"), "toyota", "TOY", "Toyota", "#eb0a1e"),
    (("CADILLAC", "V-SERIES", "V SERIES", "CTS-V"), "cadillac", "CAD", "Cadillac", "#7a1f2b"),
    (("PEUGEOT", "~9X8"), "peugeot", "PEU", "Peugeot", "#0033a0"),
    (("LAMBORGHINI", "HURAC", "~SC63"), "lamborghini", "LAM", "Lamborghini", "#ddb321"),
    (("CHEVROLET", "CHEVY", "CAMARO", "IMPALA", "MONTE CARLO", "SILVERADO", "CRUZE"), "chevrolet", "CHV",
     "Chevrolet", "#d4a017"),
    (("~FORD", "MUSTANG", "FALCON", "FIESTA", "F-150", "FUSION", "TAURUS", "THUNDERBIRD"), "ford", "FORD", "Ford",
     "#003478"),
    (("LEXUS", "~RCF", "~RC F"), "lexus", "LEX", "Lexus", "#5b6770"),
    (("ACURA", "~ARX-06", "~ARX 06", "~ARX-01", "~ARX 01", "~NSX", "~HPD"), "acura", "ACU", "Acura", "#cc0000"),
    (("HONDA", "CIVIC"), "honda", "HON", "Honda", "#cc0000"),
    (("NISSAN", "~ZX-T"), "nissan", "NIS", "Nissan", "#c3002f"),
    (("MAZDA", "~MX-5", "~MX5"), "mazda", "MZD", "Mazda", "#910a2d"),
    (("ALPINE", "~A424"), "alpine", "ALP", "Alpine", "#0090d0"),
    (("GLICKENHAUS", "~SCG"), "glickenhaus", "SCG", "Glickenhaus", "#d9232d"),
    (("ISOTTA", "TIPO6", "TIPO 6"), "isotta", "ISO", "Isotta Fraschini", "#8b1e3f"),
    (("ORECA",), "oreca", "ORE", "Oreca", "#3b82f6"),
    (("LIGIER", "JS P320", "JSP320", "CROSS CAR"), "ligier", "LIG", "Ligier", "#1d4ed8"),
    (("ADESS", "~AD25"), "adess", "ADS", "Adess", "#e11d48"),  # construtor suíço de LMP3 (AD25 / 03 Evo)
    (("DUQUEINE",), "duqueine", "DUQ", "Duqueine", "#0ea5e9"),
    (("GINETTA",), "ginetta", "GIN", "Ginetta", "#16a34a"),
    (("DALLARA", "SUPER FORMULA", "~SF23", "~IR-01", "~IR01", "~IL-15", "~IL15", "~P217", "~F312", "~DW12"),
     "dallara", "DAL", "Dallara", "#2563eb"),
    (("GENESIS", "~GMR-001"), "genesis", "GEN", "Genesis", "#6b4f2a"),
    (("HYUNDAI", "ELANTRA", "VELOSTER"), "hyundai", "HYU", "Hyundai", "#002c5f"),
    (("~KIA", "OPTIMA"), "kia", "KIA", "Kia", "#05141f"),
    (("LOTUS",), "lotus", "LTS", "Lotus", "#ffd400"),
    (("VANWALL", "VANDERVELL"), "vanwall", "VAN", "Vanwall", "#0b6e4f"),
    (("SUBARU", "~WRX"), "subaru", "SUB", "Subaru", "#003399"),
    (("VOLKSWAGEN", "~VW", "BEETLE", "JETTA"), "volkswagen", "VW", "Volkswagen", "#001e50"),
    (("RENAULT", "~CLIO"), "renault", "REN", "Renault", "#efdf00"),
    (("~RUF",), "ruf", "RUF", "RUF", "#0a3d91"),
    (("PONTIAC", "SOLSTICE", "GRAND PRIX"), "pontiac", "PON", "Pontiac", "#b91c1c"),
    (("BUICK", "LESABRE"), "buick", "BUI", "Buick", "#6b7280"),
    (("HOLDEN", "COMMODORE"), "holden", "HOL", "Holden", "#f59e0b"),
    (("~RAM",), "ram", "RAM", "Ram", "#7f1d1d"),
    (("~DODGE", "~CHARGER"), "dodge", "DOD", "Dodge", "#b91c1c"),
)

_FALLBACKS = {"corvette": "chevrolet"}


def _compile(needle: str):
    """Trecho simples -> teste `in`; palavra inteira ("~X") -> regex com limites alfanuméricos."""
    if needle.startswith("~"):
        word = re.compile(rf"(?<![A-Z0-9]){re.escape(needle[1:])}(?![A-Z0-9])")
        return lambda blob: word.search(blob) is not None
    return lambda blob: needle in blob


_COMPILED = tuple(
    (tuple(_compile(n) for n in needles), Brand(key, label, color, _FALLBACKS.get(key), name))
    for needles, key, label, name, color in _RULES
)

#: Todas as marcas do catálogo, na ordem das regras
BRANDS: tuple[Brand, ...] = tuple(b for _tests, b in _COMPILED)
BRAND_KEYS: tuple[str, ...] = tuple(b.key for b in BRANDS)


def brand_for(*texts: Optional[str]) -> Optional[Brand]:
    """Marca encontrada em qualquer um dos textos; None se não reconhecida (não chuta)."""
    blob = " ".join(t for t in texts if t).upper()
    if not blob:
        return None
    for tests, brand in _COMPILED:
        if any(t(blob) for t in tests):
            return brand
    return None


def brand_by_key(key: str) -> Optional[Brand]:
    return next((b for b in BRANDS if b.key == key), None)


#: Classes de marca ÚNICA no Le Mans Ultimate (regulamento do WEC): o texto do veículo pode citar só a equipe
#: ("Vector Sport #10"), mas todo LMP2 é Oreca 07. Usado só quando nada no texto do carro foi reconhecido.
LMU_SINGLE_MAKE = {"LMP2": "oreca"}


def brand_for_lmu_class(class_name: Optional[str]) -> Optional[Brand]:
    name = (class_name or "").upper()
    for cls, key in LMU_SINGLE_MAKE.items():
        if name.startswith(cls):
            return brand_by_key(key)
    return None


# --------------------------------------------------------------------------- #
# Regras do USUÁRIO (`brand_overrides.json` na pasta de configuração), aplicadas ANTES das regras embutidas.
# No LMU o nome do carro é "Equipe #N:livery" e NÃO cita a fabricante, então a marca de cada equipe/classe
# precisa ser dita uma vez. Formato: [{"match": "DKR Engineering", "class": "LMP3", "brand": "adess"}, ...]
# (`class` é opcional; `match` é um trecho do texto do veículo ou da equipe, sem diferenciar maiúsculas).
_OVERRIDES: list[tuple[str, str, str]] = []  # (match, class, brand_key) já normalizados
OVERRIDES_TEMPLATE = {
    "_ajuda": "Cada regra liga uma equipe/veículo a uma marca. 'match' = trecho do texto do veículo (veja 'Logos que "
              "faltam...' ou o diagnóstico); 'class' (opcional) = começo do nome da classe; 'brand' = chave da marca "
              "(ex.: adess, ligier, duqueine, lamborghini, mclaren, ford...). Depois use 'Recarregar logos'.",
    "rules": [],
}


def set_overrides(rules) -> int:
    """Troca as regras do usuário; entradas inválidas ou com marca desconhecida são ignoradas. Devolve quantas valem."""
    out: list[tuple[str, str, str]] = []
    for r in rules or []:
        if not isinstance(r, dict):
            continue
        match, key = str(r.get("match") or "").strip().upper(), str(r.get("brand") or "").strip().lower()
        if match and brand_by_key(key) is not None:
            out.append((match, str(r.get("class") or "").strip().upper(), key))
    _OVERRIDES[:] = out
    return len(out)


def load_overrides_file(path) -> int:
    """Lê `brand_overrides.json` (cria o modelo se não existir). Erros de leitura não derrubam o app."""
    import json
    from pathlib import Path
    p = Path(path)
    try:
        if not p.exists():
            p.write_text(json.dumps(OVERRIDES_TEMPLATE, indent=2, ensure_ascii=False), encoding="utf-8")
        data = json.loads(p.read_text(encoding="utf-8"))
        return set_overrides(data.get("rules") if isinstance(data, dict) else data)
    except (OSError, ValueError):
        return set_overrides([])


def brand_for_car(car_model, vehicle_raw, team_name=None, class_name=None, sim=None) -> Optional[Brand]:
    """Marca do carro: regras do usuário > texto do veículo > classe de marca única do LMU. Nunca chuta."""
    blob = " ".join(t for t in (vehicle_raw, team_name) if t).upper()
    cls = (class_name or "").upper()
    for match, ocls, key in _OVERRIDES:
        if match in blob and (not ocls or cls.startswith(ocls)):
            return brand_by_key(key)
    found = brand_for(car_model, vehicle_raw)
    if found is None and str(getattr(sim, "value", sim) or "") == "lmu":
        found = brand_for_lmu_class(class_name)
    return found
