param (
    [string]$Device = "cpu"
)

$env:TORCH_DEVICE = $Device
Write-Host "Starting backend on $Device..." -ForegroundColor Green

# Start backend
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m uvicorn backend.app.main:app --reload --port 8000"

Write-Host "Starting frontend..." -ForegroundColor Green
Set-Location frontend
Start-Process -NoNewWindow -FilePath "npm" -ArgumentList "run dev"

Write-Host "Backend URL: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Frontend URL: http://localhost:5173" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop both." -ForegroundColor Yellow
