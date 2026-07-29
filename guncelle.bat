@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM ─────────────────────────────────────────────────────────────────────────────
REM  guncelle.bat  —  nakitakim GitHub güncelleme + log aracı
REM  Windows 2012 Server uyumlu ANSI renkli script
REM ─────────────────────────────────────────────────────────────────────────────

REM VT100/ANSI modunu etkinlestir (Windows 10+; 2012'de terminal destekliyorsa calısır)
reg add "HKCU\Console" /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1

REM ESC karakterini olustur
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"

set "GRN=!ESC![92m"
set "RED=!ESC![91m"
set "YEL=!ESC![93m"
set "CYN=!ESC![96m"
set "BLU=!ESC![94m"
set "MAG=!ESC![95m"
set "WHT=!ESC![97m"
set "GRY=!ESC![90m"
set "BLD=!ESC![1m"
set "RST=!ESC![0m"
set "LINE=!ESC![90m────────────────────────────────────────────────────────────────!ESC![0m"

REM ── Log klasörü ve dosyası ───────────────────────────────────────────────────
set "LOGDIR=%~dp0logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Tarih: YYYYMMDD_HHMMSS
set "DT=%date:~6,4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "DT=%DT: =0%"
set "LOGFILE=%LOGDIR%\gitpull_%DT%.log"

REM ── Başlık ───────────────────────────────────────────────────────────────────
title nakitakim — GitHub Güncelleme
cls
echo.
echo !BLD!!CYN!  ╔═══════════════════════════════════════════════════════════╗!RST!
echo !BLD!!CYN!  ║          nakitakim  —  GitHub Güncelleme Aracı           ║!RST!
echo !BLD!!CYN!  ╚═══════════════════════════════════════════════════════════╝!RST!
echo.
echo  !GRY!Tarih   : !WHT!%date% %time%!RST!

REM ── Repo klasörünü belirle ───────────────────────────────────────────────────
set "REPO_DIR=%~dp0"
REM Sondaki \ karakterini kaldir
if "%REPO_DIR:~-1%"=="\" set "REPO_DIR=%REPO_DIR:~0,-1%"

REM .git klasörü burada var mi?
if not exist "%REPO_DIR%\.git" (
    echo.
    echo  !YEL!  Uyarı: .git klasörü bulunamadı: %REPO_DIR%!RST!
    echo  !GRY!  Olası nakitakim konumları aranıyor...!RST!
    for %%P in (
        "C:\nakitakim"
        "C:\Users\Administrator\nakitakim"
        "C:\Users\Administrator\Documents\nakitakim"
        "D:\nakitakim"
        "C:\webadmin\nakitakim"
    ) do (
        if exist "%%~P\.git" (
            set "REPO_DIR=%%~P"
            echo  !GRN!  ✔  Klasör bulundu: %%~P!RST!
            goto :FOUND
        )
    )
    echo  !RED!  ✘  nakitakim klasörü bulunamadı!!RST!
    echo  !YEL!  → Bu bat dosyasını nakitakim ana klasörüne koyun.!RST!
    goto :END
)

:FOUND
echo  !GRY!Klasör  : !WHT!%REPO_DIR%!RST!
echo  !GRY!Log     : !WHT!%LOGFILE%!RST!
echo.
echo %LINE%

REM Log başlığı
echo ============================================================ > "%LOGFILE%"
echo   nakitakim git pull - %date% %time% >> "%LOGFILE%"
echo   Klasor: %REPO_DIR% >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

cd /d "%REPO_DIR%"

REM ── 1. Mevcut durum ──────────────────────────────────────────────────────────
echo.
echo  !BLD!!WHT![1/5] Mevcut durum kontrol ediliyor...!RST!
echo.

for /f "tokens=*" %%i in ('git branch --show-current 2^>^&1') do set "BRANCH=%%i"
for /f "tokens=*" %%i in ('git log --oneline -1 2^>^&1') do set "CURRENT_COMMIT=%%i"

echo   !GRY!Branch    : !GRN!!BRANCH!!RST!
echo   !GRY!Son commit: !YEL!!CURRENT_COMMIT!!RST!
echo.
echo   Branch: !BRANCH! >> "%LOGFILE%"
echo   Onceki commit: !CURRENT_COMMIT! >> "%LOGFILE%"

REM ── 2. Fetch ─────────────────────────────────────────────────────────────────
echo  !BLD!!WHT![2/5] GitHub'dan bilgiler alınıyor (fetch)...!RST!
echo.
git fetch origin >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    echo   !RED!  ✘  FETCH BAŞARISIZ!!RST!
    echo   !GRY!  İnternet veya GitHub erişimini kontrol edin.!RST!
    echo   [HATA] fetch basarisiz >> "%LOGFILE%"
    goto :SHOW_LOG
)
echo   !GRN!  ✔  Fetch tamamlandı!RST!
echo.

