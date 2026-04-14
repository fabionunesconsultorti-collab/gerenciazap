from app import create_app
from app.core.db import get_db_connection

app = create_app()

with app.test_client() as client:
    # 1. Login auth
    res = client.post('/auth/login', data={'username': 'fabio', 'password': '123'}, follow_redirects=True)
    
    # 2. Find a valid customer ID
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, nome_completo, whatsapp FROM customers LIMIT 1")
    row = c.fetchone()
    conn.close()
    
    if row:
        cid = row['id']
        print(f"Editing customer {cid}...")
        payload = {
            'nome_completo': row['nome_completo'] + ' UPDATE',
            'cpf': '12345678901',
            'whatsapp': row['whatsapp'],
            'endereco': 'Rua Teste',
        }
        res2 = client.post(f'/crm/clientes/editar/{cid}', data=payload, follow_redirects=True)
        print("Status", res2.status_code)
        # Check flashes
        with client.session_transaction() as sess:
            print("Session:", sess.get('_flashes'))
    else:
        print("No customers in DB.")
