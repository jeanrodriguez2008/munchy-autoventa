from datetime import datetime
import pytz
from flask_login import UserMixin
from app import db, login_manager

# Zona horaria de Venezuela
tz_caracas = pytz.timezone('America/Caracas')

def get_caracas_now():
    return datetime.now(tz_caracas)

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class VehiculoMovil(db.Model):
    __tablename__ = 'vehiculos_moviles'
    id = db.Column(db.Integer, primary_key=True)
    codigo_vehiculo = db.Column(db.String(50), unique=True, nullable=False) # Código del almacén móvil
    descripcion = db.Column(db.String(100), nullable=True) # Ejemplo: Camión Ruta 1 - Placa ABC1234
    
    # Relación con usuarios
    vendedores = db.relationship('Usuario', backref='vehiculo', lazy=True)

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Contraseña encriptada
    nombre_completo = db.Column(db.String(100), nullable=False)
    cedula = db.Column(db.String(20), unique=True, nullable=True) # Cédula de identidad
    telefono = db.Column(db.String(20), nullable=True) # Teléfono de contacto
    rol = db.Column(db.String(20), nullable=False, default='vendedor') # 'vendedor', 'almacenista', 'admin', 'webmaster'
    activo = db.Column(db.Boolean, default=True) # Control de bloqueo (True = Activo, False = Bloqueado)
    
    # Pregunta y respuesta secreta para recuperación de clave
    pregunta_secreta = db.Column(db.String(150), nullable=True)
    respuesta_secreta = db.Column(db.String(200), nullable=True) # Guardada encriptada
    
    # Clave foránea para asociar al vendedor con su almacén móvil (vehículo)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey('vehiculos_moviles.id'), nullable=True)
    
    # Relación con pedidos
    pedidos = db.relationship('Pedido', backref='vendedor', lazy=True)

class Categoria(db.Model):
    __tablename__ = 'categorias'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    
    productos = db.relationship('Producto', backref='categoria_rel', lazy=True)

class Producto(db.Model):
    __tablename__ = 'productos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(150), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias.id'), nullable=False)
    unidad_medida = db.Column(db.String(20), default='Unidades')
    stock_almacen = db.Column(db.Integer, default=0) # Stock disponible en el almacén principal
    imagen = db.Column(db.String(255), nullable=True) # Nombre del archivo de foto en static/uploads/
    
    detalles = db.relationship('DetallePedido', backref='producto', lazy=True)

class Pedido(db.Model):
    __tablename__ = 'pedidos'
    id = db.Column(db.Integer, primary_key=True)
    fecha_creacion = db.Column(db.DateTime, default=get_caracas_now) # Hora de Venezuela al crear
    fecha_despacho = db.Column(db.DateTime, nullable=True) # Hora de Venezuela al despachar por Almacén
    fecha_recepcion = db.Column(db.DateTime, nullable=True) # Hora de Venezuela al confirmar el vendedor
    estatus = db.Column(db.String(20), default='Pendiente') # 'Pendiente' o 'Entregado'
    recibido_conforme = db.Column(db.Boolean, default=False) # True cuando el vendedor presiona el botón
    
    # Vendedor que monta el pedido
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    
    detalles = db.relationship('DetallePedido', backref='pedido', cascade='all, delete-orphan', lazy=True)

class DetallePedido(db.Model):
    __tablename__ = 'detalles_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False) # Cantidad Solicitada por el Vendedor
    cantidad_despachada = db.Column(db.Integer, nullable=True) # Cantidad Realmente Despachada por el Almacenista