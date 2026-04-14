from app import create_app
from app.services.customer_service import CustomerService

app = create_app()

with app.app_context():
    success, error = CustomerService.save_customer({
        'nome_completo': 'TESTE SCRIPT',
        'cpf': '00011122233',
        'whatsapp': '99999999',
        'historico_compras': 'Teste'
    }, customer_id=1)
    
    print("SUCCESS:", success)
    print("ERROR:", error)
