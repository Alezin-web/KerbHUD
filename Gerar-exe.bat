@echo off
rem Gera o KerbHUD.exe (pasta dist\KerbHUD). Precisa de internet so na 1a vez (instala o PyInstaller).
setlocal
chcp 65001 >nul
title KerbHUD - gerar exe
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (set "PY=py -3") else (set "PY=python")
set "PYTHONPATH=%~dp0src"
%PY% -m kerbhud --version
echo [1/3] Instalando dependencias de build...
%PY% -m pip install -r requirements-build.txt
if errorlevel 1 goto erro
echo [2/3] Rodando os testes...
set "PYTHONPATH=%~dp0src"
%PY% -m unittest discover -s tests
if errorlevel 1 goto erro
echo [3/3] Empacotando com o PyInstaller...
%PY% -m PyInstaller --noconfirm --clean --distpath dist --workpath build_exe\work build_exe\KerbHUD.spec
if errorlevel 1 goto erro
echo.
echo PRONTO: dist\KerbHUD\KerbHUD.exe
echo (Para diagnostico use dist\KerbHUD\KerbHUD-Diagnostico.exe diag)
pause
exit /b 0
:erro
echo.
echo FALHOU. Copie as mensagens acima e envie para analise.
pause
exit /b 1
