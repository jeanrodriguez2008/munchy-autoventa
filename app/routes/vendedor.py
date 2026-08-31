import os
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import Producto, Categoria, Pedido, DetallePedido, get_caracas_now
from app import db

vendedor_bp = Blueprint('vendedor', __name__)

@vendedor_bp.route('/vendedor/dashboard')
@login_required
def dashboard():
    return redirect(url_for('vendedor.nuevo_pedido'))

@vendedor_bp.route('/vendedor/nuevo_pedido')
@vendedor_bp.route('/vendedor/nuevo_pedido/<int:categoria_id>')
@login_required
def nuevo_pedido(categoria_id=None):
    categorias = Categoria.query.all()
    categoria_seleccionada = None
    productos = []

    if categoria_id:
        categoria_seleccionada = Categoria.query.get_or_404(categoria_id)
        productos = Producto.query.filter_by(categoria_id=categoria_id).all()
    else:
        productos = Producto.query.all()

    # Pedidos del vendedor actual para consultar estatus y recepciones
    mis_pedidos = Pedido.query.filter_by(usuario_id=current_user.id).order_by(Pedido.fecha_creacion.desc()).all()

    return render_template(
        'vendedor/nuevo_pedido.html',
        categorias=categorias,
        categoria_seleccionada=categoria_seleccionada,
        productos=productos,
        mis_pedidos=mis_pedidos
    )

@vendedor_bp.route('/vendedor/confirmar_recepcion/<int:pedido_id>', methods=['POST'])
@login_required
def confirmar_recepcion(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if pedido.usuario_id != current_user.id and current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('No tienes permiso para modificar este pedido.', 'danger')
        return redirect(url_for('vendedor.nuevo_pedido'))

    pedido.recibido_conforme = True
    pedido.fecha_recepcion = get_caracas_now()
    db.session.commit()
    
    flash(f'¡Confirmaste la recepción conforme del Pedido #{pedido.id}!', 'success')
    return redirect(url_for('vendedor.nuevo_pedido'))

@vendedor_bp.route('/vendedor/eliminar_pedido/<int:pedido_id>', methods=['POST'])
@login_required
def eliminar_pedido(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    # RESTRICCIÓN DE SEGURIDAD: Solo Webmaster, Analista y Almacenista pueden eliminar pedidos
    if current_user.rol not in ['webmaster', 'admin', 'analista', 'almacenista']:
        flash('Acceso denegado: Solo Webmaster, Analista y Almacenista pueden eliminar pedidos.', 'danger')
        return redirect(request.referrer or url_for('vendedor.nuevo_pedido'))

    try:
        # Si el pedido estaba entregado, devolvemos el stock al almacén antes de borrar
        if pedido.estatus == 'Entregado':
            for detalle in pedido.detalles:
                if detalle.producto:
                    cant_a_devolver = detalle.cantidad_despachada if detalle.cantidad_despachada is not None else detalle.cantidad
                    detalle.producto.stock_almacen += cant_a_devolver

        db.session.delete(pedido)
        db.session.commit()
        flash(f'¡El Pedido #{pedido_id} ha sido eliminado con éxito!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al intentar eliminar el pedido: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('vendedor.nuevo_pedido'))

@vendedor_bp.route('/categoria/eliminar/<int:categoria_id>', methods=['POST'])
@login_required
def eliminar_categoria(categoria_id):
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Solo el Webmaster o Administrador puede eliminar categorías.', 'danger')
        return redirect(url_for('vendedor.nuevo_pedido'))

    categoria = Categoria.query.get_or_404(categoria_id)
    nombre = categoria.nombre

    try:
        productos_asociados = Producto.query.filter_by(categoria_id=categoria.id).all()
        if productos_asociados:
            for prod in productos_asociados:
                db.session.delete(prod)
        
        db.session.delete(categoria)
        db.session.commit()
        flash(f'¡Categoría "{nombre}" eliminada exitosamente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la categoría: {str(e)}', 'danger')

    return redirect(url_for('vendedor.nuevo_pedido'))

@vendedor_bp.route('/producto/editar_imagen/<int:producto_id>', methods=['POST'])
@login_required
def editar_imagen(producto_id):
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Solo el Webmaster o Administrador puede modificar imágenes.', 'danger')
        return redirect(url_for('vendedor.nuevo_pedido'))

    producto = Producto.query.get_or_404(producto_id)
    file = request.files.get('imagen_archivo')

    if file and file.filename != '':
        filename = secure_filename(file.filename)
        extension = os.path.splitext(filename)[1]
        nuevo_nombre_archivo = f"prod_{producto.codigo}{extension}"
        
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        
        ruta_guardado = os.path.join(upload_folder, nuevo_nombre_archivo)
        file.save(ruta_guardado)

        producto.imagen = nuevo_nombre_archivo
        db.session.commit()
        flash(f'¡Imagen del producto {producto.codigo} actualizada con éxito!', 'success')
    else:
        flash('No se seleccionó ninguna imagen válida.', 'warning')

    return redirect(url_for('vendedor.nuevo_pedido', categoria_id=producto.categoria_id))

@vendedor_bp.route('/vendedor/crear_pedido', methods=['POST'])
@login_required
def crear_pedido():
    if current_user.rol not in ['vendedor', 'webmaster', 'admin', 'analista']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('auth.login'))

    items_json = request.form.get('items_json')
    if not items_json:
        flash('El pedido no contiene productos.', 'warning')
        return redirect(url_for('vendedor.nuevo_pedido'))

    try:
        items = json.loads(items_json)
        if not items:
            flash('El pedido está vacío.', 'warning')
            return redirect(url_for('vendedor.nuevo_pedido'))

        nuevo_pedido = Pedido(
            usuario_id=current_user.id,
            estatus='Pendiente'
        )
        db.session.add(nuevo_pedido)
        db.session.flush()

        for item in items:
            cant = int(item['cantidad'])
            detalle = DetallePedido(
                pedido_id=nuevo_pedido.id,
                producto_id=int(item['id']),
                cantidad=cant,
                cantidad_despachada=cant
            )
            db.session.add(detalle)

        db.session.commit()
        flash(f'¡Pedido #{nuevo_pedido.id} montado exitosamente! El almacén ya puede visualizarlo.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al procesar el pedido: {str(e)}', 'danger')

    return redirect(url_for('vendedor.nuevo_pedido'))