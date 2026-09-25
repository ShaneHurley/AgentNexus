@echo off
setlocal
cd /d "%~dp0"

REM Prefer newest available Python 3.10+ via the Windows py launcher
where py >nul 2>&1 && (
  py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && (py -3.13 start.py %* & exit /b %ERRORLEVEL%)
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && (py -3.12 start.py %* & exit /b %ERRORLEVEL%)
  py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && (py -3.11 start.py %* & exit /b %ERRORLEVEL%)
  py -3.10 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && (py -3.10 start.py %* & exit /b %ERRORLEVEL%)
)

where python >nul 2>&1 && (
  python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && (python start.py %* & exit /b %ERRORLEVEL%)
)

echo Python 3.10+ not found. Install from https://www.python.org/downloads/
exit /b 1
