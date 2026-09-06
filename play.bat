@echo off
setlocal
cd /d "%~dp0"
set "HEXXAGON_PYTHON=python"
if exist ".venv\Scripts\python.exe" set "HEXXAGON_PYTHON=.venv\Scripts\python.exe"
"%HEXXAGON_PYTHON%" main.py %*
if errorlevel 1 pause
