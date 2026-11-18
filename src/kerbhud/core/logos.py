"""Download dos logotipos de marcas para a pasta `logos/` (executado por ação do usuário).

Fonte: o repositório público `filippofilip95/car-logos-dataset` (PNGs transparentes otimizados e um
índice `data.json`). O código do repositório é MIT; os logotipos são marcas dos respectivos
fabricantes e aqui servem apenas para identificar o carro no overlay do próprio usuário.

Esse repositório foi coletado de um site de logos de carros de RUA: marcas de construtores de corrida (Ray, Radical,
Skip Barber, Riley...) podem não existir nele. O que não for encontrado aparece em `missing` e em
`python -m kerbhud logos-status`; para essas marcas, coloque você mesmo `<chave>.png` na pasta de logos
(também vale `.webp`, `.jpg` e `.svg`). Arquivos que já existem NUNCA são sobrescritos, a menos que se peça.

Nada é baixado sem o usuário pedir, e nada é enviado: só leitura de arquivos públicos (HTTP GET).
`fetch` é injetável para testes sem rede.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .brands import BRAND_KEYS, BRANDS, brand_by_key

BASE = "https://raw.githubusercontent.com/filippofilip95/car-logos-dataset/master/logos"
INDEX_URL = f"{BASE}/data.json"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

SUPPORTED_EXT = ("png", "webp", "jpg", "jpeg", "svg")  # formatos aceitos na pasta de logos (ordem de preferência)

# chave do overlay -> nomes/slugs possíveis no índice (comparação sem acentos/traços/maiúsculas).
# Tupla vazia = marca que NÃO costuma estar nesse repositório (construtores de corrida): vai direto para "faltando".
CANDIDATES: dict[str, tuple[str, ...]] = {
    "acura": ("acura",), "alpine": ("alpine",), "astonmartin": ("aston-martin",), "audi": ("audi",), "bmw": ("bmw",),
    "buick": ("buick",), "cadillac": ("cadillac",), "chevrolet": ("chevrolet",),
    "corvette": ("corvette", "chevrolet-corvette"), "dallara": ("dallara",), "dodge": ("dodge",),
    "duqueine": ("duqueine",), "ferrari": ("ferrari",), "ford": ("ford",), "genesis": ("genesis",),
    "ginetta": ("ginetta",), "glickenhaus": ("scg", "glickenhaus"), "holden": ("holden",), "honda": ("honda",),
    "hyundai": ("hyundai",), "isotta": ("isotta-fraschini",), "kia": ("kia",), "lamborghini": ("lamborghini",),
    "lexus": ("lexus",), "ligier": ("ligier",), "lotus": ("lotus",), "mazda": ("mazda",), "mclaren": ("mclaren",),
    "mercedes": ("mercedes-benz", "mercedes", "mercedes-amg"), "nissan": ("nissan",), "oreca": ("oreca",),
    "peugeot": ("peugeot",), "pontiac": ("pontiac",), "porsche": ("porsche",), "radical": ("radical",),
    "ram": ("ram", "ram-trucks"), "adess": (), "ray": (), "renault": ("renault",), "riley": ("riley",), "ruf": ("ruf",),
    "sabre": (), "sheane": (), "skipbarber": (), "subaru": ("subaru",), "toyota": ("toyota",),
    "vanwall": ("vanwall",), "volkswagen": ("volkswagen",), "williams": ("williams",),
}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


@dataclass
class LogoResult:
    downloaded: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)  # marcas que não existem no índice
    errors: list[str] = field(default_factory=list)  # falhas de rede/arquivo inválido
    fatal: str = ""  # índice inacessível: nada foi tentado

    @property
    def summary(self) -> str:
        if self.fatal:
            return self.fatal
        parts = [f"{len(self.downloaded)} logos baixados"]
        if self.missing:
            names = ", ".join(sorted(brand_name(k) for k in self.missing))
            parts.append(f"{len(self.missing)} marcas sem logo no repositório ({names}): coloque você mesmo o arquivo "
                         f"<chave>.png na pasta de logos (ver 'Logos que faltam')")
        if self.errors:
            parts.append(f"{len(self.errors)} falhas")
        return "; ".join(parts)


def brand_name(key: str) -> str:
    b = brand_by_key(key)
    return b.display_name if b else key


def logo_file(directory: Path, key: str) -> Optional[Path]:
    """Arquivo de logo da marca na pasta (a 1ª extensão suportada que existir), ou None."""
    d = Path(directory)
    for ext in SUPPORTED_EXT:
        p = d / f"{key}.{ext}"
        if p.is_file():
            return p
    return None


@dataclass(frozen=True)
class LogoStatus:
    key: str
    name: str
    path: Optional[Path]  # arquivo presente na pasta (None = falta)
    in_dataset: bool  # a marca tem alguma chance de existir no repositório de download


def logos_status(directory: Path) -> list[LogoStatus]:
    """Situação de TODAS as marcas do catálogo (instalada ou faltando) na pasta de logos."""
    return [LogoStatus(b.key, b.display_name, logo_file(directory, b.key), bool(CANDIDATES.get(b.key)))
            for b in BRANDS]


def http_fetch(url: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "KerbHUD-logo-fetch"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (URL fixa, https)
        return resp.read()


def _index(raw: bytes) -> dict[str, str]:
    """{nome normalizado: URL do PNG otimizado}, aceitando entradas com ou sem URL explícita."""
    data = json.loads(raw.decode("utf-8"))
    entries = data if isinstance(data, list) else data.get("logos", [])
    out: dict[str, str] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        slug = str(e.get("slug") or "")
        url = ""
        img = e.get("image")
        if isinstance(img, dict):
            url = str(img.get("optimized") or "")
        if not url.startswith("https://") and slug:  # sem URL (ou URL insegura): usa o caminho padrão HTTPS
            url = f"{BASE}/optimized/{slug}.png"
        if not url.startswith("https://"):
            continue
        for name in (slug, str(e.get("name") or "")):
            if name:
                out.setdefault(_norm(name), url)
    return out


def fetch_logos(dest: Path, fetch: Callable[[str], bytes] = http_fetch,
                keys: Optional[list[str]] = None, overwrite: bool = False) -> LogoResult:
    res = LogoResult()
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        index = _index(fetch(INDEX_URL))
    except Exception as exc:  # noqa: BLE001 - qualquer falha aqui significa "sem índice"
        res.fatal = f"Não foi possível acessar a lista de logos ({exc.__class__.__name__}). Verifique a internet."
        return res
    for key in (keys or list(BRAND_KEYS)):
        target = dest / f"{key}.png"
        if logo_file(dest, key) is not None and not overwrite:
            continue  # já existe (baixado antes ou colocado por você, em qualquer formato): não sobrescreve
        url = next((index[_norm(c)] for c in CANDIDATES.get(key, (key,)) if _norm(c) in index), None)
        if url is None:
            res.missing.append(key)
            continue
        try:
            data = fetch(url)
            if not data.startswith(PNG_SIGNATURE):
                raise ValueError("arquivo não é PNG")
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, target)
            res.downloaded.append(key)
        except Exception as exc:  # noqa: BLE001
            res.errors.append(f"{key}: {exc}")
    return res


def installed_logos(directory: Path) -> list[str]:
    """Chaves das marcas que têm arquivo de logo na pasta (qualquer formato suportado)."""
    d = Path(directory)
    if not d.is_dir():
        return []
    return sorted({p.stem for p in d.iterdir() if p.suffix.lower().lstrip(".") in SUPPORTED_EXT})
