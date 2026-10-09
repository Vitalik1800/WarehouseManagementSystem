
@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo WAREHOUSE MANAGEMENT SYSTEM - TEST SUITE
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Python virtual environment not found.
    exit /b 1
)

set "PYTHON=.venv\Scripts\python.exe"

echo.
echo [1/3] Running automated tests and coverage...
"%PYTHON%" -m pytest --cov=backend.app --cov-report=term-missing --cov-fail-under=90 -q
if errorlevel 1 goto failed

echo.
echo [2/3] Checking dependency compatibility...
"%PYTHON%" -m pip check
if errorlevel 1 goto failed

echo.
echo [3/3] Auditing locked dependencies...
"%PYTHON%" -m pip_audit -r requirements-lock.txt
if errorlevel 1 goto failed

echo.
echo ==========================================
echo ALL CHECKS PASSED
echo ==========================================
exit /b 0

:failed
echo.
echo ==========================================
echo CHECK FAILED - REVIEW OUTPUT ABOVE
echo ==========================================
exit /b 1
