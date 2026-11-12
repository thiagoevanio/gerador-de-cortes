@echo off
cd /d "%~dp0"
echo Gerando o instalador (Setup.exe) do Gerador de Cortes...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gerar_setup.ps1"
if errorlevel 1 (echo. & echo Deu erro - veja a mensagem acima.) else (explorer "%~dp0dist")
pause
