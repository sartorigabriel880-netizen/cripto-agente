@echo off
cd /d "%~dp0"
echo Abrindo o painel do agente cripto...
python -m streamlit run painel.py
pause
