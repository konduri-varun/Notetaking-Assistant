@echo off
echo ================================================
echo   AI Meeting Notes - Frontend
echo ================================================
echo.

cd frontend

echo Activating virtual environment...
call ..\nylas\Scripts\activate.bat

echo Starting frontend server...
echo Frontend will be available at: http://localhost:3000
echo.

python -m http.server 3000