REM ── 3. Yeni commit var mı? ───────────────────────────────────────────────────
echo  !BLD!!WHT![3/5] Yeni commitler kontrol ediliyor...!RST!
echo.
set "HAS_NEW=0"
for /f "tokens=*" %%i in ('git log --oneline HEAD..origin/!BRANCH! 2^>^&1') do (
    echo   !CYN!  ↓  %%i!RST!
    echo   Yeni: %%i >> "%LOGFILE%"
    set "HAS_NEW=1"
)
if "!HAS_NEW!"=="0" (
    echo   !GRN!  ✔  Zaten güncel — GitHub'da yeni commit yok.!RST!
    echo   Zaten guncel >> "%LOGFILE%"
)
echo.

REM ── 4. Pull ──────────────────────────────────────────────────────────────────
echo  !BLD!!WHT![4/5] Güncelleme indiriliyor (pull)...!RST!
echo.
git pull origin !BRANCH! >> "%LOGFILE%" 2>&1
set "PULL_ERR=!errorlevel!"
if !PULL_ERR! neq 0 (
    echo   !RED!  ✘  PULL BAŞARISIZ! ^(hata kodu: !PULL_ERR!^)!RST!
    echo   !YEL!  → Eğer conflict varsa: git stash → git pull!RST!
    echo   [HATA] pull basarisiz, kod !PULL_ERR! >> "%LOGFILE%"
) else (
    echo   !GRN!  ✔  Pull başarıyla tamamlandı!!RST!
    echo   [OK] pull tamamlandi >> "%LOGFILE%"
)
echo.

REM ── 5. Son commitler ─────────────────────────────────────────────────────────
echo  !BLD!!WHT![5/5] Son 6 commit:!RST!
echo.
echo %LINE%
echo   Son commitler: >> "%LOGFILE%"

set IDX=0
for /f "tokens=1,* delims= " %%a in ('git log --oneline -6 2^>^&1') do (
    set /a IDX+=1
    if !IDX! equ 1 (
        echo   !GRN!  ● %%a !WHT!%%b!RST!  !GRY!← güncel!RST!
    ) else (
        echo   !GRY!  ○ %%a %%b!RST!
    )
    echo     %%a %%b >> "%LOGFILE%"
)
echo %LINE%
echo.

REM ── Son pull'da değişen dosyalar ─────────────────────────────────────────────
echo  !BLD!!WHT!  Son güncellemeyle değişen dosyalar:!RST!
echo.
set "CHANGED=0"
for /f "tokens=*" %%f in ('git diff --name-only HEAD~1 HEAD 2^>^&1') do (
    echo   !CYN!  ✎  %%f!RST!
    echo   Degisen: %%f >> "%LOGFILE%"
    set "CHANGED=1"
)
if "!CHANGED!"=="0" (
    echo   !GRY!  (değişen dosya yok — zaten günceldi)!RST!
)
echo.

:SHOW_LOG
REM ── Sonuç özeti ──────────────────────────────────────────────────────────────
echo %LINE%
if !PULL_ERR! equ 0 (
    echo  !BLD!!GRN!  ✔  GÜNCELLEME BAŞARILI!RST!
) else (
    echo  !BLD!!RED!  ✘  GÜNCELLEME BAŞARISIZ — log dosyasına bakın!RST!
)
echo  !GRY!  Log: !WHT!%LOGFILE%!RST!
echo %LINE%
echo.

REM ── webadmin yeniden başlatma teklifi ────────────────────────────────────────
if !PULL_ERR! equ 0 (
    echo  !YEL!  webadmin_app.py sunucusunu yeniden başlatmak ister misiniz?!RST!
    echo  !GRY!  ^(E = Evet, H = Hayır^)!RST!
    set /p "RESTART=  Seçiminiz [E/H]: "
    if /i "!RESTART!"=="E" (
        echo.
        echo  !MAG!  webadmin yeniden başlatılıyor...!RST!

        REM Port 5050'de çalışan process'i kapat
        for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5050 "') do (
            if "%%p" neq "" (
                echo   !GRY!PID %%p kapatılıyor...!RST!
                taskkill /PID %%p /F >nul 2>&1
            )
        )
        timeout /t 2 /nobreak >nul

        REM Yeni process başlat
        if exist "%REPO_DIR%\webadmin_app.py" (
            start "webadmin-nakitakim" /MIN cmd /c ^
                "python \"%REPO_DIR%\webadmin_app.py\" >> \"%LOGDIR%\webadmin_app.log\" 2>&1"
            echo.
            echo   !GRN!  ✔  webadmin başlatıldı (port 5050)!RST!
            echo   !GRY!  Log: %LOGDIR%\webadmin_app.log!RST!
            echo   [OK] webadmin yeniden baslatildi >> "%LOGFILE%"
        ) else (
            echo   !RED!  ✘  webadmin_app.py bulunamadı!RST!
        )
    )
)

:END
echo.
echo  !GRY!Kapatmak için bir tuşa basın...!RST!
pause >nul
endlocal
