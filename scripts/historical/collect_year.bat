@echo off
setlocal

if "%~1"=="" (
    echo.
    echo Usage: collect_year.bat YYYY
    echo Example: collect_year.bat 2025
    echo.
    exit /b 1
)

cd /d "%~dp0..\.."

powershell -ExecutionPolicy Bypass -File ".\scripts\historical\collect_year.ps1" -Year %~1

if errorlevel 1 (
    echo.
    echo ============================================
    echo COLLECTION %~1 : INCOMPLETE
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo COLLECTION %~1 : PASS
echo ============================================
pause
