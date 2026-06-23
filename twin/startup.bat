@echo off
echo ========================================
echo  Hermes Twin Bridge — Startup
echo ========================================
echo.
echo 1. Launching Hermes Twin...
start "Hermes Twin" hermes
echo.
echo 2. Starting WhatsApp bridge...
start "WhatsApp" hermes whatsapp
echo.
echo 3. Starting Redis worker...
pip install redis -q
python worker.py
echo.
pause
