import os

class Config:
    SECRET_KEY = "chave_secreta_super_segura"
    # Base dir is cobranca/, config.py is in cobranca/app/
    BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
