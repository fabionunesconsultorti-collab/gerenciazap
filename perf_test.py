import time
import pandas as pd
from datetime import datetime
import urllib.parse
from app import read_data_file

def process_clients_optimized(file_path):
    start = time.time()
    
    groups = {
        "lembrete": [],
        "hoje": [],
        "atraso_leve": [],
        "atraso_grave": []
    }
    
    df = read_data_file(file_path)
    print(f"Read file took: {time.time() - start:.3f}s")
    if df is None or df.empty:
        return groups, "Erro"
        
    start_proc = time.time()
    
    # Drop rows without required info
    colunas_obrigatorias = ["Nome", "Telefone", "Valor", "Vencimento"]
    df = df.dropna(subset=colunas_obrigatorias).copy()
    
    # String conversions
    df['Nome'] = df['Nome'].astype(str).str.strip()
    df['Telefone'] = df['Telefone'].astype(str).str.strip()
    
    df = df[(df['Nome'] != '') & (df['Nome'] != 'nan') & (df['Telefone'] != '') & (df['Telefone'] != 'nan')]
    
    today = datetime.now().date()
    
    # Parse dates efficiently
    # Instead of row by row string matching, pandas can parse it
    df['Vencimento_dt'] = pd.to_datetime(df['Vencimento'], format='mixed', dayfirst=True, errors='coerce').dt.date
    df = df.dropna(subset=['Vencimento_dt']).copy()
    
    # Calculate difference
    # .dt.date produces python date objects. So we subtract today directly.
    df['days_diff'] = df['Vencimento_dt'].apply(lambda x: (x - today).days)
    
    # Filter groups
    df['group_key'] = ''
    df.loc[(df['days_diff'] > 0) & (df['days_diff'] <= 3), 'group_key'] = 'lembrete'
    df.loc[df['days_diff'] == 0, 'group_key'] = 'hoje'
    df.loc[(df['days_diff'] < 0) & (df['days_diff'] >= -15), 'group_key'] = 'atraso_leve'
    df.loc[df['days_diff'] < -15, 'group_key'] = 'atraso_grave'
    
    # Keep only those that fall into a group
    df = df[df['group_key'] != ''].copy()
    df = df.reset_index(drop=True)
    
    # Format values
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
    
    # Process Whatsapp texts using vectorize logic
    def clean_phone(p):
        cl = ''.join(filter(str.isdigit, p))
        if len(cl) > 8:
            if len(cl) <= 11 and not cl.startswith('55'):
                cl = '55' + cl
        return cl
        
    df['telefone_clean'] = df['Telefone'].apply(clean_phone)
    
    # We will format the messages iterating over the filtered set, which is much smaller, or using apply
    for _, row in df.iterrows():
        nome = row['Nome']
        valor_str = row['Valor_str']
        data_str = row['Data_str']
        days_diff = row['days_diff']
        group_key = row['group_key']
        clean_phone_val = row['telefone_clean']
        
        if group_key == "lembrete":
            message = f"Olá {nome}, tudo bem? Passando para lembrar que sua fatura de R$ {valor_str} vence no dia {data_str}. Qualquer dúvida, estamos à disposição!"
        elif group_key == "hoje":
            message = f"Olá {nome}! Lembramos que o vencimento da sua fatura no valor de R$ {valor_str} é hoje ({data_str}). Ignore esta mensagem caso já tenha pago."
        elif group_key == "atraso_leve":
            message = f"Olá {nome}. Não identificamos o pagamento da sua fatura de R$ {valor_str} vencida em {data_str}. Houve algum problema? Segue nossa chave Pix / Link para regularização."
        else:
            message = f"Olá {nome}. Sua fatura de R$ {valor_str} vencida em {data_str} encontra-se pendente em nosso sistema. Temos condições especiais para regularização, podemos conversar?"
            
        encoded_msg = urllib.parse.quote(message)
        whatsapp_url = f"https://wa.me/{clean_phone_val}?text={encoded_msg}"
        
        groups[group_key].append({
            "nome": nome,
            "telefone": clean_phone_val,
            "valor": valor_str,
            "vencimento": data_str,
            "dias": abs(days_diff),
            "whatsapp_url": whatsapp_url,
            "mensagem": message
        })
        
    print(f"Processing took: {time.time() - start_proc:.3f}s")
    print(f"Total entries loaded: {sum([len(v) for v in groups.values()])}")
    return groups, None

if __name__ == "__main__":
    process_clients_optimized("Relatório_de_Contas_a_Receber_Detalhado-2026-03-03.csv")
