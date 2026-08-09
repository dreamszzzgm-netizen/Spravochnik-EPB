@echo off
cd /d "%~dp0"
setlocal

set "BACKEND_PORT=8000"
set "FRONTEND_PORT=3000"
set "DATABASE_URL=postgresql+psycopg://spravoshnik:spravoshnik@127.0.0.1:5432/spravoshnik"
set "BACKEND_ORIGIN=http://127.0.0.1:%BACKEND_PORT%"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python environment not found: .venv\Scripts\python.exe
    pause
    exit /b 1
)

if not exist "frontend\package.json" (
    echo [ERROR] Frontend not found: frontend\package.json
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies...
    pushd frontend
    call npm ci
    if errorlevel 1 (
        popd
        echo [ERROR] npm ci failed.
        pause
        exit /b 1
    )
    popd
)

netstat -ano | findstr /R /C:":3000 .*LISTENING" >nul
if not errorlevel 1 (
    set "FRONTEND_PORT=3100"
    echo [WARN] Port 3000 is occupied. Frontend will use port 3100.
)

where docker >nul 2>nul
if not errorlevel 1 (
    echo [INFO] Starting PostgreSQL...
    docker compose up -d postgres
) else (
    echo [WARN] Docker not found. Backend will use an already running PostgreSQL.
)

echo.
echo ============================================
echo   Spravoshnik-EPB
echo   Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo   Backend:  http://127.0.0.1:%BACKEND_PORT%
echo   API docs: http://127.0.0.1:%BACKEND_PORT%/api/docs
echo ============================================
echo.

start "Spravoshnik Backend" cmd /k "cd /d ""%~dp0"" && set ""DATABASE_URL=%DATABASE_URL%"" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT%"
start "Spravoshnik Frontend" cmd /k "cd /d ""%~dp0frontend"" && set ""BACKEND_ORIGIN=%BACKEND_ORIGIN%"" && npm run dev -- --hostname 127.0.0.1 --port %FRONTEND_PORT%"

echo Servers are starting in separate windows.
echo Close those windows or press Ctrl+C in each one to stop the project.
timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:%FRONTEND_PORT%"

endlocal
