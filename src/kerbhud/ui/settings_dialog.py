"""Janela de Configurações: geral, atalhos, LMU e gerenciamento de layouts.

A janela só coleta valores e devolve um "patch"; quem valida e grava é `core.settings_schema` (testado sem Qt).
As ações da aba Layouts valem na hora (são operações em arquivos), as demais abas só ao clicar em OK/Aplicar.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QHBoxLayout, QKeySequenceEdit, QLabel, QLineEdit, QListWidget, QMessageBox,
                               QPushButton, QTabWidget, QToolButton, QVBoxLayout, QWidget)

from ..core import updater
from ..core.i18n import LANGUAGES, module_title, tr
from ..core.settings_schema import (CONTACT_BADGES, HOTKEY_LABELS, SIMULATOR_LABELS, SIMULATORS, UI_HZ_CHOICES,
                                    UNIT_LABELS, UNITS, UPDATE_HZ_CHOICES, settings_to_patch, validate_patch)
from ..core.visibility import MODE_LABELS, MODES


def _combo(items: list[tuple[object, str]], current) -> QComboBox:
    cb = QComboBox()
    for value, label in items:
        cb.addItem(tr(label), value)
    idx = cb.findData(current)
    cb.setCurrentIndex(max(0, idx))
    return cb


class _HotkeyField(QWidget):
    """Campo de atalho: grava só o primeiro acorde; o botão limpa (atalho desligado)."""

    def __init__(self, text: str):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.edit = QKeySequenceEdit(QKeySequence(text) if text else QKeySequence())
        self.edit.setMaximumSequenceLength(1)
        clear = QToolButton()
        clear.setText(tr("Limpar"))
        clear.clicked.connect(self.edit.clear)
        row.addWidget(self.edit, 1)
        row.addWidget(clear)

    def text(self) -> str:
        seq = self.edit.keySequence()
        return seq.toString(QKeySequence.PortableText) if seq.count() else ""


class LayoutsPanel(QWidget):
    """Lista de layouts com ativar/renomear/duplicar/exportar/importar/excluir (vale na hora)."""

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        col = QVBoxLayout(self)
        self.lay_list = QListWidget()
        col.addWidget(self.lay_list, 1)
        for text, fn in (("Ativar", self._lay_activate), ("Renomear...", self._lay_rename),
                         ("Duplicar", self._lay_duplicate), ("Exportar...", self._lay_export),
                         ("Importar...", self._lay_import), ("Excluir", self._lay_delete)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            col.addWidget(b)
        self._refresh_layouts()

    def _refresh_layouts(self, select: Optional[str] = None) -> None:
        self.lay_list.clear()
        active = self.manager.layout.name
        for n in self.manager.store.list_names():
            self.lay_list.addItem(f"{n}   ({tr('ativo')})" if n == active else n)
            self.lay_list.item(self.lay_list.count() - 1).setData(256, n)
        want = select or active
        for i in range(self.lay_list.count()):
            if self.lay_list.item(i).data(256) == want:
                self.lay_list.setCurrentRow(i)

    def _sel(self) -> Optional[str]:
        it = self.lay_list.currentItem()
        return it.data(256) if it else None

    def _guard(self, fn) -> None:
        try:
            fn()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self, tr("Layouts"), str(exc))

    def _lay_activate(self) -> None:
        if (n := self._sel()):
            self._guard(lambda: (self.manager.switch_layout(n), self._refresh_layouts(n)))

    def _lay_rename(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        n = self._sel()
        if not n:
            return
        new, ok = QInputDialog.getText(self, tr("Renomear layout"), tr("Novo nome:"), text=n)
        if ok and new.strip() and new.strip() != n:
            self._guard(lambda: (self.manager.rename_layout(n, new), self._refresh_layouts(new.strip())))

    def _lay_duplicate(self) -> None:
        if (n := self._sel()):
            self._guard(lambda: self._refresh_layouts(self.manager.duplicate_layout(n)))

    def _lay_export(self) -> None:
        n = self._sel()
        if not n:
            return
        path, _ = QFileDialog.getSaveFileName(self, tr("Exportar layout"), f"{n}.json", "Layout (*.json)")
        if path:
            self._guard(lambda: self.manager.export_layout(n, path))

    def _lay_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("Importar layout"), "", "Layout (*.json)")
        if path:
            self._guard(lambda: self._refresh_layouts(self.manager.import_layout(path)))

    def _lay_delete(self) -> None:
        n = self._sel()
        if not n:
            return
        if len(self.manager.store.list_names()) <= 1:
            QMessageBox.information(self, tr("Layouts"), tr("Mantenha ao menos um layout."))
            return
        if QMessageBox.question(self, tr("Excluir layout"), tr("Excluir o layout '{}'?").format(n)) == QMessageBox.Yes:
            self._guard(lambda: (self.manager.delete_layout(n), self._refresh_layouts()))

class SettingsDialog(QDialog):
    def __init__(self, settings: dict, manager=None, on_apply: Optional[Callable[[dict], list[str]]] = None,
                 on_check_updates: Optional[Callable[[], None]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("KerbHUD: Configurações"))
        self.settings, self.manager, self._on_apply = settings, manager, on_apply
        init = settings_to_patch(settings)
        tabs = QTabWidget()

        # ---- Geral ---- #
        g = QWidget()
        f = QFormLayout(g)
        self.sim = _combo([(k, SIMULATOR_LABELS[k]) for k in SIMULATORS], init["simulator"])
        self.vis = _combo([(k, MODE_LABELS[k]) for k in MODES], init["visibility"])
        self.language = _combo([(k, v) for k, v in LANGUAGES.items()], init.get("language", "auto"))
        self.units = _combo([(k, UNIT_LABELS[k]) for k in UNITS], init["units"])
        self.update_hz = _combo([(n, f"{n} Hz") for n in UPDATE_HZ_CHOICES], init["update_hz"])
        self.ui_hz = _combo([(n, f"{n} quadros/s") for n in UI_HZ_CHOICES], init["ui_hz"])
        self.country = QLineEdit(init.get("my_country") or "")
        self.country.setPlaceholderText(tr("ex.: br  (vazio = não mostrar)"))
        self.country.setMaxLength(40)
        self.wordmark = QCheckBox(tr("Mostrar o nome da fabricante quando não houver logo"))
        self.wordmark.setChecked(bool(init["logo_wordmark"]))
        self.invert_clutch = QCheckBox(tr("iRacing: embreagem invertida (100% = solta)"))
        self.invert_clutch.setChecked(bool(init["iracing"]["invert_clutch"]))
        f.addRow(tr("Idioma / Language"), self.language)
        f.addRow(tr("Simulador"), self.sim)
        f.addRow(tr("Mostrar o overlay"), self.vis)
        f.addRow(tr("Unidades"), self.units)
        f.addRow(tr("Leitura dos dados"), self.update_hz)
        f.addRow(tr("Atualização da tela"), self.ui_hz)
        f.addRow(tr("Meu país (bandeira)"), self.country)
        f.addRow(self.wordmark)
        f.addRow(self.invert_clutch)
        note = QLabel(tr("Trocar o simulador reconecta na hora. A leitura dos dados só muda ao reconectar."))
        note.setWordWrap(True)
        f.addRow(note)
        tabs.addTab(g, "Geral")

        # ---- Atalhos ---- #
        h = QWidget()
        hf = QFormLayout(h)
        self.hotkeys: dict[str, _HotkeyField] = {}
        for action, label in HOTKEY_LABELS.items():
            fld = _HotkeyField(init["hotkeys"].get(action, ""))
            self.hotkeys[action] = fld
            hf.addRow(tr(label), fld)
        hint = QLabel(tr("Use sempre um modificador (Ctrl, Alt, Shift ou Win) + uma tecla. "
                      "Atalhos repetidos ou já usados por outro programa são avisados."))
        hint.setWordWrap(True)
        hf.addRow(hint)
        tabs.addTab(h, "Atalhos")

        # ---- LMU ---- #
        l = QWidget()
        lf = QFormLayout(l)
        lmu = init["lmu"]
        self.driver_rank = QLineEdit(lmu.get("driver_rank") or "")
        self.driver_rank.setPlaceholderText(tr("ex.: B2  (B/S/G/P + 1 a 9)"))
        self.safety_rank = QLineEdit(lmu.get("safety_rank") or "")
        self.safety_rank.setPlaceholderText(tr("ex.: S3"))
        self.badge = QComboBox()
        self.badge.addItem(tr("(nenhum)"), None)
        for b in CONTACT_BADGES:
            self.badge.addItem(b, b)
        self.badge.setCurrentIndex(max(0, self.badge.findData(lmu.get("contact_badge"))))
        lf.addRow(tr("Meu Driver Rank"), self.driver_rank)
        lf.addRow(tr("Meu Safety Rank"), self.safety_rank)
        lf.addRow(tr("Meu selo"), self.badge)
        info = QLabel(tr("O LMU não informa seu rank pelo jogo; o que você escrever aqui é só exibido no seu "
                      "próprio perfil."))
        info.setWordWrap(True)
        lf.addRow(info)
        tabs.addTab(l, tr("Le Mans Ultimate"))

        # ---- Atualização ---- #
        u = QWidget()
        uf = QFormLayout(u)
        self.update_repo = QLineEdit(init.get("update_repo") or "")
        self.update_repo.setPlaceholderText(updater.DEFAULT_REPO)  # vazio = repositório oficial
        self.update_auto = QCheckBox(tr("Avisar na bandeja quando houver versão nova (ao iniciar)"))
        self.update_auto.setChecked(bool(init.get("check_updates_on_start", True)))
        uf.addRow(tr("Repositório no GitHub"), self.update_repo)
        repo_hint = QLabel(tr("Deixe vazio para usar o repositório oficial do KerbHUD."))
        repo_hint.setWordWrap(True)
        uf.addRow(repo_hint)
        uf.addRow(self.update_auto)
        if on_check_updates is not None:
            btn = QPushButton(tr("Verificar atualizações agora"))
            btn.clicked.connect(lambda: (self._apply(), on_check_updates()))
            uf.addRow(btn)
        uinfo = QLabel(tr("As atualizações vêm dos Releases públicos do repositório. Só se conecta ao github.com (HTTPS); "
                       "a pasta de dados (logos, bandeiras, layouts...) nunca é alterada."))
        uinfo.setWordWrap(True)
        uf.addRow(uinfo)
        tabs.addTab(u, tr("Atualização"))

        # ---- Layouts ---- #
        if manager is not None:
            self.layouts_panel = LayoutsPanel(manager)
            tabs.addTab(self.layouts_panel, "Layouts")

        box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        box.button(QDialogButtonBox.Ok).setText(tr("OK"))
        box.button(QDialogButtonBox.Apply).setText(tr("Aplicar"))
        box.button(QDialogButtonBox.Cancel).setText(tr("Cancelar"))
        box.accepted.connect(self._ok)
        box.rejected.connect(self.reject)
        box.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        root = QVBoxLayout(self)
        root.addWidget(tabs)
        root.addWidget(box)
        self.resize(460, 520)

    # ---- patch ---- #
    def patch(self) -> dict:
        return {
            "language": self.language.currentData(), "simulator": self.sim.currentData(), "visibility": self.vis.currentData(),
            "units": self.units.currentData(), "update_hz": self.update_hz.currentData(),
            "ui_hz": self.ui_hz.currentData(), "my_country": self.country.text().strip(),
            "logo_wordmark": self.wordmark.isChecked(),
            "update_repo": self.update_repo.text().strip(), "check_updates_on_start": self.update_auto.isChecked(),
            "iracing": {"invert_clutch": self.invert_clutch.isChecked()},
            "lmu": {"driver_rank": self.driver_rank.text().strip(), "safety_rank": self.safety_rank.text().strip(),
                    "contact_badge": self.badge.currentData()},
            "hotkeys": {a: f.text() for a, f in self.hotkeys.items()},
        }

    def _apply(self) -> bool:
        clean, errors = validate_patch(self.patch(), self.settings)
        if errors:
            QMessageBox.warning(self, tr("Configurações inválidas"), tr("Corrija:") + "\n\n• " + "\n• ".join(errors))
            return False
        warnings = self._on_apply(clean) if self._on_apply else []
        if warnings:
            QMessageBox.information(self, tr("Aviso"), "\n".join(warnings))
        return True

    def _ok(self) -> None:
        if self._apply():
            self.accept()


class ModuleConfigDialog(QDialog):
    """Opções de UM módulo (montadas de `core.module_options`). Cada mudança vale na hora e é salva no layout."""

    def __init__(self, manager, mid: str, parent=None):
        super().__init__(parent)
        from ..core.layout import MODULES
        from ..core.module_options import specs_for
        self.m, self.mid = manager, mid
        self.setWindowTitle(tr("Config: {}").format(module_title(mid, MODULES[mid].title).title()))
        opts = manager.layout.modules[mid].options
        form = QFormLayout()
        for o in specs_for(mid):
            cur = o.get(opts)
            if o.kind == "bool":
                w = QCheckBox(tr(o.label))
                w.setChecked(bool(cur))
                w.toggled.connect(lambda on, k=o.key: manager.set_option(mid, k, bool(on)))
                form.addRow(w)
            elif o.kind == "choice":
                cb = _combo(list(o.choices), cur)
                cb.currentIndexChanged.connect(
                    lambda _i, op=o, c=cb: manager.set_option(mid, op.key, op.cast(c.currentData()) if op.cast else c.currentData()))
                form.addRow(tr(o.label), cb)
            else:  # multi: um liga/desliga por item
                form.addRow(QLabel(tr(o.label)))
                for item, label in o.choices:
                    w = QCheckBox(tr(label))
                    w.setChecked(item in cur)
                    if o.apply == "column":
                        w.toggled.connect(lambda on, k=item: manager.set_column(mid, k, bool(on)))
                    else:
                        w.toggled.connect(lambda on, k=item: manager.set_channel(k, bool(on)))
                    form.addRow(w)
        col = QVBoxLayout(self)
        col.addLayout(form)
        close = QPushButton(tr("Fechar"))
        close.clicked.connect(self.accept)
        col.addWidget(close)
