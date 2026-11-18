"""Idiomas da interface (sem Qt): português do Brasil e inglês.

Os textos do programa são escritos em português; `tr("texto em português")` devolve o inglês quando o idioma é `en`
(e o próprio texto se não houver tradução, então nada some). Textos com valores usam `{}`/`{nome}` e `.format(...)`
depois do `tr`. O idioma é lido ao iniciar: trocar nas Configurações vale depois de reiniciar.
"""
from __future__ import annotations

from typing import Optional

LANGUAGES = {"auto": "Automático / Automatic", "pt-BR": "Português (Brasil)", "en": "English"}
_lang = "pt-BR"
EN: dict[str, str] = {}  # preenchido por core/i18n_en.py (separado para manter este arquivo pequeno)


def resolve_language(setting: Optional[str], system_locale: str = "") -> str:
    """"auto" segue o idioma do Windows (pt* -> português; qualquer outro -> inglês)."""
    if setting in ("pt-BR", "en"):
        return setting
    return "pt-BR" if str(system_locale).lower().startswith("pt") else "en"


def set_language(code: str) -> None:
    global _lang
    _lang = "en" if code == "en" else "pt-BR"
    if _lang == "en" and not EN:
        from .i18n_en import TRANSLATIONS
        EN.update(TRANSLATIONS)


def get_language() -> str:
    return _lang


def tr(text: str) -> str:
    if _lang == "en":
        return EN.get(text, text)
    return text


_MODULE_TITLES_EN = {"standings": "STANDINGS", "relative": "RELATIVE", "inputs": "INPUTS", "telemetry": "TELEMETRY",
                     "trackmap": "TRACK MAP", "fuel": "FUEL", "damage": "CAR DAMAGE", "tires": "TIRES",
                     "spotter": "SPOTTER", "radar": "RADAR", "digflag": "DIGFLAG", "status": "STATUS"}


def module_title(mid: str, pt_title: str) -> str:
    return _MODULE_TITLES_EN.get(mid, pt_title) if _lang == "en" else pt_title
