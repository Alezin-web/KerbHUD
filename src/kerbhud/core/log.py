"""Arquivo de log do KerbHUD (sem Qt, testável).

Antes não existia log nenhum: um erro numa thread simplesmente parava o overlay e ninguém sabia por quê. Agora os erros
vão para `kerbhud.log` na pasta de configurações (rotaciona em ~256 KB, guarda 1 cópia antiga). Nada de dados de
telemetria é gravado: só mensagens de erro e o rastreio da falha.
"""
from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from . import paths

LOGGER_NAME = "kerbhud"
LOG_NAME = "kerbhud.log"
_configured = False
logging.getLogger(LOGGER_NAME).addHandler(logging.NullHandler())  # sem log em arquivo (testes, linha de comando): silêncio


def log_path() -> Path:
    return paths.config_dir() / LOG_NAME


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def setup_logging(path: Optional[Path] = None) -> logging.Logger:
    """Liga o log em arquivo. Se não der para gravar (pasta protegida), segue sem log em vez de falhar."""
    global _configured
    logger = get_logger()
    if _configured:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        target = Path(path) if path else log_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(target, maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    except OSError:
        logger.addHandler(logging.NullHandler())
    _configured = True
    return logger


def install_excepthooks() -> None:
    """Erros que escapariam (thread principal ou outras threads) vão para o log em vez de sumir."""
    log = get_logger()
    previous = sys.excepthook
    limiter = RepeatLimiter()  # um erro dentro do desenho da tela se repete 30 vezes por segundo: não encher o log

    def key_of(exc_type, tb) -> str:
        last = tb
        while last is not None and last.tb_next is not None:
            last = last.tb_next
        where = f"{last.tb_frame.f_code.co_filename}:{last.tb_lineno}" if last is not None else ""
        return f"{getattr(exc_type, '__name__', exc_type)}@{where}"

    def hook(exc_type, exc, tb):
        if limiter.should_log(key_of(exc_type, tb)):
            log.error("Erro não tratado", exc_info=(exc_type, exc, tb))
        previous(exc_type, exc, tb)

    def thread_hook(args):
        if limiter.should_log(key_of(args.exc_type, args.exc_traceback)):
            log.error("Erro não tratado na thread %s", getattr(args.thread, "name", "?"),
                      exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = hook
    threading.excepthook = thread_hook


class RepeatLimiter:
    """Evita encher o log com o mesmo erro 60 vezes por segundo: registra o 1º e depois a cada `every` repetições."""

    def __init__(self, every: int = 300) -> None:
        self.every = every
        self._count: dict[str, int] = {}

    def should_log(self, key: str) -> bool:
        n = self._count.get(key, 0) + 1
        self._count[key] = n
        return n == 1 or n % self.every == 0

    def clear(self, key: Optional[str] = None) -> None:
        if key is None:
            self._count.clear()
        else:
            self._count.pop(key, None)
