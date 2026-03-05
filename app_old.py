import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
from datetime import datetime
import urllib.parse
from werkzeug.utils import secure_filename
import codecs
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
app.secret_key = "chave_secreta_super_segura"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def parse_html_xls(file_path):
    """
    Função dedicada para arquivos .xls que na verdade são HTMLs disfarçados (comum em sistemas ERP).
    Lê o HTML e o transforma num DataFrame do Pandas de forma rápida.
    """
    try:
        # Verifica se o arquivo é utf-16 ou utf-8 (a maioria dos relatórios gerados é utf-16)
        with open(file_path, 'rb') as f:
            raw = f.read(100)
        encoding = 'utf-16' if b'\x00' in raw else 'utf-8'
        
        with codecs.open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            html_content = f.read()
            
        soup = BeautifulSoup(html_content, 'lxml')
        tables = soup.find_all('table')
        if not tables:
            return None
            
        # Pega a tabela com mais linhas (geralmente a tabela de dados principal)
        target_table = max(tables, key=lambda t: len(t.find_all('tr')))
        
        headers = []
        thead = target_table.find('thead')
        if not thead:
            rows = target_table.find_all('tr')
            if not rows: return None
            # Tenta pegar cabeçalhos da primeira linha
            headers = [th.get_text(strip=True) for th in rows[0].find_all(['th', 'td'])]
            trs = rows[1:]
        else:
            headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]
            trs = target_table.find('tbody').find_all('tr') if target_table.find('tbody') else target_table.find_all('tr')
            
        data = []
        for tr in trs:
            # Pula linhas do próprio thead se o find_all pegou tudo
            if tr.parent.name == 'thead': continue
            
            cells = tr.find_all('td')
            row_data = [cell.get_text(strip=True) for cell in cells]
            
            # Garante que possuímos a mesma quantidade de colunas que headers ou preenche com vazio
            if len(row_data) > 0:
                if len(headers) > 0 and len(headers) == len(row_data):
                    data.append(dict(zip(headers, row_data)))
                else:
                    # Se não combinar a quantidade, salva usando indices como coluna
                    data.append(dict(enumerate(row_data)))
                    
        df = pd.DataFrame(data)
        
        # Mapeia colunas do Relatorio fornecido pelo Usuário para os padrões do sistema
        # Caso o sistema do cliente use estes exatos nomes:
        mapper = {}
        for col in df.columns:
            if isinstance(col, str):
                upper_col = col.upper()
                if "NOME CLIENTE" in upper_col: mapper[col] = "Nome"
                elif upper_col == "TELEFONE 1" or upper_col == "TELEFONE": mapper[col] = "Telefone"
                elif "DT. VENCTO" in upper_col and "ANT" not in upper_col: mapper[col] = "Vencimento"
                elif "VALOR ATUAL" in upper_col or upper_col == "VALOR R$": mapper[col] = "Valor"
        
        if mapper:
            df.rename(columns=mapper, inplace=True)
            
        return df

    except Exception as e:
        print(f"Erro no parse HTML: {e}")
        return None

