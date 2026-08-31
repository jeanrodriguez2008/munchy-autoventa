import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'munchy_secret_key_123')
    
    # Render y Neon usan postgresql://
    db_uri = os.environ.get('DATABASE_URL', 'sqlite:///munchy_autoventa.db')
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Registro de Blueprints
    from app.routes.auth import auth_bp
    from app.routes.vendedor import vendedor_bp
    from app.routes.almacen import almacen_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(vendedor_bp)
    app.register_blueprint(almacen_bp)
    app.register_blueprint(admin_bp)

    return app