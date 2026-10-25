@echo off
cd /d "%~dp0"
python backup.py plan
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
