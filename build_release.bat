@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
chcp 65001 >nul

echo ========================================
echo     RocoKingdom Clicker - Release Builder
echo ========================================

rem 1) Use the global Python interpreter
set "PY="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.10 -c "import sys; sys.exit(0)" >nul 2>&1
    if not errorlevel 1 set "PY=py -3.10"

    if not defined PY (
        py -3 -c "import sys; sys.exit(0)" >nul 2>&1
        if not errorlevel 1 set "PY=py -3"
    )
)

if not defined PY (
    where python >nul 2>&1
    if not errorlevel 1 set "PY=python"
)

if not defined PY (
    if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set "PY=%LocalAppData%\Programs\Python\Python310\python.exe"
)

if not defined PY (
    echo Failed to locate a usable Python interpreter.
    exit /b 1
)

echo Using Python: %PY%

rem 2) Install build deps
echo Upgrading pip and installing PyInstaller...
call %PY% -m pip install --user --upgrade pip setuptools wheel pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Failed to install PyInstaller.
    exit /b 1
)

rem 3) Run PyInstaller (onedir so interception.dll can sit next to exe)
echo Running PyInstaller...
call %PY% -m PyInstaller --noconfirm --clean --distpath "%~dp0dist" --workpath "%~dp0build_pyinstaller" --specpath "%~dp0build_pyinstaller" --name "RocoKingdom_Clicker" --onedir --add-data "%CD%\data;data" --add-data "%CD%\docs;docs" Clicker.py
if errorlevel 1 (
    echo PyInstaller build failed.
    exit /b 1
)

rem 4) Copy interception.dll if available
if exist "%~dp0interception.dll" (
    echo Copying interception.dll to release folder...
    copy /Y "%~dp0interception.dll" "%~dp0dist\RocoKingdom_Clicker\" >nul
) else (
    echo WARNING: interception.dll not found in project root. Please copy the built DLL into the release folder manually.
)

rem 5) Copy helper files (run script, README)
if exist "%~dp0run_clicker.bat" copy /Y "%~dp0run_clicker.bat" "%~dp0dist\RocoKingdom_Clicker\" >nul
if exist "%~dp0README.md" copy /Y "%~dp0README.md" "%~dp0dist\RocoKingdom_Clicker\" >nul

rem 6) Package into release zip
if not exist "%~dp0release" mkdir "%~dp0release"
set "ZIP_OK=0"
for /l %%I in (1,1,5) do (
    echo Creating release archive... (attempt %%I/5)
    powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Compress-Archive -Path '%~dp0dist\\RocoKingdom_Clicker\\*' -DestinationPath '%~dp0release\\RocoKingdom_Clicker.zip' -Force"
    if not errorlevel 1 (
        set "ZIP_OK=1"
        goto :zip_done
    )
    if %%I LSS 5 (
        echo Archive attempt %%I failed, retrying after a short wait...
        timeout /t 2 /nobreak >nul
    )
)
:zip_done
if "%ZIP_OK%"=="0" (
    echo Failed to create release archive.
    exit /b 1
)

echo Build complete. Release artifact: release\RocoKingdom_Clicker.zip
echo To run the release, extract and run the exe in the folder, or use run_clicker.bat.
endlocal
exit /b 0
