@echo off
cd /d "%~dp0"

if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo   RS Dragonwilds Save Editor
echo   ==========================
echo   Open http://localhost:5000 in your browser
echo.

python app.py
pause
