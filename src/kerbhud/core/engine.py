"""Motor de captura: detecta o simulador, faz polling e mantém o último Snapshot.

Roda em thread própria, separada da interface. A UI só chama `latest()` (leitura
barata, sem bloqueio) ou se inscreve com `subscribe()`.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from ..providers.base import Provider, ProviderDisconnected
from ..providers.demo import DemoProvider
from ..providers.iracing import IRacingProvider
from ..providers.lmu import LmuProvider
from .log import RepeatLimiter, get_logger
from .roster import Roster
from .model import Sim, Snapshot

log = get_logger()
MAX_POLL_ERRORS = 30  # leituras seguidas com erro antes de fechar e reconectar
DEFAULT_SETTINGS = {
    "simulator": "auto",  # auto | iracing | lmu | demo
    "update_hz": 60,
    "visibility": "always",  # always | track | garage (cada módulo pode ter a sua: options.show_when)
    "demo_scenario": "tour",  # cenário do modo DEMO (tour = roteiro completo)
    "units": "kmh",
    "iracing": {"invert_clutch": True, "live_positions": True},
    "lmu": {"driver_rank": None, "safety_rank": None, "contact_badge": None},
    "ui_hz": 30,
    "logo_wordmark": True,  # sem arquivo de logo: mostra o nome da fabricante em texto (false = nada)
    "my_country": None,  # ex.: "br": mostra a SUA bandeira (o LMU não informa o país dos pilotos)
    "show_window_at_startup": True,  # abre a janela principal ao iniciar (false = só o ícone da bandeja)
    "close_to_tray": True,  # fechar a janela principal = minimizar para a bandeja
    "remember_window": True,  # lembra posição e tamanho da janela principal
    "window_geometry": None,  # [x, y, largura, altura]
    "guide_seen": False,  # o guia de uso já foi mostrado (1ª abertura)
    "language": "auto",  # auto (idioma do Windows) | pt-BR | en  (vale ao reiniciar)
    "last_seen_version": None,  # última versão cuja janela de novidades já foi mostrada
    "update_repo": "",  # "usuario/repositorio" do GitHub; vazio = o repositório oficial do KerbHUD (Releases públicos)
    "check_updates_on_start": True,  # só avisa na bandeja; instalar é sempre ação da pessoa
    "driver_flags": {},  # ex.: {"Nome do Piloto": "pt"}: bandeira de pilotos específicos
    "hotkeys": {
        "toggle_edit": "Ctrl+Alt+E",
        "toggle_overlay": "Ctrl+Alt+H",
        "next_layout": "Ctrl+Alt+Right",
        "prev_layout": "Ctrl+Alt+Left",
        "layout_1": "Ctrl+Alt+1",
        "layout_2": "Ctrl+Alt+2",
        "layout_3": "Ctrl+Alt+3",
        "layout_4": "Ctrl+Alt+4",
        "demo_next_stage": "Ctrl+Alt+N",
    },
}


def _clamped_int(value, default: int, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return min(max(n, lo), hi)


def sanitize_settings(cfg: dict) -> dict:
    """Troca por valores padrão o que está com tipo errado (settings.json editado à mão): um valor ruim não pode
    derrubar o programa nem a captura. Chaves desconhecidas são mantidas."""
    d = DEFAULT_SETTINGS
    cfg["update_hz"] = _clamped_int(cfg.get("update_hz"), d["update_hz"], 1, 240)
    cfg["ui_hz"] = _clamped_int(cfg.get("ui_hz"), d["ui_hz"], 1, 120)
    if cfg.get("simulator") not in ("auto", "iracing", "lmu", "demo"):
        cfg["simulator"] = d["simulator"]
    if cfg.get("visibility") not in ("always", "track", "garage"):
        cfg["visibility"] = d["visibility"]
    for key in ("iracing", "lmu", "hotkeys", "driver_flags"):
        if not isinstance(cfg.get(key), dict):
            cfg[key] = json.loads(json.dumps(d[key]))
    for key in ("iracing", "lmu", "hotkeys"):  # chaves que faltam dentro dos grupos voltam ao padrão
        for k, v in d[key].items():
            cfg[key].setdefault(k, v)
    geo = cfg.get("window_geometry")
    if geo is not None and not (isinstance(geo, (list, tuple)) and len(geo) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in geo)):
        cfg["window_geometry"] = None
    return cfg


def load_settings(path: Optional[Path] = None) -> dict:
    """Padrões + o que o usuário salvou. Arquivo ilegível ou corrompido não impede abrir: ele é guardado como
    `settings.json.bad` (para você consultar) e o programa começa com os padrões."""
    cfg = json.loads(json.dumps(DEFAULT_SETTINGS))
    if path and Path(path).exists():
        path = Path(path)
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(user, dict):
                raise ValueError("o arquivo não é um objeto JSON")
        except (OSError, ValueError) as exc:
            log.error("settings.json ilegível (%s): usando os padrões", exc)
            try:
                path.replace(path.with_name(path.name + ".bad"))
            except OSError:
                pass
            return cfg
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return sanitize_settings(cfg)


def write_settings_file(path: Path, data: dict) -> None:
    """Grava o settings.json de forma atômica: escreve num arquivo temporário e troca (queda de luz não corrompe)."""
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def update_settings_file(path: Path, key: str, value) -> None:
    """Altera UMA chave do settings.json do usuário, preservando o resto do arquivo."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        data = {}
    data[key] = value
    write_settings_file(path, data)


