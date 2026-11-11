@echo off
cd /d "%~dp0"
echo Abrindo o instalador (vai pedir permissao de administrador)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
