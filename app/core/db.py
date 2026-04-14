import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash
from flask import session, has_request_context

# Definindo o caminho pro banco SQLite globalmente
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'database.sqlite')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tabela principal para cruzar histórico de clientes importados
    # Usa 'telefone + data_vencimento' como chave composta única
    c.execute('''
        CREATE TABLE IF NOT EXISTS client_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefone TEXT NOT NULL,
            data_vencimento TEXT NOT NULL,
            observacao TEXT DEFAULT '',
            is_sent BOOLEAN DEFAULT 0,
            last_updated DATETIME
        )
    ''')
    
    # Evita duplicação do mesmo cliente com a mesma conta
    c.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_client_data ON client_data(telefone, data_vencimento)
    ''')
    
    # Tabela de registros para auditoria (logs)
    c.execute('''
        CREATE TABLE IF NOT EXISTS action_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            action_type TEXT NOT NULL,
            details TEXT,
            client_phone TEXT,
            client_name TEXT,
            username TEXT
        )
    ''')
    
    # Adicionar a coluna username em bancos antigos caso não exista
    c.execute("PRAGMA table_info(action_logs)")
    columns = [row[1] for row in c.fetchall()]
    if 'username' not in columns:
        c.execute("ALTER TABLE action_logs ADD COLUMN username TEXT")
        
    # Nova Tabela de Usuários (Autenticação)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Criar um administrador padrão (admin / admin123) se a tabela estiver vazia
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                  ("admin", generate_password_hash("admin123"), "admin"))
    
    # Tabela de configurações (com textos de templates)
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Nova Tabela de Customers (Cadastros Completos)
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_completo TEXT NOT NULL,
            cpf TEXT UNIQUE,
            whatsapp TEXT NOT NULL,
            endereco TEXT,
            outros_dados TEXT,
            lgpd_consent BOOLEAN DEFAULT 0,
            assigned_to TEXT,
            email TEXT,
            cep TEXT,
            bairro TEXT,
            cidade TEXT,
            estado TEXT,
            numero TEXT,
            complemento TEXT,
            data_nascimento TEXT,
            profissao TEXT,
            como_conheceu TEXT,
            preferencias TEXT,
            historico_compras TEXT,
            objetivo_compra TEXT,
            desafios TEXT,
            orcamento TEXT,
            restricoes_entrega TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Adicionar colunas em bancos antigos caso não existam
    c.execute("PRAGMA table_info(customers)")
    customer_columns = [row[1] for row in c.fetchall()]
    
    new_columns = {
        'assigned_to': 'TEXT',
        'email': 'TEXT',
        'cep': 'TEXT',
        'bairro': 'TEXT',
        'cidade': 'TEXT',
        'estado': 'TEXT',
        'numero': 'TEXT',
        'complemento': 'TEXT',
        'data_nascimento': 'TEXT',
        'profissao': 'TEXT',
        'como_conheceu': 'TEXT',
        'preferencias': 'TEXT',
        'historico_compras': 'TEXT',
        'objetivo_compra': 'TEXT',
        'desafios': 'TEXT',
        'orcamento': 'TEXT',
        'restricoes_entrega': 'TEXT'
    }
    
    for col_name, col_type in new_columns.items():
        if col_name not in customer_columns:
            c.execute(f"ALTER TABLE customers ADD COLUMN {col_name} {col_type}")

    # Nova Tabela de CRM
    
    # Popula templates padrão se não existir configurações prévias (Cobrança)
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("msg_lembrete", "Olá {nome}, tudo bem? Passando para lembrar que sua fatura de R$ {valor} vence no dia {vencimento}. Qualquer dúvida, estamos à disposição!"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("msg_hoje", "Olá {nome}! Lembramos que o vencimento da sua fatura no valor de R$ {valor} é hoje ({vencimento}). Ignore esta mensagem caso já tenha pago."))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("msg_atraso_leve", "Olá {nome}. Não identificamos o pagamento da sua fatura de R$ {valor} vencida em {vencimento}. Houve algum problema? Segue nossa chave Pix / Link para regularização."))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("msg_atraso_grave", "Olá {nome}. Sua fatura de R$ {valor} vencida em {vencimento} encontra-se pendente em nosso sistema. Temos condições especiais para regularização, podemos conversar?"))
              
    # Popula templates padrão para CRM (Funil de Vendas)
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_aquisicao", "Olá {nome}! Vimos que você se interessou pelos nossos serviços. Como podemos ajudar?"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_nutricao", "Olá {nome}, preparamos novidades exclusivas que combinam com seu perfil. Vem conferir!"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_oferta", "Olá {nome}! Temos uma oferta especial pra você que é nosso cliente. Condições imperdíveis hoje!"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_posvenda", "Olá {nome}! O que achou da sua última compra com a gente no dia {ultcompra}? Seu feedback é muito importante!"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_recuperacao", "Olá {nome}! Sentimos sua falta. Preparamos uma condição super exclusiva para a sua volta, vamos aproveitar?"))
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("crm_msg_aniversario", "Parabéns, {nome}! Que o seu dia {nascimento} seja muito especial! E para comemorar, temos um presente para você!"))

    # Popula template padrão para LGPD (Promoção)
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", 
              ("promo_lgpd_text", "Declaro que concordo com a coleta e tratamento dos meus dados pessoais (Nome, CPF, Whatsapp e Endereço) para fins de participação em sorteios e promoções da loja, bem como com o recebimento de comunicações via WhatsApp, em conformidade com a Lei Geral de Proteção de Dados (LGPD - Lei 13.709/18). Estou ciente de que posso revogar este consentimento a qualquer momento."))

    
    conn.commit()
    conn.close()

def log_action(action_type, details, client_phone=None, client_name=None):
    try:
        # Pega o usuário logado se existir, caso contrário registra como Sistema/Desconhecido
        current_user = session.get('username', 'Sistema') if has_request_context() else 'Sistema'
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('''
            INSERT INTO action_logs (timestamp, action_type, details, client_phone, client_name, username)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action_type, details, client_phone, client_name, current_user))
        conn.commit()
        
        # Também loga em arquivo de texto para requisitos do usuário
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'operation_logs.txt')
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}] [{current_user}] {action_type} - {details} (Cliente: {client_name or 'N/A'})\n")
            
    except Exception as e:
        print(f"Erro ao salvar log: {e}")
    finally:
        if 'conn' in locals():
            conn.close()
