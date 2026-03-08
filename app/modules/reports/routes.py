from flask import Blueprint, render_template, session
from app.core.db import get_db_connection
from app.modules.auth.decorators import role_required
import json

reports_bp = Blueprint('reports', __name__, url_prefix='/relatorios')

@reports_bp.route('/')
@role_required('admin', 'cobranca', 'venda')
def index():
    conn = get_db_connection()
    c = conn.cursor()
    
    role = session.get('role')
    
    # Base query
    query = """
    SELECT id, timestamp, action_type, details, client_phone, client_name, username 
    FROM action_logs
    """
    params = []
    
    # Se for cobrador, não vê logs do "CRM"
    if role == 'cobranca':
        query += " WHERE action_type NOT LIKE 'CRM%'"
    # Se for vendedor crm, não vê logs de cobrança
    elif role == 'venda':
        query += " WHERE action_type LIKE 'CRM%'"
        
    query += " ORDER BY id DESC LIMIT 100"
    
    c.execute(query, params)
    logs = c.fetchall()
    
    # Busca métricas rápidas de envios de hoje (Geral, mesmo se for vendedor e estiver filtrando os logs, as descrições em painéis de métrica geralmente são gerais, 
    # ou podemos filtrar. Vamos manter a métrica antiga geral).
    c.execute("SELECT COUNT(*) as envios_hoje FROM action_logs WHERE action_type = 'MENSAGEM WHATSAPP' AND date(timestamp) = date('now', 'localtime')")
    metricas_hoje = c.fetchone()
    
    c.execute("SELECT COUNT(*) as total_envios FROM action_logs WHERE action_type = 'MENSAGEM WHATSAPP'")
    metricas_total = c.fetchone()
    
    # Dashboard stats
    stats = {
        'envios_hoje': metricas_hoje['envios_hoje'] if metricas_hoje else 0,
        'total_envios': metricas_total['total_envios'] if metricas_total else 0
    }
    
    conn.close()
    
    return render_template('reports/index.html', logs=logs, stats=stats)
