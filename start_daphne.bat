@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------
rem Start Daphne (ASGI) for Project GCE_3 on Windows
rem Usage:  start_daphne.bat [port] [bind]
rem   port - default 8000
rem   bind - default 0.0.0.0
rem Optional: set env before run
rem   set DJANGO_ALLOW_ALL_HOSTS=1    (allow any Host header for tunnels)
rem   set DAPHNE_OPTS="-v2 --access-log -"  (extra daphne flags)
rem ---------------------------------------------

set PORT=%1
if "%PORT%"=="" set PORT=8000
set BIND=%2
if "%BIND%"=="" set BIND=0.0.0.0

set ROOT=%~dp0
cd /d "%ROOT%"

if not exist "venv\Scripts\python.exe" (
  echo [ERROR] Virtualenv not found at venv\Scripts\python.exe
  echo Create venv and install requirements first:
  echo   python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
  exit /b 1
)

call "venv\Scripts\activate.bat"

if "%DJANGO_SETTINGS_MODULE%"=="" set DJANGO_SETTINGS_MODULE=gce_project.settings

echo Starting Daphne on %BIND%:%PORT% ...
echo   DJANGO_SETTINGS_MODULE=%DJANGO_SETTINGS_MODULE%
if not "%DJANGO_ALLOW_ALL_HOSTS%"=="" echo   DJANGO_ALLOW_ALL_HOSTS=%DJANGO_ALLOW_ALL_HOSTS%

REM Use python -m to ensure the module is resolved from venv
python -m daphne %DAPHNE_OPTS% -b %BIND% -p %PORT% gce_project.asgi:application

endlocal
