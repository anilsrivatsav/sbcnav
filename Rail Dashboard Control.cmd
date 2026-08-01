@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\RailDashboardControl.ps1" -Action gui
if errorlevel 1 pause
