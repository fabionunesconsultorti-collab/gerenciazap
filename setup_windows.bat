@echo off
echo Instalando o Sistema de Cobranca...
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo Instalacao concluida! Iniciando o sistema...
python run.py
pause
