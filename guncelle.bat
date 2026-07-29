@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

REM VT100/ANSI etkinlestir
reg add "HKCU\Console" /v VirtualTerminalLevel /t REG_DWORD /d 1 /f >nul 2>&1
for /F %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"

set "GRN=!ESC![92m"
set "RED=!ESC![91m"
set "YEL=!ESC![93m"
set "CYN=!ESC![96m"
set "WHT=!ESC![97m"
set "GRY=!ESC![90m"
set "BLD=!ESC![1m"
set "RST=!ESC![0m"
set "LN=!ESC![90m──────────────────────────────────────────────────────────!ESC![0m"

title webadmin-nakitAkim — Git Log

cls
echo.
echo !BLD!!CYN!  webadmin-nakitAkim  —  Git Log Görüntüleyici!RST!
echo !LN!
echo.

REM Bu bat dosyasinin bulundugu klasoru kullan
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"

cd /d "%REPO%"

REM Git kurulu mu?
git --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  !RED!  ✘  git komutu bulunamadi. PATH kontrolü yapın.!RST!
    goto :END
)

REM .git klasörü var mı?
if not exist "%REPO%\.git" (
    echo  !RED!  ✘  .git bulunamadı: %REPO%!RST!
    echo  !YEL!  Bu dosyayı webadmin-nakitAkim klasörüne koyun.!RST!
    goto :END
)

REM ── Branch ve son commit ──────────────────────────────────────────────────────
for /f "tokens=*" %%i in ('git branch --show-current 2^>^&1') do set "BRANCH=%%i"
echo  !GRY!Klasör : !WHT!%REPO%!RST!
echo  !GRY!Branch : !GRN!!BRANCH!!RST!
echo.

REM ── Son 20 commit ────────────────────────────────────────────────────────────
echo  !BLD!!WHT!  Son 20 Commit:!RST!
echo  !LN!
echo.

set IDX=0
for /f "tokens=1,2,* delims= " %%a in ('git log --oneline --no-walk=unsorted -20 --format^="%%h %%ad %%s" --date^=format:"%%d.%%m.%%Y %%H:%%M" 2^>^&1') do (
    set /a IDX+=1
    if !IDX! equ 1 (
        echo   !GRN!!BLD!  #!IDX!  %%a  %%b  %%c!RST!  !GRY!← guncel!RST!
    ) else (
        echo   !GRY!  #!IDX!  %%a  !WHT!%%b  %%c!RST!
    )
)

echo.
echo  !LN!

REM ── Değişen dosyalar (son commit) ────────────────────────────────────────────
echo.
echo  !BLD!!WHT!  Son committe değişen dosyalar:!RST!
echo.
set "HAS=0"
for /f "tokens=*" %%f in ('git diff --name-only HEAD~1 HEAD 2^>^&1') do (
    echo    !CYN!  ✎  %%f!RST!
    set "HAS=1"
)
if "!HAS!"=="0" echo   !GRY!  (yok)!RST!

echo.

REM ── git status kısa özet ──────────────────────────────────────────────────────
echo  !BLD!!WHT!  git status:!RST!
echo.
git status -s 2>&1 | findstr /v "^$" > "%TEMP%\gs.tmp"
set "CNT=0"
for /f "tokens=*" %%l in (%TEMP%\gs.tmp) do (
    echo    !YEL!%%l!RST!
    set /a CNT+=1
)
if !CNT! equ 0 echo   !GRN!  ✔  Temiz — değişen dosya yok!RST!
del "%TEMP%\gs.tmp" >nul 2>&1

echo.
echo  !LN!

:END
echo.
echo  !GRY!  Kapatmak için bir tuşa basın...!RST!
pause >nul
endlocal
