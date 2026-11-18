@echo off
rem Mostra os dados lidos do Le Mans Ultimate por 60 s.
setlocal
chcp 65001 >nul
title KerbHUD - Diagnostico-LMU
cd /d "%~dp0"
rem Usa SEMPRE o codigo desta pasta (caminho absoluto), nao o de outra copia antiga.
set "PYTHONPATH=%~dp0src"
set "PYTHONIOENCODING=utf-8"
where python >nul 2>nul
if errorlevel 1 (set "PY=py -3") else (set "PY=python")
echo ======================================================
%PY% -m kerbhud --version
echo ======================================================
%PY% -m kerbhud diag --sim lmu --seconds 60 --hz 2 --out "%~dp0diagnostico-lmu.txt"
echo.
echo O resultado tambem foi salvo em: %~dp0diagnostico-lmu.txt
pause
