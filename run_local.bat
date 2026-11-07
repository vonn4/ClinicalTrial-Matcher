@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 run_local.py %*
) else (
  python run_local.py %*
)
if errorlevel 1 pause
