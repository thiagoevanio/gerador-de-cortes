@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
echo ==========================================
echo        GERADOR DE CORTES 9:16
echo ==========================================
echo.
set /p LINK=Cole o link (YouTube/Twitch) ou caminho do video: 
set /p INICIO=Inicio do corte (ex: 12:30): 
set /p FIM=Fim do corte (ex: 13:20): 
set /p PERGUNTA=Pergunta da faixa (ENTER = Claude cria): 
set /p FOTO=Caminho da foto do topo (ENTER = automatico): 
set /p LEG=Colocar legenda no video? (S/N, ENTER = S): 

set EXTRA=
if not "%PERGUNTA%"=="" set EXTRA=%EXTRA% --pergunta "%PERGUNTA%"
if not "%FOTO%"=="" set EXTRA=%EXTRA% --foto "%FOTO%"
if /i "%LEG%"=="N" set EXTRA=%EXTRA% --sem-legenda

python cortes.py "%LINK%" --inicio %INICIO% --fim %FIM% %EXTRA%
echo.
pause
