from flask import Blueprint, render_template, session
from app.modules.auth.decorators import role_required

home_bp = Blueprint('home', __name__)

@home_bp.route('/')
def index():
    if 'user_id' not in session:
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
        
    role = session.get('role')
    if role == 'promocao':
        from flask import redirect, url_for
        return redirect(url_for('promocao.index'))
        
    return render_template('hub.html', role=role)
