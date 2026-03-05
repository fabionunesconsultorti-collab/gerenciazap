import os
import glob
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.utils import secure_filename
from .services import process_clients

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if 'planilha' not in request.files:
            flash('Nenhum arquivo enviado')
            return redirect(request.url)
            
        file = request.files['planilha']
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
            
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            session['planilha_path'] = file_path
            
            try:
                with open(os.path.join(current_app.config['UPLOAD_FOLDER'], 'active_file.txt'), 'w') as f:
                    f.write(file_path)
            except Exception as e:
                print(f"Erro ao salvar persistência: {e}")
                
            flash('Planilha carregada com sucesso!', 'success')
            return redirect(url_for('dashboard.index'))
            
    file_path = session.get('planilha_path')
    
    if not file_path or not os.path.exists(file_path):
        tracker_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'active_file.txt')
        if os.path.exists(tracker_path):
            try:
                with open(tracker_path, 'r') as f:
                    tracked_file = f.read().strip()
                if os.path.exists(tracked_file):
                    file_path = tracked_file
                    session['planilha_path'] = file_path
            except:
                pass

    if not file_path or not os.path.exists(file_path):
        file_path = 'planilha_clientes.xlsx'
        xls_files = glob.glob('*.xls')
        csv_files = glob.glob('*.csv')
        if not os.path.exists(file_path):
            if xls_files:
                file_path = xls_files[0]
            elif csv_files:
                file_path = csv_files[0]
        session['planilha_path'] = file_path

    groups, error_msg = process_clients(file_path)
    
    if error_msg:
        flash(error_msg, 'danger')
        
    current_file_name = os.path.basename(file_path) if os.path.exists(file_path) else "Nenhuma planilha encontrada"
        
    return render_template("index.html", groups=groups, current_file=current_file_name)
