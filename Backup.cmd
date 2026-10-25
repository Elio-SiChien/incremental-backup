@echo off
cd /d "%~dp0"
echo This copies SOURCE to DESTINATION and archives overwritten files.
echo Close applications editing your data. Review Preview.cmd first.
choice /c YN /n /m "Run backup now? [Y/N] "
if errorlevel 2 exit /b 0
python backup.py run
set "RESULT=%ERRORLEVEL%"
pause
exit /b %RESULT%
