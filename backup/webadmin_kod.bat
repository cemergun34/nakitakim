@echo off
chcp 1252 >nul
set LOG=C:\webadmin_kod.txt
set WA=C:\FPPRO\webadmin-nakitakim

echo. > %LOG%
echo === .env DOSYASI === >> %LOG%
type "%WA%\.env" >> %LOG% 2>&1
echo. >> %LOG%

echo === app.py === >> %LOG%
type "%WA%\app.py" >> %LOG% 2>&1
echo. >> %LOG%

echo === config.py === >> %LOG%
type "%WA%\config.py" >> %LOG% 2>&1
echo. >> %LOG%

echo === api klasoru === >> %LOG%
dir "%WA%\api" /b >> %LOG% 2>&1
echo. >> %LOG%

echo === services klasoru === >> %LOG%
dir "%WA%\services" /b >> %LOG% 2>&1
echo. >> %LOG%

echo === db klasoru === >> %LOG%
dir "%WA%\db" /b >> %LOG% 2>&1
echo. >> %LOG%

echo === api dosyalari icerigi === >> %LOG%
for /r "%WA%\api" %%f in (*.py) do (
    echo. >> %LOG%
    echo +++ %%f +++ >> %LOG%
    type "%%f" >> %LOG%
)
echo. >> %LOG%

echo === services dosyalari icerigi === >> %LOG%
for /r "%WA%\services" %%f in (*.py) do (
    echo. >> %LOG%
    echo +++ %%f +++ >> %LOG%
    type "%%f" >> %LOG%
)
echo. >> %LOG%

echo === db dosyalari icerigi === >> %LOG%
for /r "%WA%\db" %%f in (*.py) do (
    echo. >> %LOG%
    echo +++ %%f +++ >> %LOG%
    type "%%f" >> %LOG%
)

echo TAMAMLANDI: %LOG%
start notepad %LOG%
pause
