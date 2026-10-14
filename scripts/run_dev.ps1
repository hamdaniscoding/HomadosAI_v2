param([switch]$Dev)
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Missing .venv at $py - see the from-scratch steps"; exit 1 }
if (-not $env:TORCH_DEVICE) { $env:TORCH_DEVICE = (& $py -c "import torch; print('cuda' if torch.cuda.is_available() else 'cpu')") }

# stop any old server on port 8000
Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

Write-Host "Starting on device: $env:TORCH_DEVICE  ->  http://127.0.0.1:8000"
$fe = $null
if ($Dev) {
  $fe = Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm run dev" `
        -WorkingDirectory (Join-Path $root "frontend") -NoNewWindow -PassThru
  Write-Host "Frontend dev server: http://localhost:5173"
}
try {
  & $py -m uvicorn app.main:app --app-dir (Join-Path $root "backend") --host 127.0.0.1 --port 8000
} finally {
  if ($fe -and -not $fe.HasExited) { taskkill /PID $fe.Id /T /F | Out-Null }
}

