# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: gera dist\KerbHUD\ com dois executáveis na mesma pasta:
#   KerbHUD.exe              - o overlay (sem janela de console)
#   KerbHUD-Diagnostico.exe  - mesma coisa, com console, para rodar `diag`, `snapshot`, `--version`...
# Rode pelo Gerar-exe.bat (na pasta do projeto). NÃO foi testado no Windows pelo autor deste pacote.
from pathlib import Path

ROOT = Path(SPECPATH).parent
ICON = str(ROOT / "build_exe" / "kerbhud.ico")

a = Analysis(
    [str(ROOT / "build_exe" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=[(str(ROOT / "CHANGELOG.md"), "."), (str(ROOT / "CHANGELOG.en.md"), "."), (str(ROOT / "GUIDE.md"), "."), (str(ROOT / "GUIDE.en.md"), "."), (str(ROOT / "changelog"), "changelog")],
    hiddenimports=[],
    excludes=["tkinter", "unittest", "pydoc", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
              "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
              "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtSql", "PySide6.QtTest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe_gui = EXE(pyz, a.scripts, [], exclude_binaries=True, name="KerbHUD", console=False, icon=ICON,
              disable_windowed_traceback=False, upx=False)
exe_diag = EXE(pyz, a.scripts, [], exclude_binaries=True, name="KerbHUD-Diagnostico", console=True, icon=ICON,
               upx=False)

coll = COLLECT(exe_gui, exe_diag, a.binaries, a.datas, name="KerbHUD", upx=False)
