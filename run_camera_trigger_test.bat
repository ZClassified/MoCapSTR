@echo off
title MoCapSTR - Hardware Trigger Diagnose
cd /d "%~dp0"
echo Starte Kamera-Trigger-Diagnose...
echo.
python arduino/test_camera_trigger.py
pause
