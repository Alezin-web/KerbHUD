"""Parser tolerante do YAML de sessão do iRacing (sem dependências externas).

O YAML do iRacing não é 100% válido (nomes de equipe com ':' ou '#', listas com
o traço no mesmo recuo da chave pai). Em vez de um parser YAML genérico, usamos
um parser por indentação que divide cada linha apenas no PRIMEIRO ':' e trata
todos os valores como texto. Helpers convertem para int/float quando preciso.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

WANTED_SECTIONS = ("WeekendInfo", "DriverInfo", "SessionInfo")


def _strip_value(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    return v


class _Line:
    __slots__ = ("indent", "is_item", "text")

    def __init__(self, indent: int, is_item: bool, text: str):
        self.indent, self.is_item, self.text = indent, is_item, text


def _tokenize(lines: Iterable[str]) -> list[_Line]:
    out: list[_Line] = []
    for raw in lines:
        if not raw.strip() or raw.startswith(("---", "...")):
            continue
        s = raw.rstrip("\r\n")
        stripped = s.lstrip(" ")
        indent = len(s) - len(stripped)
        if stripped.startswith("- ") or stripped == "-":
            out.append(_Line(indent, True, stripped[2:] if len(stripped) > 1 else ""))
        else:
            out.append(_Line(indent, False, stripped))
    return out


def _parse_block(toks: list[_Line], i: int, indent: int) -> tuple[Any, int]:
    if i >= len(toks):
        return None, i
    if toks[i].is_item and toks[i].indent == indent:
        return _parse_list(toks, i, indent)
    return _parse_dict(toks, i, indent)


def _parse_list(toks: list[_Line], i: int, indent: int) -> tuple[list, int]:
    items: list = []
    while i < len(toks) and toks[i].is_item and toks[i].indent == indent:
        first = toks[i]
        # Reescreve "- chave: valor" como linha de dict com recuo indent+2.
        virtual = [_Line(indent + 2, False, first.text)] if first.text else []
        j = i + 1
        while j < len(toks) and (toks[j].indent > indent):
            virtual.append(toks[j])
            j += 1
        if virtual and ":" in virtual[0].text:
            item, _ = _parse_dict(virtual, 0, indent + 2)
        elif virtual:
            item = _strip_value(virtual[0].text)
        else:
            item = None
        items.append(item)
        i = j
    return items, i


def _parse_dict(toks: list[_Line], i: int, indent: int) -> tuple[dict, int]:
    d: dict[str, Any] = {}
    while i < len(toks):
        t = toks[i]
        if t.indent < indent:
            break
        if t.indent > indent or t.is_item:
            # linha inesperada neste nível: ignora para não travar
            if t.is_item and t.indent == indent:
                break
            i += 1
            continue
        key, sep, val = t.text.partition(":")
        key = key.strip()
        i += 1
        if not sep:
            continue
        val = val.strip()
        if val:
            d[key] = _strip_value(val)
            continue
        # valor vazio: bloco filho (mais recuado) ou lista no mesmo recuo
        if i < len(toks) and toks[i].indent > indent:
            child, i = _parse_block(toks, i, toks[i].indent)
            d[key] = child
        elif i < len(toks) and toks[i].is_item and toks[i].indent == indent:
            child, i = _parse_list(toks, i, indent)
            d[key] = child
        else:
            d[key] = None
    return d, i


def parse_session_yaml(text: str, sections: Iterable[str] = WANTED_SECTIONS) -> dict[str, Any]:
    """Converte o texto do YAML de sessão em dict, lendo só as seções pedidas."""
    wanted = set(sections)
    result: dict[str, Any] = {}
    current: Optional[str] = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if current in wanted and buf:
            toks = _tokenize(buf)
            if toks:
                node, _ = _parse_block(toks, 0, toks[0].indent)
                result[current] = node
        buf = []

    for line in text.splitlines():
        if line and not line[0].isspace() and not line.startswith(("---", "...", "-")) and line.rstrip().endswith(":"):
            flush()
            current = line.rstrip()[:-1]
            continue
        if current is not None:
            buf.append(line)
    flush()
    return result


# ---- helpers de conversão ------------------------------------------------- #
def as_int(v: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def as_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(str(v).strip().split()[0])
    except (TypeError, ValueError, IndexError):
        return default
