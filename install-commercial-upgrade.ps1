Set-Location $PSScriptRoot

if (Test-Path ".\schedule_assistant.db") {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item ".\schedule_assistant.db" ".\schedule_assistant.db.backup-$stamp"
    Write-Host "Database backup created."
}

if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    . ".\.venv\Scripts\Activate.ps1"
}

Write-Host "Installing Python requirements..."
python -m pip install -r requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env. Add your OpenAI API key there."
}

$envText = Get-Content ".env" -Raw
if ($envText -notmatch "(?m)^JWT_SECRET=") {
    $secret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    Add-Content ".env" "`nJWT_SECRET=$secret"
    Write-Host "Added a secure local login secret to .env."
}

Write-Host "Upgrade installed. Start the backend and frontend in separate VS Code terminals."
