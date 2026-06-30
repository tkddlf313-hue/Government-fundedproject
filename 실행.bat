@echo off
chcp 65001 > nul
echo.
echo  ===================================
echo   [Paper] Gov Support Program Launcher
echo  ===================================
echo.
cd /d "%~dp0"
set PYTHON=C:\Users\HSCAG-0710\AppData\Local\Programs\Python\Python313\python.exe
echo [1/2] Installing packages...
%PYTHON% -m pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)
echo [2/2] Starting app...
echo.
echo  Browser will open automatically.
echo  Press Ctrl+C in this window to stop.
echo.
%PYTHON% -m streamlit run app.py --server.headless false
pause
