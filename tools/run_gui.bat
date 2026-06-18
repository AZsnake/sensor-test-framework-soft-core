@echo off
cd /d "%~dp0"
python gui\main.py
if errorlevel 1 pause
