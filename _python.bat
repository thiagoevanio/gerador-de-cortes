@echo off
rem Acha o Python do programa (o que tem as bibliotecas) e define PY e PYW.
rem Ordem: .venv da pasta, o salvo pelo doutor, o Python 3.12 do launcher, o do PATH.
set "PY="
set "PYW="
if exist "%~dp0.venv\Scripts\python.exe" call :testar "%~dp0.venv\Scripts\python.exe"
if defined PY goto achou
if not exist "%~dp0python_do_programa.txt" goto procurar
set "SALVO="
set /p SALVO=<"%~dp0python_do_programa.txt"
if defined SALVO call :testar "%SALVO%"
if defined PY goto achou
:procurar
for /f "delims=" %%i in ('py -3.12 -c "import sys;print(sys.executable)" 2^>nul') do call :testar "%%i"
if defined PY goto achou
for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY call :testar "%%i"
if defined PY goto achou
goto :eof
:achou
for %%d in ("%PY%") do set "PYW=%%~dpdpythonw.exe"
if not exist "%PYW%" set "PYW=%PY%"
goto :eof
:testar
if not exist "%~1" goto :eof
"%~1" -c "import sys,tkinter,importlib.util as u;sys.exit(any(u.find_spec(m) is None for m in ('PIL','numpy','faster_whisper','yt_dlp','cv2')))" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
goto :eof
