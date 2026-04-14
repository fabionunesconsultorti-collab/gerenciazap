from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
import shutil
from datetime import datetime
import subprocess
import zipfile

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

# ==========================================
# SISTEMA E BACKUP
# ==========================================

@admin_bp.route('/sistema', methods=['GET'])
@role_required('admin')
def sistema_index():
    return render_template('admin/sistema.html')

@admin_bp.route('/sistema/backup', methods=['POST'])
@role_required('admin')
def sistema_backup():
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        backup_dir = os.path.join(base_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_gerenciazap_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Arquivos essenciais
        db_path = os.path.join(base_dir, 'database.db')
        sqlite_path = os.path.join(base_dir, 'database.sqlite')
        uploads_dir = os.path.join(base_dir, 'uploads')
        
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists(db_path):
                zipf.write(db_path, 'database.db')
            if os.path.exists(sqlite_path):
                zipf.write(sqlite_path, 'database.sqlite')
                
            if os.path.exists(uploads_dir):
                for root, dirs, files in os.walk(uploads_dir):
                    for file in files:
                        abs_file = os.path.join(root, file)
                        rel_file = os.path.relpath(abs_file, base_dir)
                        zipf.write(abs_file, rel_file)
        
        log_action("SISTEMA", f"Backup completo gerado: {backup_filename}")
        flash('Backup gerado com sucesso! O download começará em instantes.', 'success')
        return send_file(backup_path, as_attachment=True, download_name=backup_filename)
        
    except Exception as e:
        log_action("SISTEMA", f"Erro ao gerar backup: {str(e)}")
        flash(f'Erro ao gerar backup: {str(e)}', 'danger')
        return redirect(url_for('admin.sistema_index'))

@admin_bp.route('/sistema/restore', methods=['POST'])
@role_required('admin')
def sistema_restore():
    if 'backup_file' not in request.files:
        flash('Nenhum arquivo de backup enviado.', 'danger')
        return redirect(url_for('admin.sistema_index'))
        
    file = request.files['backup_file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'danger')
        return redirect(url_for('admin.sistema_index'))
        
    if not file.filename.endswith('.zip'):
        flash('Formato inválido. Envie um arquivo .zip', 'danger')
        return redirect(url_for('admin.sistema_index'))
        
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        temp_dir = os.path.join(base_dir, 'temp_restore')
        os.makedirs(temp_dir, exist_ok=True)
        
        zip_path = os.path.join(temp_dir, secure_filename(file.filename))
        file.save(zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
            
        # Restaurar banco de dados
        db_temp = os.path.join(temp_dir, 'database.db')
        sqlite_temp = os.path.join(temp_dir, 'database.sqlite')
        
        if os.path.exists(db_temp):
            shutil.copy2(db_temp, os.path.join(base_dir, 'database.db'))
        if os.path.exists(sqlite_temp):
            shutil.copy2(sqlite_temp, os.path.join(base_dir, 'database.sqlite'))
            
        # Restaurar uploads
        uploads_temp = os.path.join(temp_dir, 'uploads')
        if os.path.exists(uploads_temp):
            uploads_dest = os.path.join(base_dir, 'uploads')
            if os.path.exists(uploads_dest):
                shutil.rmtree(uploads_dest)
            shutil.copytree(uploads_temp, uploads_dest)
            
        shutil.rmtree(temp_dir)
        
        log_action("SISTEMA", "Restauração do sistema concluída.")
        flash('Sistema restaurado com sucesso!', 'success')
        
    except Exception as e:
        log_action("SISTEMA", f"Erro na restauração: {str(e)}")
        flash(f'Erro durante a restauração: {str(e)}', 'danger')
        
    return redirect(url_for('admin.sistema_index'))

@admin_bp.route('/sistema/consistency_check', methods=['POST'])
@role_required('admin')
def sistema_consistency_check():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute('PRAGMA integrity_check;')
        result = c.fetchone()[0]
        conn.close()
        
        if result == 'ok':
            log_action("SISTEMA", "Verificação de consistência: OK")
            flash('Consistência do banco de dados verificada. Status: OK (Sem erros encontrados).', 'success')
        else:
            log_action("SISTEMA", f"Verificação de consistência encontrou problemas: {result}")
            flash(f'Atenção: A verificação de consistência encontrou problemas - {result}', 'warning')
            
    except Exception as e:
        log_action("SISTEMA", f"Erro na checagem de consistência: {str(e)}")
        flash(f'Erro ao verificar banco de dados: {str(e)}', 'danger')
        
    return redirect(url_for('admin.sistema_index'))

@admin_bp.route('/sistema/update', methods=['POST'])
@role_required('admin')
def sistema_update():
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        
        # Executa git pull
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'], 
            cwd=base_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            log_action("SISTEMA", "Sistema atualizado via GitHub (git pull origin main).")
            flash(f'Atualização via GitHub realizada com sucesso!\\nLog:\\n{result.stdout}', 'success')
        else:
            log_action("SISTEMA", f"Erro ao atualizar via GitHub: {result.stderr}")
            flash(f'Erro durante a atualização:\\n{result.stderr}', 'danger')
            
    except Exception as e:
        log_action("SISTEMA", f"Erro de subprocesso ao atualizar: {str(e)}")
        flash(f'Erro de sistema ao tentar atualizar: {str(e)}', 'danger')
        
    return redirect(url_for('admin.sistema_index'))

