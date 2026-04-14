import os
from flask import Flask
from .config import Config

def create_app():
    # Passando os caminhos corretos de template e static que continuam na raiz (fora do app/)
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Inicia banco de dados
    from .core.db import init_db
    init_db()
    
    # Registrando Blueprints
    from .modules.auth.routes import auth_bp
    app.register_blueprint(auth_bp)
    
    from .modules.home.routes import home_bp
    app.register_blueprint(home_bp)
    
    from .modules.admin.routes import admin_bp
    app.register_blueprint(admin_bp)

    from .modules.crm.routes import crm_bp
    app.register_blueprint(crm_bp)
    
    from .modules.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    from .modules.settings.routes import settings_bp
    app.register_blueprint(settings_bp)
    
    from .modules.reports.routes import reports_bp
    app.register_blueprint(reports_bp)
    
    from .modules.promocao.routes import promocao_bp
    app.register_blueprint(promocao_bp)
    
    return app