def build_providers(settings: dict) -> dict[str, Provider]:
    return {
        "iracing": IRacingProvider(invert_clutch=bool(settings["iracing"].get("invert_clutch", True)),
                                   live_positions=bool(settings["iracing"].get("live_positions", True))),
        "lmu": LmuProvider(manual_ranks=settings["lmu"]),
        "demo": DemoProvider(str(settings.get("demo_scenario", "tour"))),
    }


class Engine:
    def __init__(self, settings: Optional[dict] = None, providers: Optional[dict[str, Provider]] = None):
        self.settings = settings or load_settings()
        self._providers = providers or build_providers(self.settings)
        self._active: Optional[Provider] = None
        self._latest = Snapshot(status_text="Procurando simulador...")
        self._lock = threading.Lock()
        self._subs: list[Callable[[Snapshot], None]] = []
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._reselect = False
        self._limiter = RepeatLimiter()
        self._roster = Roster()  # lembra de quem saiu da sessão (aparece apagado nos módulos)

    # ---- API pública ---------------------------------------------------- #
    def latest(self) -> Snapshot:
        with self._lock:
            return self._latest

    def subscribe(self, cb: Callable[[Snapshot], None]) -> None:
        self._subs.append(cb)

    def set_simulator(self, mode: str) -> None:
        """Troca auto/iracing/lmu/demo em tempo de execução (reconecta)."""
        if mode not in ("auto", "iracing", "lmu", "demo"):
            raise ValueError(mode)
        self.settings["simulator"] = mode
        self._reselect = True

    def set_demo_scenario(self, name: str) -> None:
        """Troca o cenário do modo DEMO (só afeta o provider DEMO)."""
        prov = self._providers.get("demo")
        if hasattr(prov, "set_scenario"):
            prov.set_scenario(name)
            self.settings["demo_scenario"] = name

    def apply_settings(self, changed) -> None:
        """Aplica no que já está rodando as configurações que mudaram (`changed` = chaves de primeiro nível)."""
        if "simulator" in changed:
            self.set_simulator(str(self.settings.get("simulator", "auto")))
        if "iracing" in changed:
            prov = self._providers.get("iracing")
            if prov is not None and hasattr(prov, "_invert_clutch"):
                prov._invert_clutch = bool(self.settings["iracing"].get("invert_clutch", True))
                prov._live_positions = bool(self.settings["iracing"].get("live_positions", True))
        # update_hz é lido a cada reconexão; `lmu` (ranks) é o mesmo dict do provedor, já vale

    def demo_next_stage(self) -> None:
        prov = self._providers.get("demo")
        if hasattr(prov, "next_stage"):
            prov.next_stage()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="kerbhud-engine", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        for p in self._providers.values():
            p.close()

    # ---- interno -------------------------------------------------------- #
    def _candidates(self) -> list[Provider]:
        mode = self.settings.get("simulator", "auto")
        if mode in self._providers:
            return [self._providers[mode]]
        return [self._providers["iracing"], self._providers["lmu"]]

    def _safe_close(self, prov) -> None:
        try:
            prov.close()
        except Exception:  # noqa: BLE001 - fechar nunca pode derrubar a captura
            log.exception("Erro ao fechar o provedor")

    def _publish(self, snap: Snapshot) -> None:
        try:
            snap = self._roster.update(snap)
        except Exception:  # noqa: BLE001 - na pior hipótese, publica sem o histórico de quem saiu
            if self._limiter.should_log("roster"):
                log.exception("Erro ao atualizar a lista de pilotos")
        with self._lock:
            self._latest = snap
        for cb in list(self._subs):
            try:
                cb(snap)
            except Exception:  # um assinante com erro não derruba a captura
                pass

    def _search(self) -> None:
        self._reselect = False  # a escolha atual já vale para esta busca
        for p in self._candidates():
            try:
                connected = p.connect()
            except Exception:  # noqa: BLE001 - um provedor com defeito não pode impedir a busca pelos outros
                if self._limiter.should_log("connect"):
                    log.exception("Erro ao conectar")
                connected = False
            if connected:
                self._active = p
                return
        hints = " | ".join(p.hint() for p in self._candidates() if p.hint())
        self._publish(Snapshot(sim=Sim.NONE, connected=False,
                               status_text="Aguardando simulador. " + hints))

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._active is None:
                self._search()
                if self._active is None:
                    self._stop.wait(1.0)
                continue
            period = 1.0 / _clamped_int(self.settings.get("update_hz"), 60, 1, 240)
            nxt = time.perf_counter()
            errors = 0
            while not self._stop.is_set() and self._active is not None:
                if self._reselect:
                    self._reselect = False
                    self._safe_close(self._active)
                    self._active = None
                    self._publish(Snapshot(status_text="Trocando simulador..."))
                    break
                try:
                    snap = self._active.poll()
                    if snap is not None:
                        self._publish(snap)
                    errors = 0
                except ProviderDisconnected as exc:
                    self._safe_close(self._active)
                    self._active = None
                    self._publish(Snapshot(connected=False, status_text=f"Simulador desconectado ({exc})"))
                    break
                except Exception as exc:  # noqa: BLE001 - qualquer outro erro de leitura: registra e segue
                    errors += 1
                    if self._limiter.should_log("poll"):
                        log.exception("Erro ao ler o simulador (%d seguidos)", errors)
                    if errors >= MAX_POLL_ERRORS:  # não melhora: fecha e reconecta do zero, em vez de travar o overlay
                        self._safe_close(self._active)
                        self._active = None
                        self._publish(Snapshot(connected=False, status_text=f"Erro ao ler o simulador, reconectando ({type(exc).__name__})"))
                        break
                nxt += period
                delay = nxt - time.perf_counter()
                if delay > 0:
                    self._stop.wait(delay)
                else:
                    nxt = time.perf_counter()
