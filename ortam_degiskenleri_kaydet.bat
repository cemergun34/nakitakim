@echo off
chcp 1252 >nul
title Sistem Ortam Degiskenleri - webadmin-nakitakim

echo.
echo =============================================
echo  Sistem Ortam Degiskenleri Ayarlaniyor
echo  (Admin yetkisi gereklidir)
echo =============================================
echo.

REM PostgreSQL
setx PG_HOST 127.0.0.1 /M
setx PG_PORT 5432 /M
setx PG_DB neondb /M
setx PG_USER postgres /M
setx PG_PASS 123 /M
setx PG_SSLMODE disable /M

REM Flask / webadmin
setx WEBADMIN_SECRET_KEY FpproGizliAnahtar2024XYZ /M
setx WEBADMIN_PORT 5050 /M
setx WEBADMIN_HOST 0.0.0.0 /M
setx WEBADMIN_API_KEY nakit-akim-api-key-2024-secure /M
setx WEBADMIN_DEBUG false /M

REM Python
setx PYTHONIOENCODING utf-8 /M
setx PYTHONUNBUFFERED 1 /M

echo.
echo =============================================
echo  TAMAMLANDI!
echo  CMD pencerelerini kapatip yeniden acin.
echo  Artik her yerden python app.py calisir.
echo =============================================
echo.
pause
