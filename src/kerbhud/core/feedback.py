"""Sugestões de melhoria. Principal: formulário dentro do KerbHUD que envia ao Google Forms do projeto (sem conta para
quem envia; só o texto digitado, o simulador, a versão do KerbHUD e o contato se a pessoa quiser, e só depois de ela
ver e confirmar). Alternativa: abrir a página de "Nova issue" no GitHub (precisa de conta), sem enviar nada."""
from __future__ import annotations

import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional
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


# ---- envio da sugestão pela própria interface (Google Forms, sem conta para quem envia) ---------------------- #
FORM_ID = "1FAIpQLSdicGLYXbUHBrA-t5HSX5SqmAFD-w4eX1g-ponrVckB4vbjag"
FORM_URL = f"https://docs.google.com/forms/d/e/{FORM_ID}/formResponse"
ALLOWED_HOST = "docs.google.com"
#: campo do formulário -> código "entry.N" (veja o link pré-preenchido do Google Forms)
FIELDS = {"idea": "entry.639367796", "why": "entry.201888621", "simulator": "entry.1443931871",
          "version": "entry.1972130337", "contact": "entry.280291273"}
LIMITS = {"idea": 2000, "why": 2000, "simulator": 40, "version": 20, "contact": 200}
MIN_IDEA = 10
COOLDOWN_S = 60
SIMULATORS = ("iRacing", "Le Mans Ultimate", "Outro / ambos")

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class FeedbackError(Exception):
    """Falha esperada no envio: a mensagem é para a pessoa."""


def clean_text(text: object, limit: int) -> str:
    """Texto sem caracteres de controle, sem espaços nas pontas e no máximo `limit` caracteres."""
    return _CONTROL.sub("", str(text or "")).replace("\r\n", "\n").strip()[:limit]


def build_submission(idea: str, why: str = "", simulator: str = "", contact: str = "", version: str = "") -> dict[str, str]:
    """Os campos exatos que serão enviados (e mostrados à pessoa antes). Levanta FeedbackError se a ideia for curta."""
    data = {k: clean_text(v, LIMITS[k]) for k, v in
            (("idea", idea), ("why", why), ("simulator", simulator), ("version", version), ("contact", contact))}
    if len(data["idea"]) < MIN_IDEA:
        raise FeedbackError(f"Descreva a ideia com pelo menos {MIN_IDEA} caracteres.")
    return data


def encode_form(data: dict[str, str]) -> bytes:
    return urllib.parse.urlencode({FIELDS[k]: v for k, v in data.items() if k in FIELDS}).encode("utf-8")


class Cooldown:
    """Uma sugestão por minuto (evita envio repetido por engano e abuso)."""

    def __init__(self, seconds: float = COOLDOWN_S, clock: Callable[[], float] = time.monotonic):
        self.seconds, self._clock, self._last = seconds, clock, None
        self._lock = threading.Lock()

    def remaining(self) -> float:
        with self._lock:
            return 0.0 if self._last is None else max(0.0, self.seconds - (self._clock() - self._last))

    def mark(self) -> None:
        with self._lock:
            self._last = self._clock()


def submit(data: dict[str, str], version: str = "", opener: Optional[Callable] = None, timeout: float = 15.0) -> None:
    """Envia a sugestão ao formulário. Só HTTPS para docs.google.com; qualquer outra coisa é recusada.
    Levanta FeedbackError (com mensagem para a pessoa) se não der certo."""
    opener = opener or urllib.request.urlopen
    req = urllib.request.Request(
        FORM_URL, data=encode_form(data), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": f"KerbHUD/{version or 'dev'}"})
    try:
        with opener(req, timeout=timeout) as resp:
            final = urllib.parse.urlparse(resp.geturl())
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        raise FeedbackError(f"O servidor recusou o envio (código {exc.code}).") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FeedbackError("Sem conexão com a internet ou o servidor não respondeu. Tente de novo mais tarde.") from exc
    if final.scheme != "https" or final.hostname != ALLOWED_HOST:
        raise FeedbackError("O envio foi redirecionado para um endereço inesperado e foi cancelado.")
    if status != 200 or "formResponse" not in final.path:
        raise FeedbackError("O formulário não aceitou o envio. Tente de novo mais tarde.")
