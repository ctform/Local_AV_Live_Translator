@echo off
setlocal
cd /d "%~dp0"
title Local AV Live Translator
echo Starting Local AV Live Translator...
echo -----------------------------------

if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

if not exist "%PYTHON%" (
    echo Python was not found. Install Python 3.10+ or create .venv.
    pause
    exit /b 1
)

rem Make the CUDA runtime installed in this venv visible to CTranslate2.
if exist ".venv\Lib\site-packages\nvidia\cublas\bin" (
    set "PATH=%~dp0.venv\Lib\site-packages\nvidia\cublas\bin;%PATH%"
)
if exist ".venv\Lib\site-packages\ctranslate2" (
    set "PATH=%~dp0.venv\Lib\site-packages\ctranslate2;%PATH%"
)

%PYTHON% main.py

if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
endlocal
