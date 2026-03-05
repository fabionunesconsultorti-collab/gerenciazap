import pandas as pd
import codecs
from bs4 import BeautifulSoup

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
                            df = df.loc[:,~df.columns.duplicated()].copy()
                        return df
                except Exception:
                    continue
            return None
            
        # Suporte a XLS
        if lower_path.endswith('.xls'):
            df = parse_html_xls(file_path)
            if df is not None and len(df) > 0 and 'Nome' in df.columns:
                return df
                
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
