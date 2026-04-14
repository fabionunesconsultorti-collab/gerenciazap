import os
import glob
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, jsonify
from werkzeug.utils import secure_filename
from .services import process_crm_clients
from app.config import Config
from app.core.db import get_db_connection, log_action
from app.modules.auth.decorators import role_required
from app.services.customer_service import CustomerService

crm_bp = Blueprint('crm', __name__, url_prefix='/crm')

# Caminho para persistência da última lista de CRM enviada
ACTIVE_CRM_FILE = os.path.join(Config.UPLOAD_FOLDER, 'active_crm_file.txt')

@crm_bp.route('/api/status', methods=['POST'])
@role_required('admin', 'venda')
def update_crm_status():
    data = request.json
    telefone = data.get('telefone')
    cliente_nome = data.get('cliente_nome', '')
    status_crm = data.get('status_crm', '')
    
    if not telefone:
        return jsonify({'success': False, 'error': 'Telefone não informado'}), 400
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO crm_data (telefone, status_crm, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(telefone) 
        DO UPDATE SET status_crm=excluded.status_crm, last_updated=CURRENT_TIMESTAMP
    ''', (telefone, status_crm))
    
    if cliente_nome:
        current_user = session.get('username')
        c.execute("SELECT assigned_to FROM customers WHERE whatsapp = ?", (telefone,))
        customer_record = c.fetchone()
        
        if not customer_record:
            c.execute("INSERT INTO customers (nome_completo, whatsapp, assigned_to) VALUES (?, ?, ?)", 
                      (cliente_nome, telefone, current_user))
        elif customer_record['assigned_to'] is None:
            c.execute("UPDATE customers SET assigned_to = ? WHERE whatsapp = ?", (current_user, telefone))
            
    conn.commit()
    conn.close()
    
    log_action("CRM WHATSAPP", f"Funil CRM alterado para: {status_crm}", client_phone=telefone)
    return jsonify({'success': True})

@crm_bp.route('/api/obs', methods=['POST'])
@role_required('admin', 'venda')
def update_crm_obs():
    data = request.json
    telefone = data.get('telefone')
    cliente_nome = data.get('cliente_nome', '')
    observacao = data.get('observacao', '')
    
    if not telefone:
        return jsonify({'success': False, 'error': 'Telefone não informado'}), 400
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO crm_data (telefone, observacao, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(telefone) 
        DO UPDATE SET observacao=excluded.observacao, last_updated=CURRENT_TIMESTAMP
    ''', (telefone, observacao))

    if cliente_nome:
        current_user = session.get('username')
        c.execute("SELECT assigned_to FROM customers WHERE whatsapp = ?", (telefone,))
        customer_record = c.fetchone()
        
        if not customer_record:
            c.execute("INSERT INTO customers (nome_completo, whatsapp, assigned_to) VALUES (?, ?, ?)", 
                      (cliente_nome, telefone, current_user))
        elif customer_record['assigned_to'] is None:
            c.execute("UPDATE customers SET assigned_to = ? WHERE whatsapp = ?", (current_user, telefone))

    conn.commit()
    conn.close()
    
    log_action("OBSERVACAO SALVA (CRM)", f"Nova observação registrada no CRM", client_phone=telefone)
    return jsonify({'success': True})

@crm_bp.route("/dashboard", methods=["GET"])
@role_required('admin', 'venda')
def dashboard():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Ranking do mês atual
    c.execute('''
        SELECT username, COUNT(*) as score 
        FROM action_logs 
        WHERE action_type IN ('CRM WHATSAPP', 'OBSERVACAO SALVA (CRM)') 
          AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now', 'localtime') 
          AND username != 'Sistema'
        GROUP BY username 
        ORDER BY score DESC
    ''')
    ranking_data = c.fetchall()
    
    # Tratando empate e posições
    ranking = []
    for idx, row in enumerate(ranking_data):
        ranking.append({
            'posicao': idx + 1,
            'username': row['username'],
            'score': row['score']
        })
        
    # Evolução Diária (Para o Gráfico)
    c.execute('''
        SELECT date(timestamp) as dia, username, COUNT(*) as interacoes 
        FROM action_logs 
        WHERE action_type IN ('CRM WHATSAPP', 'OBSERVACAO SALVA (CRM)') 
          AND strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now', 'localtime')
          AND username != 'Sistema'
        GROUP BY dia, username 
        ORDER BY dia
    ''')
    evolution_data = c.fetchall()
    
    conn.close()
    
    # Processando evolução para Chart.js
    chart_labels = []
    chart_datasets = {}
    
    for row in evolution_data:
        dia = row['dia'][-2:] + '/' + row['dia'][5:7] # formato dd/mm
        user = row['username']
        
        if dia not in chart_labels:
            chart_labels.append(dia)
            
        if user not in chart_datasets:
            chart_datasets[user] = {}
            
        chart_datasets[user][dia] = row['interacoes']
        
    chart_labels.sort()
    
    final_datasets = []
    # Cores pré-definidas para até 10 vendedores
    colors = ['#3b82f6', '#ec4899', '#10b981', '#f59e0b', '#8b5cf6', '#0ea5e9', '#ef4444', '#14b8a6', '#6366f1', '#f43f5e']
    
    color_idx = 0
    for user, data in chart_datasets.items():
        user_points = []
        for label in chart_labels:
            user_points.append(data.get(label, 0))
            
        final_datasets.append({
            'label': user,
            'data': user_points,
            'borderColor': colors[color_idx % len(colors)],
            'backgroundColor': colors[color_idx % len(colors)] + '33', # com transparência
            'borderWidth': 2,
            'fill': True,
            'tension': 0.3
        })
        color_idx += 1
        
    chart_data = {
        'labels': chart_labels,
        'datasets': final_datasets
    }
    
    return render_template("crm/dashboard.html", ranking=ranking, chart_data=chart_data)

