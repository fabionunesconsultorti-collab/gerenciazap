import os
from flask import Flask
from .config import Config

def create_app():
    # Passando os caminhos corretos de template e static que continuam na raiz (fora do app/)
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config.from_object(Config)
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Registrando Blueprints
    from .modules.dashboard.routes import dashboard_bp
    app.register_blueprint(dashboard_bp)
    
    return app
