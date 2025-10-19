@echo off
setlocal enabledelayedexpansion

rem ---------------------------------------------
rem Start Daphne (ASGI) for Project GCE_3 on Windows
rem Usage:  start_daphne.bat [port] [bind]
rem   port - default 8000
rem   bind - default 0.0.0.0
rem Optional: set env before run
rem   set DJANGO_ALLOW_ALL_HOSTS=1      (allow any Host header for tunnels)
rem   set DAPHNE_OPTS="-v2 --access-log -"  (extra daphne flags; --reload is added automatically)
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

echo Target: %BIND%:%PORT%
echo   DJANGO_SETTINGS_MODULE=%DJANGO_SETTINGS_MODULE%
if not "%DJANGO_ALLOW_ALL_HOSTS%"=="" echo   DJANGO_ALLOW_ALL_HOSTS=%DJANGO_ALLOW_ALL_HOSTS%

REM Detect if Daphne supports --reload; if not, fall back to Django runserver (which auto-reloads)
set HAS_RELOAD=
for /f "delims=" %%A in ('python -m daphne -h 2^>nul ^| findstr /I /C:"--reload"') do (
  set HAS_RELOAD=1
)

if defined HAS_RELOAD (
  echo Starting Daphne with autoreload...
  set RELOAD_ARG=--reload
  if defined DAPHNE_OPTS (
    echo %DAPHNE_OPTS% | findstr /I /C:"--reload" >nul && set RELOAD_ARG=
  )
  python -m daphne %DAPHNE_OPTS% %RELOAD_ARG% -b %BIND% -p %PORT% gce_project.asgi:application
) else (
  echo Daphne does not support --reload in this version. Using Django runserver with autoreload.
  python manage.py runserver %BIND%:%PORT%
)

endlocal
