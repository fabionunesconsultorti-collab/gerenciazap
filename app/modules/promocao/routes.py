from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.core.db import get_db_connection, log_action
from app.modules.auth.decorators import role_required

promocao_bp = Blueprint('promocao', __name__, url_prefix='/promocao')

@promocao_bp.route('/', methods=['GET'])
@role_required('admin', 'promocao')
def index():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = 'promo_lgpd_text'")
    row = c.fetchone()
    lgpd_text = row['value'] if row else ''
    conn.close()
    
    return render_template('promocao/index.html', lgpd_text=lgpd_text)

@promocao_bp.route('/cadastro', methods=['POST'])
@role_required('admin', 'promocao')
def cadastro():
    nome_completo = request.form.get('nome_completo')
    cpf = request.form.get('cpf')
    whatsapp = request.form.get('whatsapp')
    endereco = request.form.get('endereco', '')
    outros_dados = request.form.get('outros_dados', '')
    lgpd_consent = 1 if request.form.get('lgpd_consent') == 'on' else 0
    
    if not nome_completo or not cpf or not whatsapp or not lgpd_consent:
        flash("Nome, CPF, Whatsapp e aceite da LGPD são obrigatórios.", "danger")
        return redirect(url_for('promocao.index'))
        
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT id FROM customers WHERE cpf = ?", (cpf,))
    row = c.fetchone()
    
    if row:
        customer_id = row['id']
        c.execute('''
            UPDATE customers
            SET nome_completo=?, whatsapp=?, endereco=?, outros_dados=?, lgpd_consent=?
            WHERE id=?
        ''', (nome_completo, whatsapp, endereco, outros_dados, lgpd_consent, customer_id))
    else:
        c.execute("SELECT id FROM customers WHERE whatsapp = ?", (whatsapp,))
        row = c.fetchone()
        if row:
            customer_id = row['id']
            c.execute('''
                UPDATE customers
                SET nome_completo=?, cpf=?, endereco=?, outros_dados=?, lgpd_consent=?
                WHERE id=?
            ''', (nome_completo, cpf, endereco, outros_dados, lgpd_consent, customer_id))
        else:
            c.execute('''
                INSERT INTO customers (nome_completo, cpf, whatsapp, endereco, outros_dados, lgpd_consent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (nome_completo, cpf, whatsapp, endereco, outros_dados, lgpd_consent))
            customer_id = c.lastrowid
            
    conn.commit()
    conn.close()
    
    # Redireciona para o recibo par ser impresso no cliente (Browser Front-end)
    return redirect(url_for('promocao.recibo', customer_id=customer_id))

@promocao_bp.route('/recibo/<int:customer_id>', methods=['GET'])
@role_required('admin', 'promocao')
def recibo(customer_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Buscar usuário
    c.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    customer = c.fetchone()
    
    # Buscar texto LGPD
    c.execute("SELECT value FROM settings WHERE key = 'promo_lgpd_text'")
    row = c.fetchone()
    lgpd_text = row['value'] if row else ''
    
    conn.close()
    
    if not customer:
        flash("Cliente não encontrado.", "danger")
        return redirect(url_for('promocao.index'))
        
    # Mascarar CPF: 123.456.789-00 -> ***.456.789-**
    cpf = customer['cpf']
    masked_cpf = f"***.{cpf[4:11]}-**" if len(cpf) >= 11 else cpf
        
    return render_template('promocao/recibo.html', customer=customer, masked_cpf=masked_cpf, lgpd_text=lgpd_text)
