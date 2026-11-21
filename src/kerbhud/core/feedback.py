"""Sugestões de melhoria: abre a página "Nova issue" do repositório no GitHub (no navegador da pessoa), já com um
modelo de texto. Nada é enviado pelo KerbHUD: quem escreve e envia é a pessoa, com a conta dela no GitHub."""
from __future__ import annotations

from urllib.parse import quote

from .updater import DEFAULT_REPO, valid_repo

_TEMPLATES = {
    "pt": ("Sugestão: ",
           "**O que você gostaria que o KerbHUD fizesse?**\n\n\n"
           "**Por quê? (como isso ajudaria nas suas corridas)**\n\n\n"
           "**Simulador (iRacing / Le Mans Ultimate)**\n\n\n"
           "---\nVersão do KerbHUD: {version}\n"),
    "en": ("Suggestion: ",
           "**What would you like KerbHUD to do?**\n\n\n"
           "**Why? (how would it help your racing)**\n\n\n"
           "**Simulator (iRacing / Le Mans Ultimate)**\n\n\n"
           "---\nKerbHUD version: {version}\n"),
}


def suggestion_url(repo: str, version: str, language: str = "pt") -> str:
    """Endereço (https://github.com/<repo>/issues/new?...) com título e corpo preenchidos; repositório inválido cai no oficial."""
    repo = repo if valid_repo(repo) else DEFAULT_REPO
    title, body = _TEMPLATES.get(language, _TEMPLATES["pt"])
    return (f"https://github.com/{repo}/issues/new?title={quote(title)}"
            f"&body={quote(body.format(version=version))}")
