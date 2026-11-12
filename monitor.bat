@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Monitor de Cortes
call "%~dp0_python.bat"
if not defined PY (
  echo Faltam o Python ou as bibliotecas. Rode o INSTALAR.bat primeiro.
  pause
  goto :eof
)
"%PY%" monitor.py
pause
