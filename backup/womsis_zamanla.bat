@echo off
chcp 1252 >nul
echo.
echo =====================================================
echo  WOMSIS Otomatik Zamanlama Kurulumu
echo =====================================================
echo.
echo Senkronizasyon saatini girin (varsayilan: 00:00)
echo Ornek: 00:00 (gece yaris) veya 08:30 (sabah 8:30)
echo.
set /p SAAT="Saat (bos bırakırsanız 00:00 olur): "

if "%SAAT%"=="" set SAAT=00:00

echo.
echo [*] Kopyalanacak script: womsis_sync.bat
set DEST=C:\FPPRO\webadmin-nakitakim\womsis_sync.bat
copy "%~dp0womsis_sync.bat" "%DEST%" >nul 2>&1
echo [OK] Script kopyalandi: %DEST%

echo.
echo [*] Mevcut womsis-sync gorevi siliniyor (varsa)...
schtasks /delete /tn "womsis-sync" /f >nul 2>&1

echo [*] Yeni gorev olusturuluyor: Her gece %SAAT%...
schtasks /create ^
  /tn "womsis-sync" ^
  /tr "%DEST%" ^
  /sc daily ^
  /st %SAAT% ^
  /ru SYSTEM ^
  /f

if errorlevel 1 (
    echo [HATA] Gorev olusturulamadi!
) else (
    echo [OK] Gorev olusturuldu: Her gece %SAAT%'de WOMSIS senkronizasyonu
)

echo.
echo [*] Simdi manuel test yapmak ister misiniz?
set /p TEST="Evet icin E, Hayir icin H: "
if /i "%TEST%"=="E" (
    echo [*] Manuel test baslatiliyor...
    call "%DEST%"
    echo [OK] Test tamamlandi. Log: C:\FPPRO\webadmin-nakitakim\womsis_sync.log
)

echo.
echo =====================================================
echo  TAMAMLANDI!
echo  Zamanlama: Her gece saat %SAAT%
echo  Log dosyasi: C:\FPPRO\webadmin-nakitakim\womsis_sync.log
echo =====================================================
echo.
echo Zamanlama Gorevi Yonetimi icin:
echo  - Gormek:   schtasks /query /tn "womsis-sync"
echo  - Silmek:   schtasks /delete /tn "womsis-sync" /f
echo  - Manuel:   schtasks /run /tn "womsis-sync"
echo.
pause
