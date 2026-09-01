import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy import text

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'munchy_secret_key_123')
    
    # Render y Neon usan postgresql://
    db_uri = os.environ.get('DATABASE_URL', 'sqlite:///munchy_autoventa.db')
    if db_uri.startswith("postgres://"):
        db_uri = db_uri.replace("postgres://", "postgresql://", 1)
        
    # Asegurar parámetro sslmode=require para conexiones PostgreSQL en Render
    if db_uri.startswith("postgresql://") and "sslmode=" not in db_uri:
        if "?" in db_uri:
            db_uri += "&sslmode=require"
        else:
            db_uri += "?sslmode=require"
        
    app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Evitar caída de conexión SSL reconectando automáticamente (Pool Pre-Ping)
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_timeout': 30
    }

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

    # Creación automática de tablas, migración de columnas y usuario webmaster por defecto
    with app.app_context():
        db.create_all()

        # Migración automática de columna request_id para PostgreSQL en Render
        try:
            db.session.execute(text("ALTER TABLE pedidos ADD COLUMN IF NOT EXISTS request_id VARCHAR(36) UNIQUE;"))
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Aviso en migración de columna request_id: {e}")

        try:
            from app.models import Usuario
            if not Usuario.query.filter_by(username='webmaster').first():
                from werkzeug.security import generate_password_hash
                admin_user = Usuario(
                    username='webmaster',
                    password=generate_password_hash('Munchy2026*'),
                    nombre_completo='Administrador Webmaster',
                    rol='admin',
                    activo=True
                )
                db.session.add(admin_user)
                db.session.commit()
        except Exception as e:
            print(f"Error creando usuario administrador inicial: {e}")

    return app