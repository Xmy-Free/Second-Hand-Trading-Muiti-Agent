# 校园二手交易 Multi-Agent 平台 · Windows 一键启动
# 用法：在项目根目录右键“使用 PowerShell 运行”，或：powershell -ExecutionPolicy Bypass -File .\start-all.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Py = Join-Path $Backend ".venv\Scripts\python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  校园二手交易 Multi-Agent 平台 · 一键启动" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1) 依赖检查
if (-not (Test-Path $Py)) {
    Write-Host "[1/4] 创建后端虚拟环境并安装依赖..." -ForegroundColor Yellow
    python -m venv (Join-Path $Backend ".venv")
    & $Py -m pip install -r (Join-Path $Backend "requirements.txt")
} else {
    Write-Host "[1/4] 后端虚拟环境已就绪" -ForegroundColor Green
}

if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Host "[2/4] 安装前端依赖（首次较慢）..." -ForegroundColor Yellow
    Push-Location $Frontend
    npm.cmd install
    Pop-Location
} else {
    Write-Host "[2/4] 前端依赖已就绪" -ForegroundColor Green
}

# 2) 首次启动自动建表 + 播种（由后端 lifespan 完成，这里只做提示）
Write-Host "[3/4] 数据库将在后端启动时自动初始化并播种（含作者账号 2400320321）" -ForegroundColor Green

# 3) 启动后端（新窗口）
Write-Host "[4/4] 启动后端 FastAPI (http://localhost:8000) 与前端 Vite (http://localhost:5173)..." -ForegroundColor Yellow
Start-Process -FilePath $Py -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" -WorkingDirectory $Backend -WindowStyle Normal
Start-Sleep -Seconds 4
Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory $Frontend -WindowStyle Normal

Start-Sleep -Seconds 6
Start-Process "http://localhost:5173/login"
Write-Host ""
Write-Host "启动完成：" -ForegroundColor Green
Write-Host "  前端：http://localhost:5173" -ForegroundColor White
Write-Host "  后端文档：http://localhost:8000/docs" -ForegroundColor White
Write-Host "  默认密码全部为 123456" -ForegroundColor White
Write-Host "  关闭服务：关闭弹出的两个命令行窗口即可" -ForegroundColor Gray
