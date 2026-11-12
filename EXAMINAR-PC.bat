@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
title Examinar o PC - Gerador de Cortes
call "%~dp0_python.bat"
if defined PY ( "%PY%" doutor.py ) else ( py doutor.py 2>nul || python doutor.py 2>nul || echo Nenhum Python neste PC. Rode o INSTALAR.bat. )
echo.
pause
