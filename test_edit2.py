from app import create_app
app = create_app()
with app.test_client() as client:
    client.post('/auth/login', data={'username': 'fabio', 'password': '123'}, follow_redirects=True)
    res = client.post(f'/crm/clientes/editar/1', data={'nome_completo': 'Test', 'whatsapp': '123'}, follow_redirects=False)
    print(res.text)
