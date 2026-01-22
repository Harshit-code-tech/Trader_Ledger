@echo off
REM ========================================
REM Trader Ledger - First-Time Setup
REM ========================================

echo.
echo ========================================
echo   Trader Ledger Setup
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10 or higher from python.org
    echo.
    pause
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

REM Create virtual environment
if not exist "venv\" (
    echo.
    echo [2/4] Creating virtual environment...
    python -m venv venv
) else (
    echo.
    echo [2/4] Virtual environment already exists.
)

REM Activate and install dependencies
echo.
echo [3/4] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

REM Create necessary directories and database
echo.
echo [4/4] Initializing database...
python core/practise/db_init.py

deactivate

echo.
echo ========================================
echo   Setup Complete!
echo ========================================
echo.
echo You can now run the application using:
echo   run.bat
echo.
pause