def read_data_file(file_path):
    try:
        lower_path = file_path.lower()
        
        # Suporte a CSV
        if lower_path.endswith('.csv'):
            for enc in ['utf-8', 'ISO-8859-1', 'cp1252']:
                try:
                    df = pd.read_csv(file_path, sep=';', encoding=enc)
                    if not df.empty and len(df.columns) > 1:
                        # Mapeia colunas do Relatorio num formato CSV para os padrões do sistema
                        # Mapeia colunas do Relatorio num formato CSV para os padrões do sistema
                        mapper = {}
                        for col in df.columns:
                            upper_col = str(col).upper().strip()
                            if "NOME CLIENTE" in upper_col and "Nome" not in mapper.values(): mapper[col] = "Nome"
                            elif (upper_col == "TELEFONE 1" or upper_col == "TELEFONE") and "Telefone" not in mapper.values(): mapper[col] = "Telefone"
                            elif "DATA DE VENCIMENTO" in upper_col and "ANTERIOR" not in upper_col and "Vencimento" not in mapper.values(): mapper[col] = "Vencimento"
                            elif "VALOR ATUAL" in upper_col:
                                mapper = {k: v for k, v in mapper.items() if v != "Valor"}
                                mapper[col] = "Valor"
                            elif "VALOR R$" in upper_col and "Valor" not in mapper.values(): mapper[col] = "Valor"
                        if mapper:
                            df.rename(columns=mapper, inplace=True)
                            # Remover colunas duplicadas que ainda possam existir
                            df = df.loc[:,~df.columns.duplicated()].copy()
                        return df
                except Exception:
                    continue
            return None
            
        # Suporte a XLS
        if lower_path.endswith('.xls'):
            # Tenta ler como HTML primeiro (devido ao formato report comum enviado pelo usuário)
            df = parse_html_xls(file_path)
            if df is not None and len(df) > 0 and 'Nome' in df.columns:
                return df
                
            # Fallback para engine oficial xlrd caso seja mesmo um binario XLS antigo
            try:
                df = pd.read_excel(file_path, engine='xlrd')
                return df
            except:
                pass
                
        # Se for XLSX ou o fallback anterior falhar
        df = pd.read_excel(file_path)
        return df
    except Exception as e:
        print(f"Erro genérico ao ler planilha: {e}")
        return None

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

    # Remove duplicates if any (just safe measure)
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
        if len(cl) > 8:
            if len(cl) <= 11 and not cl.startswith('55'):
                cl = '55' + cl
        return cl
        
    df['telefone_clean'] = df['Telefone'].apply(clean_phone)
    
    for _, row in df.iterrows():
        nome, valor_str, data_str = row['Nome'], row['Valor_str'], row['Data_str']
        days_diff, group_key, clean_phone_val = row['days_diff'], row['group_key'], row['telefone_clean']
        
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
        
    return groups, None

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        # Check if file was uploaded
        if 'planilha' not in request.files:
            flash('Nenhum arquivo enviado')
            return redirect(request.url)
            
        file = request.files['planilha']
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
            
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            session['planilha_path'] = file_path
            
            # Salva o caminho do arquivo para persistência entre dispositivos (ex: PC -> Celular)
            try:
                with open(os.path.join(app.config['UPLOAD_FOLDER'], 'active_file.txt'), 'w') as f:
                    f.write(file_path)
            except Exception as e:
                print(f"Erro ao salvar persistência: {e}")
                
            flash('Planilha carregada com sucesso!', 'success')
            return redirect(url_for('index'))
            
    # Usa planilha na sessão
    file_path = session.get('planilha_path')
    
    # Se não tem na sessão ou o arquivo não existe, tenta buscar do tracker global (para persistência entre dispositivos)
    if not file_path or not os.path.exists(file_path):
        tracker_path = os.path.join(app.config['UPLOAD_FOLDER'], 'active_file.txt')
        if os.path.exists(tracker_path):
            try:
                with open(tracker_path, 'r') as f:
                    tracked_file = f.read().strip()
                if os.path.exists(tracked_file):
                    file_path = tracked_file
                    session['planilha_path'] = file_path
            except:
                pass

    # Fallback se ainda não tiver achado arquivo válido
    if not file_path or not os.path.exists(file_path):
        file_path = 'planilha_clientes.xlsx'
        import glob
        xls_files = glob.glob('*.xls')
        csv_files = glob.glob('*.csv')
        if not os.path.exists(file_path):
            if xls_files:
                file_path = xls_files[0]
            elif csv_files:
                file_path = csv_files[0]
        session['planilha_path'] = file_path

    groups, error_msg = process_clients(file_path)
    
    if error_msg:
        flash(error_msg, 'danger')
        
    current_file_name = os.path.basename(file_path) if os.path.exists(file_path) else "Nenhuma planilha encontrada"
        
    return render_template("index.html", groups=groups, current_file=current_file_name)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0')
