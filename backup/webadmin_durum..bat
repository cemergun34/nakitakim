@echo off
chcp 1252 >nul
set WA=C:\FPPRO\webadmin-nakitakim

echo === app.py son 30 satir ===
powershell -Command "Get-Content '%WA%\app.py' | Select-Object -Last 30"

echo.
echo === templates klasoru ===
dir "%WA%\templates" /b

echo.
echo === womsis_timer_src.html var mi? ===
if exist "%WA%\womsis_timer_src.html" (echo VAR) else (echo YOK)
if exist "%WA%\templates\womsis_timer.html" (echo templates/womsis_timer.html VAR) else (echo templates/womsis_timer.html YOK)

echo.
echo === Port 5050 calisiyor mu? ===
netstat -ano | findstr ":5050"

pause
