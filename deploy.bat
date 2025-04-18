@echo off

REM Stop any running instances
taskkill /F /IM python.exe /T

REM Create virtual environment if it doesn't exist
if not exist venv (
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install/update dependencies
pip install -r requirements.txt
pip install gunicorn

REM Create download directory if it doesn't exist
if not exist yt_downloads (
    mkdir yt_downloads
)

REM Set environment variables
set FLASK_ENV=production
set DOWNLOAD_FOLDER=%CD%\yt_downloads

REM Start the application with Gunicorn
gunicorn app:app --bind 0.0.0.0:8000 --workers 4 --timeout 120 --access-logfile - --error-logfile - 