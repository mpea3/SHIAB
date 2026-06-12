@echo off
cd /d "%~dp0"

if not exist config.yaml (
    echo config.yaml not found - copying from config.example.yaml
    copy config.example.yaml config.yaml
)

if not exist data mkdir data

echo Rebuilding and starting SHIAB...
docker compose up --build -d

echo.
echo SHIAB is running at http://localhost:8000
echo.
echo Useful commands:
echo   docker compose logs -f    - follow logs
echo   docker compose down       - stop
echo   docker compose restart    - restart without rebuild
