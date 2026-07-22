@echo off
chcp 1252 >nul

:: Log dosyasi
set LOG=C:\FPPRO\webadmin-nakitakim\womsis_sync.log
echo [%date% %time%] WOMSIS senkronizasyonu basliyor... >> %LOG%

:: Webadmin API'yi cagir - WOMSIS sync endpoint
set API_URL=http://127.0.0.1:5050
set API_KEY=nakit-akim-api-key-2024-secure

:: PowerShell ile API cagir
powershell -Command "try { $r = Invoke-WebRequest -Uri '%API_URL%/api/womsis/sync' -Method POST -Headers @{'X-API-Key'='%API_KEY%'} -TimeoutSec 300; Write-Host $r.StatusCode; $r.Content } catch { Write-Host 'HATA:' $_.Exception.Message }" >> %LOG% 2>&1

echo [%date% %time%] Senkronizasyon tamamlandi. >> %LOG%
