@echo off
chcp 1252 >nul
echo.
echo =============================================
echo  PostgreSQL Sifre Sifirlama (Otomatik)
echo =============================================
echo.

:: PostgreSQL versiyonunu bul
set PG_VER=
set PG_BIN=
set PG_DATA=

for %%v in (17 16 15 14 13 12) do (
    if exist "C:\Program Files\PostgreSQL\%%v\bin\psql.exe" (
        if "%PG_VER%"=="" (
            set PG_VER=%%v
            set PG_BIN=C:\Program Files\PostgreSQL\%%v\bin
            set PG_DATA=C:\Program Files\PostgreSQL\%%v\data
        )
    )
)

if "%PG_BIN%"=="" (
    echo [HATA] PostgreSQL bulunamadi!
    pause
    exit /b 1
)

echo [OK] PostgreSQL %PG_VER% bulundu
echo.

:: Yedek al
copy "%PG_DATA%\pg_hba.conf" "%PG_DATA%\pg_hba.conf.bak" >nul 2>&1

:: Trust moduna al - boyle sifre istemez
(
echo # Gecici trust modu
echo local   all    all              trust
echo host    all    all    127.0.0.1/32    trust
echo host    all    all    ::1/128         trust
echo host    all    all    0.0.0.0/0       md5
) > "%PG_DATA%\pg_hba.conf"

:: Servisi durdur
sc stop "postgresql-x64-%PG_VER%" >nul 2>&1
net stop "postgresql-x64-%PG_VER%" >nul 2>&1

echo [*] Bekleniyor (10 saniye)...
timeout /t 10 /nobreak >nul

:: Servisi baslat
sc start "postgresql-x64-%PG_VER%" >nul 2>&1
net start "postgresql-x64-%PG_VER%" >nul 2>&1

echo [*] Servis basliyor (15 saniye bekleniyor)...
timeout /t 15 /nobreak >nul

:: PGPASSWORD bos olunca trust modda sifre sormaz
set PGPASSWORD=

echo [*] Sifre '123' yapiliyor...
"%PG_BIN%\psql.exe" -U postgres -h 127.0.0.1 -p 5432 -d postgres -c "ALTER USER postgres WITH PASSWORD '123';"

echo [*] Superadmin duzeltiliyor...
"%PG_BIN%\psql.exe" -U postgres -h 127.0.0.1 -p 5432 -d neondb -c "UPDATE uyelik SET musterino=1 WHERE kullanici_adi='superadmin';"

:: Orjinal pg_hba.conf geri yukle
copy "%PG_DATA%\pg_hba.conf.bak" "%PG_DATA%\pg_hba.conf" >nul 2>&1
echo [OK] pg_hba.conf orjinaline dondu

:: Son restart
sc stop "postgresql-x64-%PG_VER%" >nul 2>&1
timeout /t 8 /nobreak >nul
sc start "postgresql-x64-%PG_VER%" >nul 2>&1
timeout /t 10 /nobreak >nul

:: Test - artik sifre 123
set PGPASSWORD=123
echo [*] Test ediliyor (sifre: 123)...
"%PG_BIN%\psql.exe" -U postgres -h 127.0.0.1 -p 5432 -d neondb -c "SELECT 'TAMAMLANDI - Sifre 123 calisiyor!' AS SONUC;"

echo.
echo =============================================
echo  BITTI! Hicbir sifre girmenize gerek yoktu.
echo =============================================
pause