@crm_bp.route("/", methods=["GET", "POST"])
@role_required('admin', 'venda')
def index():
    if request.method == "POST":
        if 'planilha_crm' not in request.files:
            flash('Nenhum arquivo CRM enviado', 'danger')
            return redirect(request.url)
            
        file = request.files['planilha_crm']
        if file.filename == '':
            flash('Nenhum arquivo CRM selecionado', 'danger')
            return redirect(request.url)
            
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], "CRM_" + filename)
            file.save(file_path)
            session['planilha_crm_path'] = file_path
            
            try:
                with open(ACTIVE_CRM_FILE, 'w') as f:
                    f.write(file_path)
            except Exception as e:
                print(f"Erro ao salvar persistência do CRM: {e}")
                
            flash('Lista de Clientes CRM carregada com sucesso!', 'success')
            log_action("SISTEMA", f"Nova lista CRM carregada: {filename}")
            return redirect(url_for('crm.index'))
            
    file_path = session.get('planilha_crm_path')
    
    if not file_path or not os.path.exists(file_path):
        if os.path.exists(ACTIVE_CRM_FILE):
            try:
                with open(ACTIVE_CRM_FILE, 'r') as f:
                    tracked_file = f.read().strip()
                if os.path.exists(tracked_file):
                    file_path = tracked_file
                    session['planilha_crm_path'] = file_path
            except:
                pass

    clients, error_msg = {"by_nascimento": {}, "by_ultcompra": {}, "by_funnel": {}}, None
    
    total_clientes = 0
    aniversariantes_hoje = 0
    
    if file_path and os.path.exists(file_path):
        clients, error_msg = process_crm_clients(file_path)
        
        # Calculate stats from the generated dictionaries
        from datetime import datetime
        hoje_str = datetime.now().strftime("%d/%m")
        
        for k, cl_list in clients.get("by_funnel", {}).items():
            total_clientes += len(cl_list)
            for c in cl_list:
                if c.get("nascimento") == hoje_str:
                    aniversariantes_hoje += 1
                    
    # Log requests metric for the logged user
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        SELECT COUNT(*) as envios 
        FROM action_logs 
        WHERE action_type LIKE 'CRM%' 
        AND username = ? 
        AND date(timestamp) = date('now', 'localtime')
    ''', (session.get('username'),))
    acoes_hoje = c.fetchone()['envios']
    conn.close()
    
    stats = {
        'total_clientes': total_clientes,
        'aniversariantes': aniversariantes_hoje,
        'acoes_hoje': acoes_hoje
    }
    
    if error_msg:
        flash(error_msg, 'danger')
        
    current_file_name = os.path.basename(file_path) if file_path and os.path.exists(file_path) else "Nenhuma lista CRM carregada"
        
    return render_template("crm/index.html", clients=clients, current_file=current_file_name, stats=stats)

@crm_bp.route('/clientes', methods=['GET'])
@role_required('admin', 'venda')
def list_customers():
    conn = get_db_connection()
    c = conn.cursor()
    # Pega todos os clientes
    c.execute("SELECT * FROM customers ORDER BY created_at DESC")
    customers = c.fetchall()
    conn.close()
    
    # Adicionar contagens úteis
    total_customers = len(customers)
    total_lgpd = sum(1 for c in customers if c['lgpd_consent'])
    
    return render_template('crm/clientes.html', customers=customers, total=total_customers, lgpd=total_lgpd)

@crm_bp.route('/clientes/novo', methods=['GET', 'POST'])
@role_required('admin', 'venda')
def novo_cliente():
    if request.method == 'POST':
        # Delegate saving logic to our new service layer
        success, error = CustomerService.save_customer(request.form)
        if success:
            flash("Cliente criado com sucesso!", "success")
            log_action("NOVO CLIENTE", "Novo cliente cadastrado no CRM", client_name=request.form.get('nome_completo'))
            return redirect(url_for('crm.list_customers'))
        else:
            flash(f"Erro ao salvar cliente: {error}", "danger")
            
    return render_template('crm/customer_form.html', action='new', customer=None)

@crm_bp.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@role_required('admin', 'venda')
def editar_cliente(id):
    if request.method == 'POST':
        success, error = CustomerService.save_customer(request.form, customer_id=id)
        if success:
            flash("Cliente atualizado com sucesso!", "success")
            log_action("EDIÇÃO DE CLIENTE", f"ID {id} atualizado no CRM", client_name=request.form.get('nome_completo'))
            return redirect(url_for('crm.list_customers'))
        else:
            flash(f"Erro ao atualizar cliente: {error}", "danger")
            
    # GET request: load customer data to fill the form
    customer = CustomerService.get_customer(id)
    if not customer:
        flash("Cliente não encontrado.", "warning")
        return redirect(url_for('crm.list_customers'))
        
    return render_template('crm/customer_form.html', action='edit', customer=customer)

