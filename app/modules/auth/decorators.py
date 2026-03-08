from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """
    Exije que o usuário tenha um dos roles listados na tupla `roles`.
    Ex: @role_required('admin', 'venda')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Primeiro checa se tá logado
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
                
            # Depois checa se a role tá na lista de liberadas
            if session.get('role') not in roles:
                flash('Você não tem permissão para acessar esta área.', 'danger')
                
                # Redireciona de volta para o melhor painel com base no próprio cargo
                user_role = session.get('role')
                if user_role == 'venda':
                    return redirect(url_for('crm.index'))
                else:
                    return redirect(url_for('dashboard.index'))
                    
            return f(*args, **kwargs)
        return decorated_function
    return decorator
