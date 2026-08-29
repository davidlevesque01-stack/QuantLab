@echo off
cd /d "%~dp0..\.."

powershell -ExecutionPolicy Bypass -File ".\scripts\historical\collect_year.ps1" -Year 2026

if errorlevel 1 (
    echo.
    echo ============================================
    echo COLLECTION 2026 : INCOMPLETE
    echo ============================================
    pause
    exit /b 1
)

echo.
echo ============================================
echo COLLECTION 2026 : PASS
echo ============================================
pause
