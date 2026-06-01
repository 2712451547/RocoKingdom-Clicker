@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator privileges...
    echo Please click Yes in the UAC dialog.
    powershell -NoProfile -Command "Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', '""%~f0""' -Verb RunAs"
    exit /b
)

if exist "%~dp0RocoKingdom_Clicker.exe" goto release_mode

title RocoKingdom Clicker Release
color 0A
cls

echo.
echo ========================================
echo     RocoKingdom Clicker Release
echo         Powered by Interception
echo ========================================
echo.

set "PYTHON_EXE=%~dp0.venv\Scripts\pythonw.exe"

if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
)

if not exist "%PYTHON_EXE%" (
    echo Local virtual environment not found.
    echo Creating .venv for this release...
    python -m venv .venv
)

"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Local Python environment not found.
    echo.
    echo Please install Python 3.10+ and make sure it is available on PATH.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('"%PYTHON_EXE%" --version') do set "PYTHON_VERSION=%%i"
echo OK: Detected %PYTHON_VERSION%
echo.

echo OK: Using project-local .venv
echo.
echo ========================================
echo Launching clicker...
echo Please wait...
echo ========================================
echo.

"%PYTHON_EXE%" Clicker.py --gui

if errorlevel 1 (
    color 0C
    echo.
    echo ERROR: Program crashed
    echo.
) else (
    color 02
    echo.
    echo OK: Program exited normally
    echo.
)

pause
endlocal
goto :eof

:release_mode
title RocoKingdom Clicker Release
color 0A
cls

echo.
echo ========================================
echo     RocoKingdom Clicker Release
echo         Powered by Interception
echo ========================================
echo.

echo Launching bundled release executable...
echo.

"%~dp0RocoKingdom_Clicker.exe" --gui

if errorlevel 1 (
    color 0C
    echo.
    echo ERROR: Program crashed
    echo.
) else (
    color 02
    echo.
    echo OK: Program exited normally
    echo.
)

pause
endlocal
