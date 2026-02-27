@echo off
title PDF til JSON konverter

echo ============================================================
echo   PDF til JSON konverter
echo ============================================================
echo.

cd /d "%~dp0"

python --version >nul 2>&1
if not errorlevel 1 goto :python_ok

echo Python ikke fundet. Downloader og installerer...
echo.

powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.3/python-3.12.3-amd64.exe' -OutFile '%TEMP%\python-installer.exe'"

if not exist "%TEMP%\python-installer.exe" (
    echo FEJL: Kunne ikke downloade Python.
    echo Download manuelt fra https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Installerer Python (dette kan tage et minut)...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0

del "%TEMP%\python-installer.exe" >nul 2>&1

echo Python installeret. Genstarter script...
echo.

:: Opdater PATH i denne session
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\;%LOCALAPPDATA%\Programs\Python\Python312\Scripts\;%PATH%"

python --version >nul 2>&1
if errorlevel 1 (
    echo FEJL: Python blev installeret men kan ikke findes.
    echo Luk dette vindue, aaben en ny kommandoprompt og proev igen.
    echo.
    pause
    exit /b 1
)

:python_ok
echo Python fundet:
python --version
echo.

pip show pikepdf >nul 2>&1
if errorlevel 1 (
    echo Installerer pakker ...
    echo.
    pip install pdfminer.six pikepdf Pillow
    echo.
)

set count=0
for %%f in (*.pdf *.PDF) do set /a count+=1

if %count%==0 (
    echo Ingen PDF-filer fundet i mappen:
    echo %cd%
    echo.
    pause
    exit /b 1
)

echo Fandt %count% PDF-fil(er). Starter konvertering...
echo.

python pdf_to_json.py --dir .

echo.
echo Faerdig! JSON-filerne ligger i samme mappe.
echo.
pause
