@echo off
rem Instala o PySide6 (so na primeira vez).
setlocal
chcp 65001 >nul
title KerbHUD - Instalar-dependencias
cd /d "%~dp0"
rem Usa SEMPRE o codigo desta pasta (caminho absoluto), nao o de outra copia antiga.
set "PYTHONPATH=%~dp0src"
set "PYTHONIOENCODING=utf-8"
where python >nul 2>nul
if errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo ======================================================
%PY% -m kerbhud --version
echo ======================================================
%PY% -m pip install -r requirements.txt
pause
