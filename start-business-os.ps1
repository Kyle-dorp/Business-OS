$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = "C:\Python314\python.exe"

function Port-IsRunning([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

if (-not (Port-IsRunning 8000)) {
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}

if (-not (Port-IsRunning 5173)) {
    Start-Process -FilePath $python `
        -ArgumentList "-m", "http.server", "5173", "--bind", "127.0.0.1" `
        -WorkingDirectory (Join-Path $PSScriptRoot "frontend\dist") -WindowStyle Hidden
}

Write-Host "Starting Bam's Sub Shoppe Business OS..." -ForegroundColor Cyan

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $api = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        $site = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5173" -TimeoutSec 2
        if ($api.status -eq "ok" -and $site.StatusCode -eq 200) {
            Write-Host "Ready! Opening browser..." -ForegroundColor Green
            break
        }
    } catch { Start-Sleep -Seconds 1 }
}

Start-Process "http://127.0.0.1:5173"
