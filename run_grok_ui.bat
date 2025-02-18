@echo off
cd /d %~dp0

echo Checking for running Streamlit instances...
taskkill /F /IM "streamlit.exe" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Streamlit" >nul 2>&1

echo Starting Grok UI from virtual environment...
venv\Scripts\python.exe -m streamlit run Grok_UI_Util.py --server.port=8502

if errorlevel 1 (
    echo Error starting Streamlit. Please check if virtual environment is activated properly.
    pause
    exit /b 1
)
pause
