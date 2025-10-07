@echo off
echo ================================================
echo   AI Meeting Notes - Backend Server
echo ================================================
echo.

cd backend

echo Activating virtual environment...
call ..\nylas\Scripts\activate.bat

echo.
echo Starting FastAPI server...
echo Backend will be available at: http://localhost:8000
echo.

uvicorn main:app --reload
