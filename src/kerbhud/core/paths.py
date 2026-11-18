"""Pastas de configuração do usuário (sem dependências de Qt)."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def config_dir() -> Path:
    """`%APPDATA%\\KerbHUD` no Windows; `~/.config/kerbhud` nos demais.

    A variável de ambiente KERBHUD_HOME sobrescreve (útil para testes e para
    versão portátil: coloque a pasta ao lado do .exe).
    """
    override = os.environ.get("KERBHUD_HOME") or os.environ.get("SIMOVERLAY_HOME")  # nome antigo ainda vale
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "KerbHUD"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kerbhud"
    base.mkdir(parents=True, exist_ok=True)
    return base


_OLD_NAME = "SimOverlay"  # nome anterior do programa (até a 0.16): só para migrar o que a pessoa já tinha


def legacy_config_dir() -> Path | None:
    """Pasta de configuração do nome antigo (ou None quando há KERBHUD_HOME / não existe)."""
    if os.environ.get("KERBHUD_HOME") or os.environ.get("SIMOVERLAY_HOME"):
        return None
    if sys.platform == "win32":
        d = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / _OLD_NAME
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / _OLD_NAME.lower()
    return d if d.is_dir() else None


def legacy_app_dirs() -> list[Path]:
    """Pastas do programa com o nome antigo ao lado desta (ex.: `simoverlay-0.16.0`), que tenham dados do usuário."""
    if os.environ.get("KERBHUD_HOME") or os.environ.get("SIMOVERLAY_HOME"):
        return []
    try:
        here = app_root().resolve()
        out = []
        for d in here.parent.iterdir():
            if d.is_dir() and d.resolve() != here and d.name.lower().startswith(_OLD_NAME.lower()):
                inner = [d, d / "simoverlay"] if (d / "simoverlay").is_dir() else [d]
                out.extend(x for x in inner if (x / "dados").is_dir() or any((x / n).is_dir() for n in ("logos", "flags", "badges")))
        return out
    except OSError:
        return []


def migrate_legacy_config() -> list[str]:
    """Copia `settings.json` e `brand_overrides.json` da pasta de configuração do nome antigo, se ainda não existirem."""
    old, copied = legacy_config_dir(), []
    if old is None:
        return copied
    new = config_dir()
    for name in ("settings.json", "brand_overrides.json"):
        src, dst = old / name, new / name
        if src.is_file() and not dst.exists():
            try:
                shutil.copy2(src, dst)
                copied.append(name)
            except OSError:
                pass
    return copied


def app_root() -> Path:
    """Pasta raiz do KerbHUD, onde ficam `logos`, `flags` e `badges` (fáceis de achar e de copiar arquivos).

    No .exe é a pasta do executável; rodando do código, a pasta do projeto (a que tem `src/`). Se a pasta não for
    gravável (ex.: instalado em Arquivos de Programas) ou o código estiver instalado como pacote, cai na pasta de
    configuração. KERBHUD_HOME sempre vence (testes e versão portátil).
    """
    if os.environ.get("KERBHUD_HOME"):
        return config_dir()
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent
    else:
        root = Path(__file__).resolve().parents[3]
        if not (root / "src" / "kerbhud").is_dir():
            return config_dir()
    return root if os.access(root, os.W_OK) else config_dir()


DATA_DIR_NAME = "dados"
ASSET_DIRS = ("logos", "flags", "badges", "layouts", "tracks")


def data_dir() -> Path:
    """Pasta `dados` (dentro da raiz do KerbHUD) que reúne logos, flags, badges, layouts e tracks.

    O atualizador NUNCA mexe nesta pasta: é o que é seu (e o que foi baixado), por isso fica separada do código.
    """
    d = app_root() / DATA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _asset_dir(name: str) -> Path:
    d = data_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _copy_missing(old: Path, new: Path) -> int:
    n = 0
    for f in old.iterdir():
        dest = new / f.name
        if f.is_file() and not dest.exists():
            try:
                shutil.copy2(f, dest)
                n += 1
            except OSError:
                pass
    return n


def migrate_legacy_assets() -> list[str]:
    """Copia (sem apagar nada, sem sobrescrever) o que estava nos lugares antigos para a pasta `dados`.

    Lugares antigos: `%APPDATA%\\KerbHUD\\<pasta>` (até a 0.12), `<raiz>\\<pasta>` (0.13.0), a pasta `dados` de uma cópia
    com o nome antigo (SimOverlay) e a configuração do nome antigo. Devolve um resumo por pasta que recebeu arquivos.
    Idempotente.
    """
    moved: list[str] = []
    target = data_dir().resolve()
    sources = []
    legacy_cfg = legacy_config_dir()
    for base in (config_dir(), app_root(), *([legacy_cfg] if legacy_cfg else []), *legacy_app_dirs()):
        for cand in (base / "dados", base):
            cand = cand.resolve()
            if cand.is_dir() and cand != target and cand not in sources:
                sources.append(cand)
    for name in ASSET_DIRS:
        copied = 0
        for base in sources:
            old = base / name
            if old.is_dir() and old.resolve() != (target / name).resolve():
                copied += _copy_missing(old, _asset_dir(name))
        if copied:
            moved.append(f"{name} ({copied})")
    for base in sources:  # layout ativo
        st = base / "state.json"
        if st.is_file() and not (target / "state.json").exists():
            try:
                shutil.copy2(st, target / "state.json")
            except OSError:
                pass
    return moved


def layouts_dir() -> Path:
    return _asset_dir("layouts")


def logos_dir() -> Path:
    """Pasta onde o usuário pode colocar logotipos de marcas (`bmw.png`, `porsche.png`...)."""
    return _asset_dir("logos")


def badges_dir() -> Path:
    """Ícones de rank do LMU (`trusted.png`, `good.png`, `b2.png`...), colocados pelo usuário."""
    return _asset_dir("badges")


def tracks_dir() -> Path:
    """Traçados de pista gravados pelo Track Map (um .json por pista); apagar a pasta só obriga a regravar."""
    return _asset_dir("tracks")


def flags_dir() -> Path:
    """Pasta das bandeiras de países (`br.png`, `gb-eng.png`...), baixadas pelo usuário."""
    return _asset_dir("flags")
