import os
import pandas as pd
from datetime import datetime
import urllib.parse
from app.core.file_parsers import read_data_file
from app.core.db import get_db_connection, log_action

def get_message_templates():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings")
    templates = {row['key']: row['value'] for row in c.fetchall()}
    conn.close()
    return templates

def process_clients(file_path):
    groups = {
        "lembrete": [],
        "hoje": [],
        "atraso_leve": [],
        "atraso_grave": []
    }
    
    if not file_path or not os.path.exists(file_path):
        return groups, "Arquivo não encontrado."
    
    df = read_data_file(file_path)
    if df is None or df.empty:
        return groups, "Não foi possível ler as informações ou o arquivo está vazio."
    
    colunas_obrigatorias = ["Nome", "Telefone", "Valor", "Vencimento"]
    for col in colunas_obrigatorias:
        if col not in df.columns:
            return groups, f"A coluna '{col}' não foi encontrada na planilha. Verifique o cabeçalho."

    df = df.loc[:,~df.columns.duplicated()].copy()
    
    df = df.dropna(subset=colunas_obrigatorias).copy()
    df['Nome'] = df['Nome'].astype(str).str.strip()
    df['Telefone'] = df['Telefone'].astype(str).str.strip()
    
    df = df[(df['Nome'] != '') & (df['Nome'] != 'nan') & (df['Telefone'] != '') & (df['Telefone'] != 'nan')]
    
    today = datetime.now().date()
    
    df['Vencimento_dt'] = pd.to_datetime(df['Vencimento'], format='mixed', dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Vencimento_dt']).copy()
    
    df['days_diff'] = df['Vencimento_dt'].apply(lambda x: (x - today).days)
    
    df['group_key'] = ''
    df.loc[(df['days_diff'] > 0) & (df['days_diff'] <= 3), 'group_key'] = 'lembrete'
    df.loc[df['days_diff'] == 0, 'group_key'] = 'hoje'
    df.loc[(df['days_diff'] < 0) & (df['days_diff'] >= -15), 'group_key'] = 'atraso_leve'
    df.loc[df['days_diff'] < -15, 'group_key'] = 'atraso_grave'
    
    df = df[df['group_key'] != ''].copy()
    df = df.reset_index(drop=True)
    
    def format_valor(v):
        try:
            if isinstance(v, str):
                v = float(v.replace('.', '').replace(',', '.'))
            else:
                v = float(v)
            return f"{v:,.2f}".replace(",", "v").replace(".", ",").replace("v", ".")
        except:
            return str(v)
            
    df['Valor_str'] = df['Valor'].apply(format_valor)
    df['Data_str'] = pd.to_datetime(df['Vencimento_dt']).dt.strftime("%d/%m/%Y")
    
    def clean_phone(p):
        cl = ''.join(filter(str.isdigit, str(p)))
        if not cl:
            return "", False
            
        if cl.startswith("55") and len(cl) >= 12:
            cl = cl[2:]
            
        if cl.startswith("0") and len(cl) >= 11:
            cl = cl[1:]
            
        if len(cl) in (10, 11):
            ddd = cl[:2]
            numero = cl[2:]
        elif len(cl) in (8, 9):
            ddd = '19'
            numero = cl
        else:
            return cl, False
            
        is_whatsapp = not numero.startswith('3')
        
        return f"55{ddd}{numero}", is_whatsapp
        
    phone_data = df['Telefone'].apply(clean_phone)
    df['telefone_clean'] = phone_data.apply(lambda x: x[0])
    df['is_whatsapp'] = phone_data.apply(lambda x: x[1])
    
    # --- INTEGRAÇÃO COM BANCO DE DADOS ---
    conn = get_db_connection()
    c = conn.cursor()
    
    # Sincronização automática com a tabela customers usando o WhatsApp 
    # (CPFs ficam em branco, aguardando painel de sorteios atualizar)
    unique_clients = df.drop_duplicates(subset=['telefone_clean'])
    for _, r in unique_clients.iterrows():
        n = str(r['Nome']).strip()
        tel = str(r['telefone_clean']).strip()
        if tel:
            c.execute("SELECT id FROM customers WHERE whatsapp = ?", (tel,))
            if not c.fetchone():
                c.execute("INSERT INTO customers (nome_completo, whatsapp) VALUES (?, ?)", (n, tel))
                
    c.execute("SELECT telefone, data_vencimento, observacao, is_sent FROM client_data")
    db_data = c.fetchall()
    conn.close()
    
    # Criar um dicionário de busca rápida baseado no cliente + vencimento
    db_map = {}
    for row in db_data:
        key = f"{row['telefone']}_{row['data_vencimento']}"
        db_map[key] = {
            "obs": row['observacao'],
            "is_sent": bool(row['is_sent'])
        }
        
    templates = get_message_templates()
    
    for _, row in df.iterrows():
        nome, valor_str, data_str = row['Nome'], row['Valor_str'], row['Data_str']
        days_diff, group_key = row['days_diff'], row['group_key']
        clean_phone_val, is_whatsapp = row['telefone_clean'], row['is_whatsapp']
        
        client_key = f"{clean_phone_val}_{data_str}"
        saved_data = db_map.get(client_key, {"obs": "", "is_sent": False})
        
        if group_key == "lembrete":
            message = templates.get("msg_lembrete", "Olá {nome}, tudo bem? Passando para lembrar que sua fatura de R$ {valor} vence no dia {vencimento}. Qualquer dúvida, estamos à disposição!")
        elif group_key == "hoje":
            message = templates.get("msg_hoje", "Olá {nome}! Lembramos que o vencimento da sua fatura no valor de R$ {valor} é hoje ({vencimento}). Ignore esta mensagem caso já tenha pago.")
        elif group_key == "atraso_leve":
            message = templates.get("msg_atraso_leve", "Olá {nome}. Não identificamos o pagamento da sua fatura de R$ {valor} vencida em {vencimento}. Houve algum problema? Segue nossa chave Pix / Link para regularização.")
        else:
            message = templates.get("msg_atraso_grave", "Olá {nome}. Sua fatura de R$ {valor} vencida em {vencimento} encontra-se pendente em nosso sistema. Temos condições especiais para regularização, podemos conversar?")
            
        message = message.format(nome=nome, valor=valor_str, vencimento=data_str)
            
        encoded_msg = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{clean_phone_val}?text={encoded_msg}" if is_whatsapp else ""
        
        groups[group_key].append({
            "nome": nome,
            "telefone": clean_phone_val,
            "valor": valor_str,
            "vencimento": data_str,
            "dias": abs(days_diff),
            "whatsapp_url": whatsapp_url,
            "is_whatsapp": is_whatsapp,
            "mensagem": message,
            "observacao": saved_data["obs"],
            "is_sent": saved_data["is_sent"]
        })
    
    log_action("SISTEMA", f"Planilha processada. {len(df)} clientes analisados.")
    return groups, None
