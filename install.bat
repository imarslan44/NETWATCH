@echo off
REM ─────────────────────────────────────────────────────────────────
REM  NetWatch — Windows Install Script
REM  Installs dependencies and sets up auto-start on login
REM ─────────────────────────────────────────────────────────────────

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║        NetWatch Windows Installer        ║
echo  ╚══════════════════════════════════════════╝
echo.

REM ── Check Python ──
python --version >nul 2>&1
IF ERRORLEVEL 1 (
    echo  ❌ Python not found!
    echo     Download Python from https://python.org and add to PATH.
    pause
    exit /b 1
)

FOR /F "tokens=*" %%i IN ('python --version') DO echo  ✅ %%i found

REM ── Install packages ──
echo.
echo  📦 Installing Python packages...
python -m pip install -r requirements.txt --quiet
echo  ✅ Packages installed

REM ── Create start script ──
echo python "%~dp0app.py" > "%~dp0start.bat"

REM ── Add to startup (Task Scheduler - always active) ──
echo.
echo  ⚙  Setting up auto-start on Windows login...

schtasks /create /tn "NetWatch" ^
    /tr "\"%~dp0start_hidden.vbs\"" ^
    /sc ONLOGON ^
    /rl HIGHEST ^
    /f >nul 2>&1

REM ── Create hidden start VBS (runs without CMD window) ──
echo Set oShell = CreateObject("WScript.Shell") > "%~dp0start_hidden.vbs"
echo oShell.Run "python ""%~dp0app.py""", 0, False >> "%~dp0start_hidden.vbs"

echo.
echo  ╔══════════════════════════════════════════╗
echo  ║          ✅  Install Complete!           ║
echo  ╠══════════════════════════════════════════╣
echo  ║  Starting NetWatch now...                ║
echo  ║                                          ║
echo  ║  Dashboard: http://localhost:5000        ║
echo  ║  Username:  admin                        ║
echo  ║  Password:  netwatch123                  ║
echo  ║                                          ║
echo  ║  NetWatch will auto-start on every       ║
echo  ║  Windows login.                          ║
echo  ║                                          ║
echo  ║  To stop: Task Manager → NetWatch        ║
echo  ╚══════════════════════════════════════════╝
echo.

REM ── Start now ──
start "" "%~dp0start_hidden.vbs"
timeout /t 2 /nobreak >nul
start http://localhost:5000

pause
