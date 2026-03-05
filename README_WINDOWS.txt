=========================================
SISTEMA DE COBRANCAS INTELIGENTE
=========================================

Para rodar este sistema no Windows de forma fácil:

MÉTODO 1: INSTALAÇÃO NOVA (Recomendado)
1. Instale o Python (versão 3.10 ou superior) no Windows. Marque a opção "Add python.exe to PATH" durante a instalação.
2. Copie toda esta pasta (cobranca) para o seu computador Windows.
3. Clique duas vezes no arquivo `setup_windows.bat`. Ele vai instalar tudo sozinho pela primeira vez.
4. Para abrir o sistema das próximas vezes, basta dar dois cliques no `run.bat`.

MÉTODO 2: MANUAL
1. Abra o Prompt de Comando (CMD) dentro da pasta cobranca.
2. Crie um ambiente virtual rodando: python -m venv venv
3. Ative o ambiente virtual: venv\Scripts\activate
4. Instale as dependências: pip install -r requirements.txt
5. Inicie o servidor: python run.py
6. Abra o navegador e acesse: http://localhost:5000
