$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Business OS - Connect Claude" -ForegroundColor Cyan
Write-Host "Your key will be hidden while you type and saved only on this computer."
Write-Host ""

$secureKey = Read-Host "Paste your Anthropic API key, then press Enter" -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
}

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "No key was entered. Nothing changed." -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit 1
}

if (-not $apiKey.StartsWith("sk-ant-")) {
    Write-Host "That does not look like an Anthropic API key." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

$envPath = Join-Path $PSScriptRoot ".env"
$envText = if (Test-Path $envPath) { Get-Content $envPath -Raw } else { Get-Content ".env.example" -Raw }

if ($envText -match "(?m)^ANTHROPIC_API_KEY=") {
    $envText = $envText -replace "(?m)^ANTHROPIC_API_KEY=.*$", "ANTHROPIC_API_KEY=$apiKey"
} else {
    $envText += "`r`nANTHROPIC_API_KEY=$apiKey"
}
if ($envText -notmatch "(?m)^ANTHROPIC_MODEL=") {
    $envText += "`r`nANTHROPIC_MODEL=claude-sonnet-4-5"
}
if ($envText -notmatch "(?m)^JWT_SECRET=") {
    $secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    $envText += "`r`nJWT_SECRET=$secret"
}

Set-Content -LiteralPath $envPath -Value $envText -Encoding UTF8
$apiKey = $null

Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $PSScriptRoot -WindowStyle Hidden

Start-Sleep -Seconds 4
try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
    if ($health.ai_configured) {
        Write-Host "Claude is connected to Business OS." -ForegroundColor Green
    } else {
        Write-Host "The key was saved, but the app did not detect it. Ask Codex for help." -ForegroundColor Yellow
    }
} catch {
    Write-Host "The key was saved, but the app could not restart. Ask Codex for help." -ForegroundColor Yellow
}

Read-Host "Press Enter to close"
