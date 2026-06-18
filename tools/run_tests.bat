@echo off
cd /d "%~dp0"
python -m pytest %*
if errorlevel 1 pause
