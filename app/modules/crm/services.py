import os
import pandas as pd
from datetime import datetime
import urllib.parse
from app.core.file_parsers import read_data_file
from app.core.db import get_db_connection

def get_crm_templates():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT key, value FROM settings WHERE key LIKE 'crm_%'")
    templates = {row['key']: row['value'] for row in c.fetchall()}
    conn.close()
    return templates

def process_crm_clients(file_path):
    result = {
        "by_nascimento": {},
        "by_ultcompra": {},
        "by_funnel": {}
    }
    
    if not file_path or not os.path.exists(file_path):
        return result, "Arquivo CRM não encontrado."
        
    df = read_data_file(file_path)
    if df is None or df.empty:
        return result, "Não foi possível ler o arquivo CRM ou ele está vazio."
        
    colunas_obrigatorias = ["NOME", "TELEFONE1", "NASCIMENTO", "ULTCOMPRA"]
    for col in colunas_obrigatorias:
        if col not in df.columns:
            return result, f"A coluna '{col}' não foi encontrada na planilha do CRM. Verifique o cabeçalho."

    df = df.loc[:,~df.columns.duplicated()].copy()
    
    # Preencher Sobrenome caso exista, senão string vazia
    if "SOBRENOME" in df.columns:
        df["SOBRENOME"] = df["SOBRENOME"].fillna("")
        df["Nome Completo"] = df["NOME"].astype(str).str.strip() + " " + df["SOBRENOME"].astype(str).str.strip()
    else:
        df["Nome Completo"] = df["NOME"].astype(str).str.strip()
        
    df["Nome Completo"] = df["Nome Completo"].str.strip()
    df['Telefone'] = df['TELEFONE1'].astype(str).str.strip()
    df['Sexo'] = df['SEXO'].astype(str).str.strip() if 'SEXO' in df.columns else ""
    
    # Filtrar válidos
    df = df[(df['Nome Completo'] != '') & (df['Nome Completo'] != 'nan') & (df['Telefone'] != '') & (df['Telefone'] != 'nan')]
    
    # Tratar Nascimento
    df['nasc_dt'] = pd.to_datetime(df['NASCIMENTO'], format='mixed', dayfirst=True, errors='coerce')
    df['nasc_str'] = df['nasc_dt'].dt.strftime("%d/%m")
    df['mes_nasc'] = df['nasc_dt'].dt.month
    
    # Tratar Última Compra
    df['ult_dt'] = pd.to_datetime(df['ULTCOMPRA'], format='mixed', dayfirst=True, errors='coerce')
    df['ult_str'] = df['ult_dt'].dt.strftime("%d/%m/%Y")
    df['mes_ano_ult'] = df['ult_dt'].dt.strftime("%Y-%m")
    
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
    
    # === DB LOOKUP ===
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT telefone, observacao, status_crm FROM crm_data")
    db_data = c.fetchall()
    conn.close()
    
    db_map = {row['telefone']: {"obs": row['observacao'], "status": row['status_crm']} for row in db_data}
    
    templates = get_crm_templates()
    
    meses_pt = {1:"Janeiro", 2:"Fevereiro", 3:"Março", 4:"Abril", 5:"Maio", 6:"Junho", 
                7:"Julho", 8:"Agosto", 9:"Setembro", 10:"Outubro", 11:"Novembro", 12:"Dezembro"}
    
    for _, row in df.iterrows():
        nome = row['Nome Completo']
        telefone = row['telefone_clean']
        is_whatsapp = row['is_whatsapp']
        nasc_str = row['nasc_str'] if pd.notna(row['nasc_str']) else "Não Informado"
        ult_str = row['ult_str'] if pd.notna(row['ult_str']) else "Não Informado"
        limite = row.get('LIMITE', '')
        
        saved_data = db_map.get(telefone, {"obs": "", "status": ""})
        
        client_obj = {
            "nome": nome,
            "telefone": telefone,
            "nascimento": nasc_str,
            "ultcompra": ult_str,
            "limite": limite,
            "sexo": row.get('Sexo', ''),
            "is_whatsapp": is_whatsapp,
            "obs_salva": saved_data["obs"],
            "status_crm": saved_data["status"],
            "mensagens": {},
            "_ult_dt": row['ult_dt']
        }
        
        # Gerar os links das mensagens baseadas nos templates
        for tipo in ["aquisicao", "nutricao", "oferta", "posvenda", "recuperacao", "aniversario"]:
            tpl = templates.get(f"crm_msg_{tipo}", "Olá {nome}!")
            msg_formatada = tpl.format(nome=nome, ultcompra=ult_str, nascimento=nasc_str)
            client_obj["mensagens"][tipo] = {
                "texto": msg_formatada,
                "url": f"https://wa.me/{telefone}?text={urllib.parse.quote(msg_formatada)}" if is_whatsapp else ""
            }
            
        # Agrupar por Nascimento (Exibir apenas os do dia de hoje)
        hoje_str = datetime.now().strftime("%d/%m")
        if nasc_str == hoje_str:
            grupo_nasc = f"Hoje ({hoje_str})"
            if grupo_nasc not in result["by_nascimento"]:
                result["by_nascimento"][grupo_nasc] = []
            result["by_nascimento"][grupo_nasc].append(client_obj)
        
        # Agrupar por Última Compra (Ano-Mês ou Vazio)
        mes_ano_ult = row['mes_ano_ult']
        if pd.isna(mes_ano_ult):
            grupo_ult = "Data Desconhecida"
        else:
            dt = row['ult_dt']
            grupo_ult = f"{dt.year}-{dt.month:02d} ({meses_pt.get(dt.month)}/{dt.year})"
            
        if grupo_ult not in result["by_ultcompra"]:
            result["by_ultcompra"][grupo_ult] = []
        result["by_ultcompra"][grupo_ult].append(client_obj)
        
        # Agrupar por Kanban (Funil)
        grupo_funil = saved_data["status"] if saved_data["status"] else "Nenhuma abordagem registrada"
        if grupo_funil not in result["by_funnel"]:
            result["by_funnel"][grupo_funil] = []
        result["by_funnel"][grupo_funil].append(client_obj)
        
    # Ordenar as chaves dos dicionários
    result["by_nascimento"] = dict(sorted(result["by_nascimento"].items()))
    result["by_ultcompra"] = dict(sorted(result["by_ultcompra"].items(), reverse=True))
    
    # Ordenar clientes dentro de by_ultcompra por dt decrescente
    for k in result["by_ultcompra"]:
        result["by_ultcompra"][k].sort(key=lambda x: x['_ult_dt'] if pd.notna(x['_ult_dt']) else pd.Timestamp.min, reverse=True)

    return result, None
