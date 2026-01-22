@echo off
REM ============================================
REM Trader Ledger - Professional Build Script
REM Creates standalone .exe and installer
REM ============================================

echo.
echo ============================================
echo   Building Trader Ledger Installer
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)

echo [Step 1/5] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [Step 2/5] Installing build tools...
pip install pyinstaller pillow

echo.
echo [Step 3/5] Creating application icon...
python create_icon.py

echo.
echo [Step 4/5] Building executable with PyInstaller...
pyinstaller --clean --noconfirm TraderLedger.spec

if not exist "dist\TraderLedger.exe" (
    echo ERROR: Executable build failed!
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo Executable created: dist\TraderLedger.exe
echo.
echo [Step 5/5] To create installer:
echo   1. Install Inno Setup from: https://jrsoftware.org/isdl.php
echo   2. Right-click installer.iss and select "Compile"
echo   3. Installer will be in: installer_output\
echo.
echo OR just distribute: dist\TraderLedger.exe (standalone, no install needed)
echo.
pause
