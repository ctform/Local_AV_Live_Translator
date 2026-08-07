@echo off
title Live Subtitle Translator
echo Starting Live Subtitle Translator...
echo -----------------------------------

:: Set paths for CUDA DLLs (Adjust if Python path is different on other machines)
set "PATH=C:\Users\arthur\AppData\Local\Programs\Python\Python311\Lib\site-packages\nvidia\cublas\bin;C:\Users\arthur\AppData\Local\Programs\Python\Python311\Lib\site-packages\nvidia\cudnn\bin;%PATH%"

:: Run the script
python main.py

echo.
echo Application closed.
pause
