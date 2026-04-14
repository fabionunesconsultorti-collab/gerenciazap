import sqlite3
from app.core.db import get_db_connection

class CustomerService:
    @staticmethod
    def get_customer(customer_id):
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
        customer = c.fetchone()
        conn.close()
        return customer

    @staticmethod
    def save_customer(customer_data, customer_id=None):
        conn = get_db_connection()
        c = conn.cursor()
        
        # Fields map
        fields = [
            'nome_completo', 'cpf', 'whatsapp', 'endereco', 'outros_dados',
            'email', 'cep', 'bairro', 'cidade', 'estado', 'numero', 'complemento',
            'data_nascimento', 'profissao', 'como_conheceu', 'preferencias', 
            'historico_compras', 'objetivo_compra', 'desafios', 'orcamento', 'restricoes_entrega'
        ]
        
        values = []
        for field in fields:
            values.append(customer_data.get(field, ''))

        try:
            if customer_id:
                # Update
                set_clause = ", ".join([f"{f} = ?" for f in fields])
                query = f"UPDATE customers SET {set_clause} WHERE id = ?"
                values.append(customer_id)
                c.execute(query, tuple(values))
            else:
                # Insert
                placeholders = ", ".join(["?"] * len(fields))
                columns = ", ".join(fields)
                query = f"INSERT INTO customers ({columns}) VALUES ({placeholders})"
                c.execute(query, tuple(values))
                
            conn.commit()
            success = True
            error = None
        except Exception as e:
            conn.rollback()
            success = False
            error = str(e)
        finally:
            conn.close()
            
        return success, error

    @staticmethod
    def enrich_customer_data(cpf_or_params):
        """
        Futuramente, implemente aqui integrações com API's externas
        como Receita Federal, Serasa, etc.
        """
        return {
            "status": "info",
            "message": "Funcionalidade de enriquecimento por IA/API será implementada em atualizações futuras."
        }
