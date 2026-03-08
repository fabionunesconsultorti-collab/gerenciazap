from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from app.core.db import get_db_connection, log_action
from app.modules.auth.decorators import role_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/usuarios', methods=['GET'])
@role_required('admin')
def list_users():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, username, role, is_active FROM users ORDER BY id")
    users = c.fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/usuarios/novo', methods=['POST'])
@role_required('admin')
def create_user():
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role', 'cobranca')
    
    if not username or not password:
        flash('Usuário e senha são obrigatórios.', 'danger')
        return redirect(url_for('admin.list_users'))
        
    conn = get_db_connection()
    c = conn.cursor()
    
    # Verifica se já existe
    c.execute("SELECT id FROM users WHERE username = ?", (username,))
    if c.fetchone():
        flash('Este nome de usuário já está em uso.', 'danger')
        conn.close()
        return redirect(url_for('admin.list_users'))
        
    hashed_password = generate_password_hash(password)
    
    c.execute('''
        INSERT INTO users (username, password_hash, role, is_active)
        VALUES (?, ?, ?, 1)
    ''', (username, hashed_password, role))
    
    conn.commit()
    conn.close()
    
    log_action("SISTEMA", f"Novo usuário criado: {username} ({role})")
    flash(f'Usuário {username} criado com sucesso!', 'success')
    return redirect(url_for('admin.list_users'))

@admin_bp.route('/usuarios/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(user_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT username, is_active, role FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    
    if not user:
        flash('Usuário não encontrado.', 'danger')
        conn.close()
        return redirect(url_for('admin.list_users'))
        
    if user['username'] == 'admin' and user['role'] == 'admin':
        flash('Não é possível desativar o administrador principal do sistema.', 'danger')
        conn.close()
        return redirect(url_for('admin.list_users'))
        
    new_status = 0 if user['is_active'] else 1
    c.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    
    status_text = "ativado" if new_status == 1 else "desativado"
    log_action("SISTEMA", f"Acesso do usuário {user['username']} foi {status_text}.")
    flash(f'Status do usuário {user["username"]} alterado para {status_text}.', 'success')
    
    return redirect(url_for('admin.list_users'))
