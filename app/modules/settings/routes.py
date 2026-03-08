from flask import Blueprint, render_template, request, flash, redirect, url_for
from app.core.db import get_db_connection, log_action
from app.modules.auth.decorators import role_required

settings_bp = Blueprint('settings', __name__, url_prefix='/configuracoes')

@settings_bp.route('/', methods=['GET', 'POST'])
@role_required('admin')
def index():
    conn = get_db_connection()
    c = conn.cursor()
    
    if request.method == 'POST':
        # Cobrança
        msg_lembrete = request.form.get('msg_lembrete')
        msg_hoje = request.form.get('msg_hoje')
        msg_atraso_leve = request.form.get('msg_atraso_leve')
        msg_atraso_grave = request.form.get('msg_atraso_grave')
        
        # CRM
        crm_msg_aquisicao = request.form.get('crm_msg_aquisicao')
        crm_msg_nutricao = request.form.get('crm_msg_nutricao')
        crm_msg_oferta = request.form.get('crm_msg_oferta')
        crm_msg_posvenda = request.form.get('crm_msg_posvenda')
        crm_msg_recuperacao = request.form.get('crm_msg_recuperacao')
        crm_msg_aniversario = request.form.get('crm_msg_aniversario')
        
        updates = [
            ('msg_lembrete', msg_lembrete),
            ('msg_hoje', msg_hoje),
            ('msg_atraso_leve', msg_atraso_leve),
            ('msg_atraso_grave', msg_atraso_grave),
            ('crm_msg_aquisicao', crm_msg_aquisicao),
            ('crm_msg_nutricao', crm_msg_nutricao),
            ('crm_msg_oferta', crm_msg_oferta),
            ('crm_msg_posvenda', crm_msg_posvenda),
            ('crm_msg_recuperacao', crm_msg_recuperacao),
            ('crm_msg_aniversario', crm_msg_aniversario)
        ]
        
        for key, value in updates:
            c.execute('''
                INSERT INTO settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) 
                DO UPDATE SET value=excluded.value
            ''', (key, value))
            
        conn.commit()
        log_action("CONFIGURACOES", "Templates de mensagens atualizados")
        flash("Configurações de mensagens salvas com sucesso!", "success")
        return redirect(url_for('settings.index'))
        
    # GET: Carrega as configurações atuais
    c.execute("SELECT key, value FROM settings")
    rows = c.fetchall()
    settings_data = {row['key']: row['value'] for row in rows}
    conn.close()
    
    return render_template('settings/index.html', settings=settings_data)
