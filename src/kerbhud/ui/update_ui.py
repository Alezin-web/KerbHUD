"""Atualização pela interface: verifica, mostra as novidades, baixa, aplica e reinicia (a lógica está em core/updater)."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox, QSystemTrayIcon

from .. import __version__
from ..core.changelog import plain_release_notes
from ..core.i18n import get_language, tr
from ..core import updater
from ..core.updatenotice import RECHECK_HOURS, UpdateNotice
from ..core.paths import app_root


class UpdateController:
    def __init__(self, tray, settings: dict, quit_app: Callable[[], None], save_setting: Callable[[str, object], None]):
        self.tray, self.settings, self._quit, self._save = tray, settings, quit_app, save_setting
        self._busy = False
        self._box: dict = {}
        self.available: Optional[updater.ReleaseInfo] = None  # versão nova já encontrada
        self.state = "idle"  # idle | checking | available | uptodate | error | installing
        self.message = ""
        self.listeners: list[Callable[[], None]] = []
        self.notice = UpdateNotice(settings.get("update_dismissed", ""))
        self._timer: Optional[QTimer] = None

    def start_periodic(self) -> None:
        """Reconfere a cada poucas horas (o programa fica aberto na bandeja por dias); só avisa, nunca instala."""
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(lambda: self.settings.get("check_updates_on_start", True) and self.check(manual=False))
            self._timer.start(RECHECK_HOURS * 3600 * 1000)

    def banner_visible(self) -> bool:
        info = self.available
        return self.state in ("available", "installing") and self.notice.banner_visible(info.version if info else None)

    def dismiss(self) -> None:
        """"Agora não": esconde a faixa para ESTA versão (uma versão mais nova avisa de novo)."""
        if self.available is not None:
            self.notice.dismiss(self.available.version)
            self.settings["update_dismissed"] = self.available.version
            self._save("update_dismissed", self.available.version)
        for cb in list(self.listeners):
            cb()

    def _set(self, state: str, message: str = "") -> None:
        self.state, self.message = state, message
        for cb in list(self.listeners):
            cb()

    # ---- verificar ----------------------------------------------------- #
    def check(self, manual: bool = True) -> None:
        repo = updater.effective_repo(self.settings)
        if self._busy:
            return
        if self.available is not None and manual:  # já sabemos que há versão nova: vai direto para a oferta
            self._offer(self.available)
            return
        if not updater.valid_repo(repo):
            self._set("error", tr("Repositório não configurado (Config → Configurações → Atualização)"))
            if manual:
                QMessageBox.information(
                    None, tr("Atualização"),
                    tr("Informe o repositório do GitHub em Config → Configurações → Atualização (formato usuario/repositorio)."))
            return
        self._busy = True
        self._box = {}
        self._set("checking", tr("Verificando..."))

        def work() -> None:
            try:
                self._box["info"] = updater.check_latest(repo, __version__)
                self._box["done"] = True
            except updater.UpdateError as exc:
                self._box["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - nada pode derrubar o overlay
                self._box["error"] = f"erro inesperado: {exc}"

        threading.Thread(target=work, name="kerbhud-update-check", daemon=True).start()
        self._poll_check(manual)

    def _poll_check(self, manual: bool) -> None:
        if "done" not in self._box and "error" not in self._box:
            QTimer.singleShot(300, lambda: self._poll_check(manual))
            return
        self._busy = False
        if "error" in self._box:
            self._set("error", tr(self._box["error"]))
            if manual:
                QMessageBox.warning(None, tr("Atualização"), tr(self._box["error"]))
            return
        info = self._box.get("info")
        self.available = info
        if info is None:
            self._set("uptodate", tr("Você está na versão mais recente ({})").format(__version__))
            if manual:
                QMessageBox.information(None, tr("Atualização"), tr("Você já está na versão mais recente ({}).").format(__version__))
            return
        self._set("available", tr("Nova versão {} disponível").format(info.version))
        if not manual:  # checagem automática: só avisa (balão uma vez por versão + faixa na janela), a pessoa decide
            if self.notice.should_balloon(info.version):
                self.tray.tray.showMessage(tr("KerbHUD"), tr("Nova versão {} disponível. Abra a janela do KerbHUD (ou o menu da bandeja) para atualizar.").format(info.version), QSystemTrayIcon.Information, 10000)
            return
        self._offer(info)

    # ---- baixar e aplicar ---------------------------------------------- #
    def _offer(self, info: updater.ReleaseInfo) -> None:
        notes = (plain_release_notes(info.notes, get_language()) or tr("(sem notas)"))[:1500]
        ok = QMessageBox.question(
            None, tr("Nova versão disponível"),
            tr("Você está na {cur}. Disponível: {new}.\n\n{notes}\n\n"
               "Baixar e instalar agora? Suas pastas de dados (logos, bandeiras, layouts...) não são tocadas.").format(
                cur=__version__, new=info.version, notes=notes))
        if ok == QMessageBox.Yes:
            self._install(info)

    def _install(self, info: updater.ReleaseInfo) -> None:
        root = app_root()
        frozen = bool(getattr(sys, "frozen", False))
        if not os.access(root, os.W_OK):
            QMessageBox.warning(None, tr("Atualização"), tr("Sem permissão para gravar em {}. Mova o KerbHUD para uma "
                                   "pasta sua (ex.: Documentos) e tente de novo.").format(root))
            return
        self._busy = True
        self._box = {}
        self._set("installing", tr("Baixando a versão {}...").format(info.version))
        work_dir = root / "_update"

        def work() -> None:
            try:
                new = updater.download_and_prepare(info, work_dir, progress=lambda g, t: self._box.__setitem__("got", (g, t)))
                if not frozen:
                    self._box["changed"] = updater.apply_source_update(new, root, info.version)
                else:
                    self._box["new_dir"] = new
                self._box["done"] = True
            except updater.UpdateError as exc:
                self._box["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001
                self._box["error"] = f"erro inesperado: {exc}"

        threading.Thread(target=work, name="kerbhud-update", daemon=True).start()
        self.tray.tray.showMessage(tr("KerbHUD"), tr("Baixando a versão {}...").format(info.version), QSystemTrayIcon.Information, 4000)
        self._poll_install(info, frozen, root)

    def _poll_install(self, info, frozen: bool, root: Path) -> None:
        if "done" not in self._box and "error" not in self._box:
            QTimer.singleShot(400, lambda: self._poll_install(info, frozen, root))
            return
        self._busy = False
        if "error" in self._box:
            self._set("available", tr("Nova versão {} disponível").format(info.version))
            QMessageBox.warning(None, tr("Atualização"), tr("Não foi possível atualizar: {}").format(tr(self._box["error"])) + (
                                "\n" + tr("Nada foi alterado no seu KerbHUD.") if frozen else ""))
            return
        self._set("installing", tr("Versão {} instalada. Reinicie para usar.").format(info.version))
        if QMessageBox.question(None, tr("Atualização pronta"),
                                tr("Versão {} instalada. Reiniciar o KerbHUD agora?").format(info.version)) == QMessageBox.Yes:
            self._restart(frozen, root)

    def _restart(self, frozen: bool, root: Path) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            if frozen:
                bat = updater.write_swap_script(Path(self._box["new_dir"]), root, Path(sys.executable).name, os.getpid())
                subprocess.Popen(["cmd", "/c", str(bat)], creationflags=flags, close_fds=True)
            else:
                env = dict(os.environ, PYTHONPATH=str(root / "src"))
                subprocess.Popen([sys.executable, "-m", "kerbhud", "run"], cwd=str(root), env=env,
                                 creationflags=flags, close_fds=True)
        except OSError as exc:
            QMessageBox.warning(None, tr("Reiniciar"), tr("Não consegui reiniciar sozinho ({}). Feche e abra o KerbHUD.").format(exc))
            return
        self._quit()
