from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import Usuario, VehiculoMovil
from app import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.rol == 'vendedor':
            return redirect(url_for('vendedor.dashboard'))
        else:
            return redirect(url_for('almacen.panel'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.rol == 'vendedor':
            return redirect(url_for('vendedor.dashboard'))
        else:
            return redirect(url_for('almacen.panel'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        usuario = Usuario.query.filter_by(username=username).first()
        
        if usuario and check_password_hash(usuario.password, password):
            if not usuario.activo:
                flash('Tu cuenta ha sido bloqueada por el Webmaster/Administrador. Contacta a soporte.', 'danger')
                return redirect(url_for('auth.login'))

            login_user(usuario)
            flash(f'¡Bienvenido de nuevo, {usuario.nombre_completo}!', 'success')
            
            if usuario.rol == 'vendedor':
                return redirect(url_for('vendedor.dashboard'))
            else:
                return redirect(url_for('almacen.panel'))
        else:
            flash('Usuario o contraseña incorrectos. Por favor, verifica.', 'danger')
            
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    vehiculos = VehiculoMovil.query.all()

    if request.method == 'POST':
        nombre_completo = request.form.get('nombre_completo')
        cedula = request.form.get('cedula')
        telefono = request.form.get('telefono')
        username = request.form.get('username')
        password = request.form.get('password')
        rol = request.form.get('rol')
        vehiculo_id = request.form.get('vehiculo_id')
        pregunta_secreta = request.form.get('pregunta_secreta')
        respuesta_secreta = request.form.get('respuesta_secreta')

        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya se encuentra registrado.', 'warning')
            return redirect(url_for('auth.register'))

        if cedula and Usuario.query.filter_by(cedula=cedula).first():
            flash('La cédula ingresada ya está registrada.', 'warning')
            return redirect(url_for('auth.register'))

        try:
            v_id = int(vehiculo_id) if vehiculo_id and rol == 'vendedor' else None
            nuevo_usuario = Usuario(
                nombre_completo=nombre_completo,
                cedula=cedula,
                telefono=telefono,
                username=username,
                password=generate_password_hash(password),
                rol=rol if rol in ['vendedor', 'almacenista'] else 'vendedor',
                activo=True,
                vehiculo_id=v_id,
                pregunta_secreta=pregunta_secreta,
                respuesta_secreta=generate_password_hash(respuesta_secreta.lower().strip())
            )
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('¡Registro completado con éxito! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar usuario: {str(e)}', 'danger')

    return render_template('auth/register.html', vehiculos=vehiculos)

@auth_bp.route('/recuperar', methods=['GET', 'POST'])
def recuperar():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))

    usuario_encontrado = None

    if request.method == 'POST':
        step = request.form.get('step')

        if step == '1':
            username = request.form.get('username')
            usuario = Usuario.query.filter_by(username=username).first()
            if usuario and usuario.pregunta_secreta:
                usuario_encontrado = usuario
            else:
                flash('El usuario no existe o no tiene pregunta secreta configurada.', 'danger')

        elif step == '2':
            user_id = request.form.get('user_id')
            respuesta = request.form.get('respuesta_secreta')
            nueva_password = request.form.get('nueva_password')

            usuario = Usuario.query.get(user_id)
            if usuario and check_password_hash(usuario.respuesta_secreta, respuesta.lower().strip()):
                usuario.password = generate_password_hash(nueva_password)
                db.session.commit()
                flash('¡Contraseña restablecida con éxito! Inicia sesión con tu nueva clave.', 'success')
                return redirect(url_for('auth.login'))
            else:
                flash('La respuesta secreta es incorrecta.', 'danger')
                usuario_encontrado = usuario

    return render_template('auth/recuperar.html', usuario=usuario_encontrado)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))