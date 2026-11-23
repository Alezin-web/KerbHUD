"""Janela "Sugerir melhoria": a pessoa escreve, vê exatamente o que será enviado e confirma. O envio vai para o
formulário do projeto (sem conta) em uma thread, sem travar o overlay. A lógica está em core/feedback."""
from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from .. import __version__
from ..core import feedback
from ..core.i18n import get_language, tr
from ..core.updater import effective_repo

_COOLDOWN = feedback.Cooldown()  # uma sugestão por minuto, valendo para todas as janelas abertas


class SuggestionDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._box: dict = {}
        self._sending = False
        self.setWindowTitle(tr("Sugerir melhoria"))
        self.setMinimumWidth(520)
        col = QVBoxLayout(self)
        intro = QLabel(tr("Conte sua ideia para o KerbHUD. Não precisa de conta: o texto vai direto para o criador."))
        intro.setWordWrap(True)
        col.addWidget(intro)
        form = QFormLayout()
        self.idea = QPlainTextEdit()
        self.idea.setPlaceholderText(tr("O que você gostaria que o KerbHUD fizesse? (mínimo {} caracteres)").format(feedback.MIN_IDEA))
        self.idea.setFixedHeight(110)
        self.why = QPlainTextEdit()
        self.why.setPlaceholderText(tr("Por quê? Como isso ajudaria nas suas corridas? (opcional)"))
        self.why.setFixedHeight(70)
        self.sim = QComboBox()
        for s in feedback.SIMULATORS:
            self.sim.addItem(tr(s), s)
        self.contact = QLineEdit()
        self.contact.setPlaceholderText(tr("E-mail ou Discord, se quiser resposta (opcional)"))
        self.contact.setMaxLength(feedback.LIMITS["contact"])
        form.addRow(tr("Ideia"), self.idea)
        form.addRow(tr("Por quê"), self.why)
        form.addRow(tr("Simulador"), self.sim)
        form.addRow(tr("Contato"), self.contact)
        col.addLayout(form)
        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color: #9aa0a6;")
        col.addWidget(self.preview)
        self.consent = QCheckBox(tr("Concordo em enviar este texto ao criador do KerbHUD pela internet"))
        col.addWidget(self.consent)
        self.status = QLabel()
        self.status.setWordWrap(True)
        col.addWidget(self.status)
        row = QHBoxLayout()
        self.github = QPushButton(tr("Abrir no GitHub (precisa de conta)"))
        self.copy = QPushButton(tr("Copiar texto"))
        self.send = QPushButton(tr("Enviar"))
        self.close_btn = QPushButton(tr("Fechar"))
        row.addWidget(self.github)
        row.addWidget(self.copy)
        row.addStretch(1)
        row.addWidget(self.send)
        row.addWidget(self.close_btn)
        col.addLayout(row)
        self.github.clicked.connect(self._open_github)
        self.copy.clicked.connect(self._copy)
        self.send.clicked.connect(self._send)
        self.close_btn.clicked.connect(self.close)
        for w in (self.idea, self.why):
            w.textChanged.connect(self._refresh)
        self.contact.textChanged.connect(self._refresh)
        self.sim.currentIndexChanged.connect(self._refresh)
        self.consent.toggled.connect(self._refresh)
        self._refresh()

    # ---- o que será enviado -------------------------------------------- #
    def _data(self) -> dict:
        return {"idea": self.idea.toPlainText(), "why": self.why.toPlainText(), "simulator": str(self.sim.currentData() or ""),
                "contact": self.contact.text(), "version": __version__}

    def _refresh(self) -> None:
        d = self._data()
        parts = [tr("a ideia"), tr("o motivo") if d["why"].strip() else None, tr("o simulador ({})").format(d["simulator"]),
                 tr("a versão do KerbHUD ({})").format(__version__), tr("o contato") if d["contact"].strip() else None]
        self.preview.setText(tr("Será enviado somente: {}. Nada do seu computador, pastas ou contas.").format(
            ", ".join(p for p in parts if p)))
        ok = len(d["idea"].strip()) >= feedback.MIN_IDEA and self.consent.isChecked() and not self._sending
        self.send.setEnabled(ok)

    # ---- ações ----------------------------------------------------------- #
    def _copy(self) -> None:
        d = self._data()
        text = f"{d['idea']}\n\n{d['why']}\n\n{d['simulator']} · KerbHUD {__version__}".strip()
        QApplication.clipboard().setText(text)
        self.status.setText(tr("Texto copiado."))

    def _open_github(self) -> None:
        QDesktopServices.openUrl(QUrl(feedback.suggestion_url(effective_repo(self.settings), __version__, get_language())))

    def _send(self) -> None:
        wait = _COOLDOWN.remaining()
        if wait > 0:
            self.status.setText(tr("Aguarde {} s para enviar outra sugestão.").format(int(wait) + 1))
            return
        try:
            data = feedback.build_submission(**self._data())
        except feedback.FeedbackError as exc:
            self.status.setText(tr(str(exc)))
            return
        self._sending = True
        self._box = {}
        self.status.setText(tr("Enviando..."))
        self._refresh()

        def work() -> None:
            try:
                feedback.submit(data, __version__)
                self._box["ok"] = True
            except feedback.FeedbackError as exc:
                self._box["error"] = str(exc)
            except Exception as exc:  # noqa: BLE001 - nada pode derrubar o overlay
                self._box["error"] = f"erro inesperado: {exc}"

        threading.Thread(target=work, name="kerbhud-suggestion", daemon=True).start()
        QTimer.singleShot(300, self._poll)

    def _poll(self) -> None:
        if "ok" not in self._box and "error" not in self._box:
            QTimer.singleShot(300, self._poll)
            return
        self._sending = False
        if "ok" in self._box:
            _COOLDOWN.mark()
            self.status.setText(tr("Enviado! Obrigado pela sugestão."))
            self.idea.clear()
            self.why.clear()
            self.consent.setChecked(False)
        else:
            self.status.setText(tr(self._box["error"]) + " " + tr("Você pode copiar o texto ou abrir no GitHub."))
        self._refresh()
