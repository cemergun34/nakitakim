@echo off
title webadmin-nakitakim

echo ============================================================
echo   IQ Finans - webadmin-nakitakim Server
echo   Start time: %DATE% %TIME%
echo ============================================================
echo.

REM PostgreSQL Settings
set PG_HOST=127.0.0.1
set PG_PORT=5432
set PG_DB=neondb
set PG_USER=postgres
set PG_PASS=123
set PG_SSLMODE=disable

REM Flask Settings
set WEBADMIN_SECRET_KEY=FpproGizliAnahtar2024XYZ
set WEBADMIN_DEBUG=false
set WEBADMIN_PORT=5050
set WEBADMIN_HOST=0.0.0.0
set WEBADMIN_API_KEY=nakit-akim-api-key-2024-secure

REM Python Settings
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

REM Create logs folder
if not exist "logs" mkdir logs

REM Log file name (dated)
set LOG_FILE=logs\webadmin_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%.log

echo [INFO] Log file: %LOG_FILE%
echo [INFO] Server: http://0.0.0.0:%WEBADMIN_PORT%
echo [INFO] Press Ctrl+C to stop
echo.

echo [%TIME%] Server starting... >> "%LOG_FILE%"

REM --- Try py launcher first ---
where py >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [INFO] Using: py launcher
    py app.py >> "%LOG_FILE%" 2>&1
    goto END
)

REM --- Try python ---
where python >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo [INFO] Using: python
    python app.py >> "%LOG_FILE%" 2>&1
    goto END
)

REM --- Try common install paths ---
set PYTHON_PATH=C:\Python311\python.exe
if not exist "%PYTHON_PATH%" set PYTHON_PATH=C:\Python310\python.exe
if not exist "%PYTHON_PATH%" set PYTHON_PATH=C:\Python39\python.exe
if not exist "%PYTHON_PATH%" set PYTHON_PATH=C:\Python38\python.exe
if not exist "%PYTHON_PATH%" set PYTHON_PATH=C:\Python312\python.exe

if exist "%PYTHON_PATH%" (
    echo [INFO] Using: %PYTHON_PATH%
    "%PYTHON_PATH%" app.py >> "%LOG_FILE%" 2>&1
    goto END
)

echo.
echo [ERROR] Python not found! Please add Python to PATH or set PYTHON_PATH manually in this bat file.
echo.
pause

:END
echo.
echo ============================================================
echo   SERVER STOPPED: %DATE% %TIME%
echo   Check log: %LOG_FILE%
echo ============================================================
echo.
pause
