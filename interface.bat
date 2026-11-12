@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
call "%~dp0_python.bat"
if defined PY goto abrir
echo.
echo  Faltam o Python ou as bibliotecas neste PC.
echo  Vou abrir o instalador: ele examina o PC e instala tudo sozinho.
echo.
timeout /t 4 >nul
call "%~dp0INSTALAR.bat"
goto :eof
:abrir
start "" "%PYW%" interface.py
