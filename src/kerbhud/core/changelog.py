"""Changelog (CHANGELOG.md): leitura, "o que há de novo desde a última vez" e conversão segura para HTML (sem Qt).

Formato: cada versão é um `## 0.14.0 — Título`; dentro dela vale um subconjunto de Markdown: `###` títulos, `* ` listas,
`**negrito**`, `` `código` `` e imagens `![texto](arquivo.png)` (somente arquivos da pasta `changelog/`, nada de URL).
"""
from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .updater import parse_version

_HEAD = re.compile(r"^##\s+v?(\d+(?:\.\d+)*)\s*(?:[—–-]+\s*(.*))?$")
_IMG = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
_SAFE_IMG = re.compile(r"^[\w][\w.\-]{0,80}\.(png|jpg|jpeg|gif|webp)$", re.I)


@dataclass
class Entry:
    version: str
    title: str
    body: str


def resource_root() -> Path:
    """Onde estão CHANGELOG.md e `changelog/`: dentro do pacote do .exe, ou na raiz do projeto."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[3]


def parse_changelog(text: str) -> list[Entry]:
    entries: list[Entry] = []
    cur: Optional[Entry] = None
    for line in text.splitlines():
        m = _HEAD.match(line.strip())
        if m:
            cur = Entry(m.group(1), (m.group(2) or "").strip(), "")
            entries.append(cur)
        elif cur is not None:
            cur.body += line + "\n"
    entries.sort(key=lambda e: parse_version(e.version), reverse=True)
    for e in entries:
        e.body = e.body.strip()
    return entries


def load_changelog(root: Optional[Path] = None, language: str = "pt-BR") -> list[Entry]:
    """`CHANGELOG.md` (português) ou `CHANGELOG.en.md` (inglês; se não existir, cai no português)."""
    base = root or resource_root()
    names = ["CHANGELOG.en.md", "CHANGELOG.md"] if language == "en" else ["CHANGELOG.md"]
    for name in names:
        try:
            return parse_changelog((base / name).read_text(encoding="utf-8"))
        except OSError:
            continue
    return []


def entries_to_show(entries: list[Entry], last_seen: Optional[str], current: str) -> list[Entry]:
    """Primeira vez (sem versão vista): só a mais recente. Depois: tudo que é mais novo que a última vista, até a atual."""
    upto = [e for e in entries if parse_version(e.version) <= parse_version(current)]
    if not last_seen:
        return upto[:1]
    try:
        seen = parse_version(last_seen)
    except ValueError:
        return upto[:1]
    return [e for e in upto if parse_version(e.version) > seen]


def _inline(text: str) -> str:
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*([^*\n]+?)\*(?![*\w])", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def md_to_html(md: str, images_dir: Optional[Path] = None) -> str:
    """Converte o subconjunto de Markdown. Imagens só entram se forem arquivos simples existentes em `images_dir`."""
    out: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_list()
            continue
        m = _IMG.fullmatch(line.strip())
        if m:
            close_list()
            alt, name = m.group(1), m.group(2)
            if images_dir is not None and _SAFE_IMG.match(name) and (images_dir / name).is_file():
                out.append(f'<p><img src="{html.escape(name)}" width="480" alt="{html.escape(alt)}"></p>')
            continue  # imagem inválida/ausente: simplesmente não aparece
        if line.startswith("## "):
            close_list()
            out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            close_list()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif re.match(r"^\s*[*-]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(re.sub(r'^\s*[*-]\s+', '', line))}</li>")
        else:
            close_list()
            out.append(f"<p>{_inline(line)}</p>")
    close_list()
    return "\n".join(out)


def entries_to_html(entries: list[Entry], images_dir: Optional[Path] = None) -> str:
    parts = []
    for e in entries:
        head = f"Versão {e.version}" + (f" — {html.escape(e.title)}" if e.title else "")
        parts.append(f"<h2>{head}</h2>\n{md_to_html(e.body, images_dir)}")
    return "\n<hr>\n".join(parts) if parts else "<p>Sem novidades registradas.</p>"


# ---- guia de uso e página com a identidade do KerbHUD ----------------------------------------------------- #
def load_guide(root: Optional[Path] = None, language: str = "pt-BR") -> str:
    """`GUIDE.md` (português) ou `GUIDE.en.md` (inglês; cai no português se faltar)."""
    base = root or resource_root()
    for name in (["GUIDE.en.md", "GUIDE.md"] if language == "en" else ["GUIDE.md"]):
        try:
            return (base / name).read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def hotkeys_md(hotkeys: dict, label_for) -> str:
    """Lista dos atalhos atuais (os que estão ligados), no formato de lista do Markdown restrito."""
    lines = [f"* **{keys}** — {label_for(action)}" for action, keys in hotkeys.items() if keys]
    return "\n".join(lines) if lines else "* —"


def guide_html(md: str, hotkeys_markdown: str, images_dir: Optional[Path] = None) -> str:
    return md_to_html(md.replace("{{HOTKEYS}}", hotkeys_markdown), images_dir)


def _stripe(cells: int = 60) -> str:
    from . import brand
    tds = "".join(f'<td bgcolor="{brand.RED if i % 2 == 0 else brand.WHITE}" height="6"></td>' for i in range(cells))
    return f'<table width="100%" cellspacing="0" cellpadding="0"><tr>{tds}</tr></table>'


PAGE_CSS = (
    "body { background-color: #0b0b0d; color: #f4f4f5; font-size: 10pt; }"
    "h2 { color: #e10600; font-style: italic; margin-top: 14px; }"
    "h3 { color: #f4f4f5; }"
    "li { margin-bottom: 4px; }"
    "code { color: #f5c400; }"
    "b { color: #ffffff; }"
    "hr { color: #2a2a31; }"
)


def branded_page(inner_html: str, tagline: str, images_dir: Optional[Path] = None) -> str:
    """Cabeçalho com o logo + KERB(branco)HUD(vermelho) e a zebra, seguido do conteúdo. HTML simples (QTextBrowser)."""
    from . import brand
    logo = ""
    if images_dir is not None and (images_dir / "logo.png").is_file():
        logo = '<td width="70"><img src="logo.png" width="56" height="56"></td>'
    head = (f'<table width="100%" cellspacing="0" cellpadding="6"><tr>{logo}<td>'
            f'<span style="font-size:24pt; font-weight:bold; font-style:italic; color:{brand.WHITE};">KERB</span>'
            f'<span style="font-size:24pt; font-weight:bold; font-style:italic; color:{brand.RED};">HUD</span><br>'
            f'<span style="color:{brand.GRAY};">{html.escape(tagline)}</span></td></tr></table>')
    return f"{head}{_stripe()}{inner_html}{_stripe()}"


def release_notes(version: str, repo: str, root: Optional[Path] = None) -> str:
    """Texto do Release no GitHub para `version`: a entrada do changelog em português e em inglês.

    Imagens relativas (ex.: banner-0.17.0.png) viram links para a pasta changelog/ do próprio repositório, na tag.
    Usado pelo workflow de publicação (tools/release_notes.py)."""
    root = root or resource_root()
    base = f"https://raw.githubusercontent.com/{repo}/v{version}/changelog/"

    def fix(body: str) -> str:
        return _IMG.sub(lambda m: f"![{m.group(1)}]({base + m.group(2) if _SAFE_IMG.match(m.group(2)) else m.group(2)})", body)

    parts = []
    for lang, label, download in (
            ("pt-BR", "Português", "**Baixe** `KerbHUD-windows.zip`, extraia e abra `KerbHUD.exe`. Quem já usa: *Ajuda → Verificar atualizações*."),
            ("en", "English", "**Download** `KerbHUD-windows.zip`, extract it and run `KerbHUD.exe`. Existing users: *Help → Check for updates*.")):
        entry = next((e for e in load_changelog(root, lang) if e.version == version), None)
        if entry is None:
            continue
        title = f" — {entry.title}" if entry.title else ""
        parts.append(f"## {label}{title}\n\n{fix(entry.body)}\n\n{download}")
    if not parts:
        raise ValueError(f"versão {version} não está no CHANGELOG")
    return "\n\n---\n\n".join(parts) + "\n"


def plain_release_notes(notes: str, language: str = "pt-BR") -> str:
    """Notas do Release como texto simples para a caixa "Nova versão disponível".

    Se o texto tiver as duas línguas (feito por `release_notes`), fica só a da interface. Tira imagens, a linha de
    download e a marcação de Markdown (**, `, *), e os marcadores de lista viram "•"."""
    sections = [s.strip() for s in re.split(r"\n-{3,}\n", notes or "") if s.strip()]
    want = "## English" if language == "en" else "## Português"
    chosen = next((s for s in sections if s.startswith(want)), sections[0] if sections else "")
    lines = []
    for raw in chosen.splitlines():
        line = raw.strip()
        if _IMG.fullmatch(line) or line.startswith(("**Baixe**", "**Download**")):
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
            for prefix in ("Português — ", "English — ", "Português", "English"):
                if line.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break
        if line[:2] in ("* ", "- "):
            line = "• " + line[2:]
        line = line.replace("**", "").replace("`", "")
        line = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"\1", line)
        lines.append(line)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text
