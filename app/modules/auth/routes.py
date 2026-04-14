from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from app.core.db import get_db_connection, log_action

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            if not user['is_active']:
                flash('Usuário está desativado pelo administrador.', 'danger')
                return redirect(url_for('auth.login'))
                
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            log_action("SISTEMA", f"Usuário do tipo {user['role']} conectou.")
            
            # Se for admin, vai para o dashboard, se for vendedor também
            if user['role'] == 'promocao':
                return redirect(url_for('promocao.index'))
            return redirect(url_for('home.index'))
        else:
            flash('Usuário ou senha inválidos.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    log_action("SISTEMA", "Vendedor desconectado do painel.")
    session.clear()
    return redirect(url_for('auth.login'))
