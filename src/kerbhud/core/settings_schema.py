"""Configurações editáveis na janela de Configurações: esquema, validação e aplicação (sem Qt, testável).

A interface só monta os campos e entrega um "patch" (dict aninhado); aqui se valida tudo antes de gravar em
`settings.json`. Valores inválidos viram mensagens de erro e NÃO são gravados; chaves desconhecidas são ignoradas.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from . import visibility
from .flags import country_code
from .updater import valid_repo
from .winapi import parse_hotkey

SIMULATORS = ("auto", "iracing", "lmu", "demo")
SIMULATOR_LABELS = {"auto": "Automático (detecta o jogo aberto)", "iracing": "iRacing", "lmu": "Le Mans Ultimate",
                    "demo": "DEMO (dados de teste)"}
UPDATE_HZ_CHOICES = (30, 60, 120)
UI_HZ_CHOICES = (20, 30, 45, 60)
UNITS = ("kmh", "mph")
UNIT_LABELS = {"kmh": "km/h", "mph": "mph"}
CONTACT_BADGES = ("Rookie", "Good", "Trusted", "Warning", "Probation", "Creator", "Driver", "Staff")
_RANK = re.compile(r"^[BSGP][1-9]$")  # bronze/prata/ouro/platina + nível (ex.: B2, S3)

#: ação -> rótulo (a ordem é a da janela). `layout_N` troca para o N-ésimo layout da lista.
HOTKEY_LABELS = {
    "toggle_edit": "Modo de edição",
    "toggle_overlay": "Mostrar / esconder o overlay",
    "next_layout": "Próximo layout",
    "prev_layout": "Layout anterior",
    "layout_1": "Layout 1", "layout_2": "Layout 2", "layout_3": "Layout 3", "layout_4": "Layout 4",
    "demo_next_stage": "DEMO: pular para a próxima etapa",
}
DEFAULT_HOTKEYS = {
    "toggle_edit": "Ctrl+Alt+E", "toggle_overlay": "Ctrl+Alt+H",
    "next_layout": "Ctrl+Alt+Right", "prev_layout": "Ctrl+Alt+Left",
    "layout_1": "Ctrl+Alt+1", "layout_2": "Ctrl+Alt+2", "layout_3": "Ctrl+Alt+3", "layout_4": "Ctrl+Alt+4",
    "demo_next_stage": "Ctrl+Alt+N",
}

_MOD_NAMES = {"CTRL": "Ctrl", "CONTROL": "Ctrl", "ALT": "Alt", "SHIFT": "Shift", "WIN": "Win", "META": "Win"}
_MOD_ORDER = ("Ctrl", "Alt", "Shift", "Win")


def normalize_hotkey(text: str) -> str:
    """"ctrl + alt + e" -> "Ctrl+Alt+E". Levanta ValueError se o atalho for inválido."""
    parse_hotkey(text)  # valida (modificador + tecla conhecida)
    parts = [p.strip() for p in text.split("+") if p.strip()]
    mods = sorted({_MOD_NAMES[p.upper()] for p in parts[:-1]}, key=_MOD_ORDER.index)
    key = parts[-1]
    key = key.upper() if (len(key) == 1 or (key[:1].upper() == "F" and key[1:].isdigit())) else key.capitalize()
    return "+".join([*mods, key])


def _choice(value, allowed, label: str, errors: list[str], cast=None):
    try:
        v = cast(value) if cast else value
    except (TypeError, ValueError):
        errors.append(f"{label}: valor inválido ({value!r})")
        return None
    if v not in allowed:
        errors.append(f"{label}: use um destes: {', '.join(map(str, allowed))}")
        return None
    return v


def validate_patch(patch: dict, current: Optional[dict] = None) -> tuple[dict, list[str]]:
    """Valida um patch (chaves como em settings.json). Devolve (patch limpo, erros)."""
    errors: list[str] = []
    out: dict[str, Any] = {}
    cur = current or {}

    if "simulator" in patch:
        v = _choice(patch["simulator"], SIMULATORS, "Simulador", errors)
        if v is not None:
            out["simulator"] = v
    if "visibility" in patch:
        v = _choice(patch["visibility"], visibility.MODES, "Mostrar o overlay", errors)
        if v is not None:
            out["visibility"] = v
    if "update_hz" in patch:
        v = _choice(patch["update_hz"], UPDATE_HZ_CHOICES, "Leitura do jogo (Hz)", errors, int)
        if v is not None:
            out["update_hz"] = v
    if "ui_hz" in patch:
        v = _choice(patch["ui_hz"], UI_HZ_CHOICES, "Atualização da tela (Hz)", errors, int)
        if v is not None:
            out["ui_hz"] = v
    if "units" in patch:
        v = _choice(patch["units"], UNITS, "Unidade de velocidade", errors)
        if v is not None:
            out["units"] = v
    if "logo_wordmark" in patch:
        out["logo_wordmark"] = bool(patch["logo_wordmark"])
    if "my_country" in patch:
        raw = patch["my_country"]
        if raw in (None, "") or not str(raw).strip():
            out["my_country"] = None
        elif (code := country_code(raw)) is not None:
            out["my_country"] = code
        else:
            errors.append(f"País: {raw!r} não reconhecido (use o código, ex.: br, gb, us, ou o nome em inglês)")

    if "language" in patch:
        v = _choice(patch["language"], ("auto", "pt-BR", "en"), "Idioma", errors)
        if v is not None:
            out["language"] = v
    if "check_updates_on_start" in patch:
        out["check_updates_on_start"] = bool(patch["check_updates_on_start"])
    if "update_repo" in patch:
        raw = str(patch["update_repo"] or "").strip()
        raw = re.sub(r"^https?://github\.com/", "", raw).strip("/")
        raw = raw[:-4] if raw.endswith(".git") else raw
        if not raw:
            out["update_repo"] = ""
        elif valid_repo(raw):
            out["update_repo"] = raw
        else:
            errors.append("Repositório de atualização: use usuario/repositorio (ex.: alex/KerbHUD)")

    if isinstance(patch.get("iracing"), dict) and "invert_clutch" in patch["iracing"]:
        out["iracing"] = {"invert_clutch": bool(patch["iracing"]["invert_clutch"])}

    if isinstance(patch.get("lmu"), dict):
        lmu: dict[str, Any] = {}
        for key, label in (("driver_rank", "Driver Rank"), ("safety_rank", "Safety Rank")):
            if key in patch["lmu"]:
                raw = patch["lmu"][key]
                if raw in (None, "") or not str(raw).strip():
                    lmu[key] = None
                elif _RANK.match(str(raw).strip().upper()):
                    lmu[key] = str(raw).strip().upper()
                else:
                    errors.append(f"{label}: use letra (B, S, G ou P) + número, ex.: B2, S3, G1, P2")
        if "contact_badge" in patch["lmu"]:
            raw = patch["lmu"]["contact_badge"]
            if raw in (None, "") or not str(raw).strip():
                lmu["contact_badge"] = None
            else:
                found = next((b for b in CONTACT_BADGES if b.lower() == str(raw).strip().lower()), None)
                if found:
                    lmu["contact_badge"] = found
                else:
                    errors.append(f"Badge: use um destes: {', '.join(CONTACT_BADGES)}")
        if lmu:
            out["lmu"] = lmu

    if isinstance(patch.get("hotkeys"), dict):
        hk: dict[str, str] = {}
        for action, text in patch["hotkeys"].items():
            if action not in HOTKEY_LABELS:
                continue
            if not text or not str(text).strip():
                hk[action] = ""  # desligado
                continue
            try:
                hk[action] = normalize_hotkey(str(text))
            except ValueError as exc:
                errors.append(f"Atalho '{HOTKEY_LABELS[action]}': {exc}")
        merged = {**{k: v for k, v in (cur.get("hotkeys") or {}).items() if k in HOTKEY_LABELS}, **hk}
        seen: dict[str, str] = {}
        for action, text in merged.items():
            if not text:
                continue
            key = text.lower()
            if key in seen:
                errors.append(f"Atalho repetido: {text} ({HOTKEY_LABELS[seen[key]]} e {HOTKEY_LABELS[action]})")
            seen[key] = action
        if hk:
            out["hotkeys"] = hk
    return out, errors


def apply_patch(settings: dict, clean: dict) -> set[str]:
    """Aplica o patch JÁ VALIDADO em `settings`, no mesmo objeto (os provedores guardam referências a sub-dicts).
    Devolve as chaves de primeiro nível que mudaram de fato."""
    changed: set[str] = set()
    for key, value in clean.items():
        if isinstance(value, dict):
            sub = settings.setdefault(key, {})
            for k, v in value.items():
                if sub.get(k) != v:
                    sub[k] = v
                    changed.add(key)
        elif settings.get(key) != value:
            settings[key] = value
            changed.add(key)
    return changed


def settings_to_patch(settings: dict) -> dict:
    """Os campos que a janela edita, lidos do dicionário de settings (valores iniciais da janela)."""
    return {
        "simulator": settings.get("simulator", "auto"), "visibility": settings.get("visibility", "always"),
        "update_hz": settings.get("update_hz", 60), "ui_hz": settings.get("ui_hz", 30),
        "units": settings.get("units", "kmh"), "logo_wordmark": bool(settings.get("logo_wordmark", True)),
        "my_country": settings.get("my_country") or "",
        "language": settings.get("language", "auto"),
        "update_repo": settings.get("update_repo") or "", "check_updates_on_start": bool(settings.get("check_updates_on_start", True)),
        "iracing": {"invert_clutch": bool((settings.get("iracing") or {}).get("invert_clutch", True))},
        "lmu": {k: (settings.get("lmu") or {}).get(k) or "" for k in ("driver_rank", "safety_rank", "contact_badge")},
        "hotkeys": {**DEFAULT_HOTKEYS, **(settings.get("hotkeys") or {})},
    }
