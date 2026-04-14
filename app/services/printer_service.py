import subprocess
import os
import datetime
import textwrap

class PrinterService:
    @staticmethod
    def print_promo_receipt(customer_data, lgpd_text):
        """
        Gera um cupom fiscal de promocoes em raw text para impressora térmica 80mm
        e o envia diretamente para a impressora padrão do sistema Linux via spooler CUPS.
        """
        # Impressora térmica 80mm padrão geralmente suporta 48 colunas de largura em fonte normal.
        COLUMNS = 48
        
        # Helper interno para centralizar título
        def center(text, fillchar=' '):
            return text.center(COLUMNS, fillchar)

        # Helper para divisor
        def divider(char='-'):
            return char * COLUMNS

        cpf = customer_data.get('cpf', '')
        masked_cpf = f"***.{cpf[4:11]}-**" if len(cpf) >= 11 else cpf

        data_hora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # Construindo o Buffer do Ticket
        ticket_lines = []
        ticket_lines.append(divider('='))
        ticket_lines.append(center("CUPOM DE PROMOCAO / SORTEIO"))
        ticket_lines.append(divider('='))
        ticket_lines.append("")
        
        ticket_lines.append(f"DATA: {data_hora}")
        ticket_lines.append(divider())
        ticket_lines.append(center("DADOS DO CLIENTE", ' '))
        ticket_lines.append("")
        
        ticket_lines.append(f"NOME : {customer_data.get('nome_completo', '')[:38]}")
        ticket_lines.append(f"CPF  : {masked_cpf}")
        ticket_lines.append(f"WHATS: {customer_data.get('whatsapp', '')}")
        ticket_lines.append("")
        
        ticket_lines.append(divider('='))
        ticket_lines.append(center("TERMO DE ACEITE - LGPD", ' '))
        ticket_lines.append(divider('='))
        ticket_lines.append("O cliente listado acima leu e concordou com a")
        ticket_lines.append("inclusao de seus dados em nosso banco de dados.")
        ticket_lines.append("")
        
        # Quebra de linha dinâmica para o texto LGPD evitando ultrapassar 48 colunas
        wrapped_lgpd = textwrap.wrap(lgpd_text, width=COLUMNS)
        for line in wrapped_lgpd:
            ticket_lines.append(line)

        ticket_lines.append("")
        ticket_lines.append(divider())
        ticket_lines.append(center("BOA SORTE!", ' '))
        ticket_lines.append(divider())
        
        # Alguns espaçamentos no final para a guilhotina da impressora cortar certo (Feed)
        ticket_lines.append("\n\n\n\n\n") 
        
        # Converta a lista para string com CRLF
        ticket_text = "\n".join(ticket_lines)

        # Envia o arquivo Raw Text pro Linux CUPS/lpd
        try:
            # -d define o destino, omitindo -d ele pega o padrão do SO
            # -o raw informa ao CUPS para nao emular drivers/fonte, mandar exatamente os bytes ASCII
            process = subprocess.Popen(
                ['lp', '-o', 'raw'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(input=ticket_text.encode('latin1', errors='replace'))
            
            if process.returncode != 0:
                print(f"[PrinterService] Falha ao enviar para impressora: {stderr.decode()}")
                return False
                
            return True
        except Exception as e:
            print(f"[PrinterService] Erro fatal de impressao: {e}")
            return False
