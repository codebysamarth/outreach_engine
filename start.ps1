# Outreach Engine - Start Script
# Runs both backend and frontend in separate terminals

Write-Host "🚀 Starting Outreach Engine..." -ForegroundColor Cyan
Write-Host ""

# Check if services are running
Write-Host "Checking Docker services..." -ForegroundColor Yellow
docker ps | Select-String "outreach" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Starting Docker services..." -ForegroundColor Yellow
    docker compose up -d
    Start-Sleep -Seconds 5
}

Write-Host "✓ Docker services running" -ForegroundColor Green
Write-Host ""

# Start backend in new terminal
Write-Host "Starting Backend API on port 8080..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD'; .\venv\Scripts\Activate.ps1; python -m uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8080"

Start-Sleep -Seconds 3

# Start frontend in new terminal
Write-Host "Starting Frontend on port 5173..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PWD\frontend'; npm run dev"

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "✅ Application started!" -ForegroundColor Green
Write-Host ""
Write-Host "Backend API:  http://localhost:8080" -ForegroundColor White
Write-Host "Frontend UI:  http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Opening browser..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"
