@echo off
cd /d "%~dp0"
python backup.py verify
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
