import pandas as pd
from datetime import datetime, timedelta
import random

def generate_sample_data():
    today = datetime.now()
    
    # Generate some realistic names
    names = [
        "Ana Silva", "Bruno Costa", "Carlos Oliveira", "Daniela Santos", 
        "Eduardo Mendes", "Fernanda Lima", "Gustavo Ramos", "Helena Pereira",
        "Igor Almeida", "Julia Rodrigues", "Lucas Fernandes", "Mariana Alves",
        "Nicolas Ferreira", "Olivia Ribeiro", "Pedro Barbosa", "Quintino Dias",
        "Rafaela Castro", "Samuel Araujo", "Tatiana Machado", "Ulisses Gomes"
    ]
    
    # Dates relative to today to fit into the 4 groups:
    # 1. Lembrete (vence em 1-3 dias)
    # 2. Vence Hoje (vence em 0 dias)
    # 3. Atraso Leve (atraso de 1 a 15 dias -> venceu há 1-15 dias)
    # 4. Atraso Grave (atraso > 15 dias -> venceu há mais de 15 dias)
    
    data = []
    
    for i in range(20):
        name = names[i]
        # Generate a fake brazilian phone number (e.g. 5511999999999)
        phone = f"55119{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        # Random value between 50.00 and 1500.00
        value = round(random.uniform(50.0, 1500.0), 2)
        
        # Distribute randomly across the 4 categories
        category = random.choice([1, 2, 3, 4])
        
        if category == 1:
            # Lembrete: +1 to +3 days
            days_offset = random.randint(1, 3)
        elif category == 2:
            # Hoje: 0 days
            days_offset = 0
        elif category == 3:
            # Atraso Leve: -1 to -15 days
            days_offset = -random.randint(1, 15)
        else:
            # Atraso Grave: -16 to -60 days
            days_offset = -random.randint(16, 60)
            
        due_date = today + timedelta(days=days_offset)
        
        data.append({
            "Nome": name,
            "Telefone": phone,
            "Valor": value,
            "Vencimento": due_date.strftime("%Y-%m-%d")
        })
        
    df = pd.DataFrame(data)
    df.to_excel("planilha_clientes.xlsx", index=False)
    print("Arquivo 'planilha_clientes.xlsx' gerado com sucesso!")

if __name__ == "__main__":
    generate_sample_data()
