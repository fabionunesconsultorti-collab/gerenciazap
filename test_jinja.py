from app.core.db import get_db_connection
from jinja2 import Template

conn = get_db_connection()
c = conn.cursor()
c.execute("SELECT * FROM customers LIMIT 1")
row = c.fetchone()
    
template = "{{ customer.nome_completo }}"
try:
    t = Template(template)
    print("JINJA OUTPUT:", t.render(customer=row))
except Exception as e:
    print("ERROR:", e)
