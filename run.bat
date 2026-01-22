@echo off
REM ========================================
REM Trader Ledger - One-Click Launcher
REM For Baba's Trading Records
REM ========================================

echo.
echo ========================================
echo   Starting Trader Ledger...
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo ERROR: Virtual environment not found!
    echo Please run setup.bat first.
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment and run
call venv\Scripts\activate.bat
python app.py

REM Deactivate when done
deactivate

echo.
echo Application closed.
pause
