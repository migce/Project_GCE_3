@echo off
setlocal enabledelayedexpansion

rem -----------------------------------------------------
rem Cloudflare Tunnel – Foreground launcher (minimal logs)
rem This script validates config and runs cloudflared in this window
rem with low log verbosity (warn).
rem -----------------------------------------------------

set CFEXE=cloudflared
if exist "C:\Program Files\cloudflared\cloudflared.exe" set CFEXE="C:\Program Files\cloudflared\cloudflared.exe"
if exist "C:\Program Files (x86)\cloudflared\cloudflared.exe" set CFEXE="C:\Program Files (x86)\cloudflared\cloudflared.exe"

set CFCONFIG=%USERPROFILE%\.cloudflared\config.yml

echo === Cloudflare Tunnel (foreground) ===
echo Executable : %CFEXE%
echo Config     : %CFCONFIG%

if not exist "%CFCONFIG%" (
  echo [ERROR] Config not found: %CFCONFIG%
  echo Create config.yml in ^%USERPROFILE^%\.cloudflared first.
  exit /b 1
)

rem Validate ingress rules
echo Validating config ...
%CFEXE% tunnel --config "%CFCONFIG%" ingress validate
if errorlevel 1 (
  echo [ERROR] Config validation failed. See errors above.
  exit /b 1
)

rem Extract tunnel ID from config (line starting with 'tunnel:')
for /f "tokens=2 delims=: " %%A in ('findstr /b /c:"tunnel:" "%CFCONFIG%"') do set TUNNEL_ID=%%A
set TUNNEL_ID=%TUNNEL_ID: =%

echo Running: %CFEXE% tunnel --config "%CFCONFIG%" --loglevel warn run %TUNNEL_ID%
%CFEXE% tunnel --config "%CFCONFIG%" --loglevel warn run %TUNNEL_ID%

endlocal
