import os
import json
import pandas as pd
from io import BytesIO
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from werkzeug.security import generate_password_hash
from app.models import Usuario, VehiculoMovil, Producto, Categoria, Pedido, DetallePedido
from app import db

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard')
@login_required
def dashboard():
    if current_user.rol not in ['vendedor', 'almacenista', 'admin', 'webmaster', 'analista']:
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('auth.login'))

    vendedor_id_filtro = request.args.get('vendedor_id', type=int)
    if current_user.rol == 'vendedor':
        vendedor_id_filtro = current_user.id

    vendedores = Usuario.query.filter_by(rol='vendedor').all()

    query_pedidos = Pedido.query
    if vendedor_id_filtro:
        query_pedidos = query_pedidos.filter_by(usuario_id=vendedor_id_filtro)

    pedidos_todos = query_pedidos.all()
    total_pedidos = len(pedidos_todos)
    pedidos_procesados = [p for p in pedidos_todos if p.estatus == 'Entregado']
    pedidos_entregados_count = len(pedidos_procesados)

    pedidos_ids = [p.id for p in pedidos_todos]
    if pedidos_ids:
        detalles_todos = DetallePedido.query.filter(DetallePedido.pedido_id.in_(pedidos_ids)).all()
    else:
        detalles_todos = []

    total_unidades_solicitadas = sum([d.cantidad for d in detalles_todos])
    total_unidades_despachadas = sum([d.cantidad_despachada if d.cantidad_despachada is not None else d.cantidad for d in detalles_todos])

    efectividad_despacho_pct = round((total_unidades_despachadas / total_unidades_solicitadas * 100), 1) if total_unidades_solicitadas > 0 else 0.0

    if pedidos_ids:
        prod_top_query = db.session.query(
            Producto.descripcion,
            func.sum(DetallePedido.cantidad_despachada).label('total_cant')
        ).join(DetallePedido, Producto.id == DetallePedido.producto_id)\
         .filter(DetallePedido.pedido_id.in_(pedidos_ids))\
         .group_by(Producto.id)\
         .order_by(desc('total_cant')).first()

        producto_top_nombre = prod_top_query.descripcion if prod_top_query else 'Sin registros'
    else:
        producto_top_nombre = 'Sin registros'

    pedidos_completos = 0
    pedidos_incompletos = 0

    for p in pedidos_procesados:
        es_completo = True
        for d in p.detalles:
            cant_desp = d.cantidad_despachada if d.cantidad_despachada is not None else d.cantidad
            if cant_desp < d.cantidad:
                es_completo = False
                break
        if es_completo:
            pedidos_completos += 1
        else:
            pedidos_incompletos += 1

    tasa_cumplimiento = round((pedidos_completos / pedidos_entregados_count * 100), 1) if pedidos_entregados_count > 0 else 0.0
    promedio_unidades_pedido = round(total_unidades_despachadas / total_pedidos, 1) if total_pedidos > 0 else 0.0

    diferencias_segundos = []
    for p in pedidos_procesados:
        if p.fecha_despacho and p.fecha_creacion and p.fecha_despacho >= p.fecha_creacion:
            diff = (p.fecha_despacho - p.fecha_creacion).total_seconds()
            diferencias_segundos.append(diff)

    if diferencias_segundos:
        prom_seg = sum(diferencias_segundos) / len(diferencias_segundos)
        minutos_prom = int(prom_seg // 60)
        horas_prom = minutos_prom // 60
        min_restantes = minutos_prom % 60
        tiempo_promedio_str = f"{horas_prom}h {min_restantes}m" if horas_prom > 0 else f"{minutos_prom} min"
    else:
        tiempo_promedio_str = "N/A"

    top_vendedores_raw = db.session.query(
        Usuario.id,
        Usuario.nombre_completo,
        func.sum(DetallePedido.cantidad).label('total_volumen')
    ).join(Pedido, Pedido.usuario_id == Usuario.id)\
     .join(DetallePedido, DetallePedido.pedido_id == Pedido.id)\
     .group_by(Usuario.id)\
     .order_by(desc('total_volumen'))\
     .limit(3).all()

    top_3_vendedores = []
    for v_id, nombre, volumen in top_vendedores_raw:
        articulo_estrella = db.session.query(
            Producto.descripcion,
            func.sum(DetallePedido.cantidad).label('total_prod')
        ).join(DetallePedido, DetallePedido.producto_id == Producto.id)\
         .join(Pedido, Pedido.id == DetallePedido.pedido_id)\
         .filter(Pedido.usuario_id == v_id)\
         .group_by(Producto.id)\
         .order_by(desc('total_prod')).first()

        top_3_vendedores.append({
            'nombre': nombre,
            'volumen': volumen,
            'producto_estrella': articulo_estrella[0] if articulo_estrella else 'N/A',
            'cantidad_estrella': articulo_estrella[1] if articulo_estrella else 0
        })

    gestion_vendedores = []

    for v in vendedores:
        ped_v = Pedido.query.filter_by(usuario_id=v.id).all()
        ped_ids_v = [p.id for p in ped_v]
        det_v = DetallePedido.query.filter(DetallePedido.pedido_id.in_(ped_ids_v)).all() if ped_ids_v else []

        solicitadas_v = sum([d.cantidad for d in det_v])
        despachadas_v = sum([d.cantidad_despachada if d.cantidad_despachada is not None else d.cantidad for d in det_v])
        efectividad_v = round((despachadas_v / solicitadas_v * 100), 1) if solicitadas_v > 0 else 0.0

        mas_pedido = db.session.query(
            Producto.descripcion,
            func.sum(DetallePedido.cantidad).label('total_cant')
        ).join(DetallePedido, Producto.id == DetallePedido.producto_id)\
         .filter(DetallePedido.pedido_id.in_(ped_ids_v))\
         .group_by(Producto.id)\
         .order_by(desc('total_cant')).first() if ped_ids_v else None

        gestion_vendedores.append({
            'id': v.id,
            'vendedor': v.nombre_completo,
            'vehiculo': v.vehiculo.codigo_vehiculo if v.vehiculo else 'Sin Asignar',
            'total_pedidos': len(ped_v),
            'unidades_solicitadas': solicitadas_v,
            'unidades_despachadas': despachadas_v,
            'efectividad': efectividad_v,
            'top_producto': mas_pedido[0] if mas_pedido else 'Sin ventas'
        })

    return render_template(
        'admin/dashboard.html',
        vendedores=vendedores,
        vendedor_id_filtro=vendedor_id_filtro,
        efectividad_despacho_pct=efectividad_despacho_pct,
        total_unidades_solicitadas=total_unidades_solicitadas,
        pedidos_entregados_count=pedidos_entregados_count,
        producto_top_nombre=producto_top_nombre,
        tasa_cumplimiento=tasa_cumplimiento,
        pedidos_completos=pedidos_completos,
        pedidos_incompletos=pedidos_incompletos,
        promedio_unidades_pedido=promedio_unidades_pedido,
        tiempo_promedio_str=tiempo_promedio_str,
        top_3_vendedores=top_3_vendedores,
        gestion_vendedores=gestion_vendedores
    )

@admin_bp.route('/admin/cargar_masiva', methods=['GET', 'POST'])
@login_required
def cargar_masiva():
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        file = request.files.get('file_excel')
        if not file or file.filename == '':
            flash('Por favor selecciona un archivo Excel válido.', 'warning')
            return redirect(url_for('admin.cargar_masiva'))

        try:
            df = pd.read_excel(file)
            columnas_requeridas = ['CODIGO', 'DESCRIPCION', 'CATEGORIA', 'UNIDAD_MEDIDA']

            if not all(col in df.columns for col in columnas_requeridas):
                flash(f'El archivo Excel debe contener las columnas: {", ".join(columnas_requeridas)}', 'danger')
                return redirect(url_for('admin.cargar_masiva'))

            procesados = 0
            for index, row in df.iterrows():
                codigo = str(row['CODIGO']).strip()
                descripcion = str(row['DESCRIPCION']).strip()
                nombre_categoria = str(row['CATEGORIA']).strip()
                unidad = str(row['UNIDAD_MEDIDA']).strip()

                categoria = Categoria.query.filter_by(nombre=nombre_categoria).first()
                if not categoria:
                    categoria = Categoria(nombre=nombre_categoria)
                    db.session.add(categoria)
                    db.session.flush()

                producto = Producto.query.filter_by(codigo=codigo).first()
                if producto:
                    producto.descripcion = descripcion
                    producto.categoria_id = categoria.id
                    producto.unidad_medida = unidad
                else:
                    nuevo_producto = Producto(
                        codigo=codigo,
                        descripcion=descripcion,
                        categoria_id=categoria.id,
                        unidad_medida=unidad,
                        imagen=None
                    )
                    db.session.add(nuevo_producto)
                
                procesados += 1

            db.session.commit()
            flash(f'¡Carga masiva exitosa! Se procesaron {procesados} productos correctamente manteniendo sus imágenes.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al procesar el archivo Excel: {str(e)}', 'danger')

        return redirect(url_for('admin.cargar_masiva'))

    return render_template('admin/cargar_masiva.html')

@admin_bp.route('/admin/descargar_plantilla')
@login_required
def descargar_plantilla():
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('admin.dashboard'))

    datos = {
        'CODIGO': ['G-001', 'S-001', 'B-001'],
        'DESCRIPCION': ['Galletas ChocoChips 120g', 'Papas Onduladas 45g', 'Jugo Naranja 250ml'],
        'CATEGORIA': ['Galletas', 'Snacks', 'Bebidas'],
        'UNIDAD_MEDIDA': ['Unidades', 'Unidades', 'Unidades']
    }
    df = pd.DataFrame(datos)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Plantilla_Articulos')
    output.seek(0)

    return send_file(
        output,
        download_name='plantilla_maestro_articulos.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@admin_bp.route('/admin/gestion_vendedores')
@login_required
def gestion_vendedores():
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('admin.dashboard'))

    vehiculos = VehiculoMovil.query.all()
    usuarios = Usuario.query.all()
    return render_template('admin/gestion_vendedores.html', vehiculos=vehiculos, usuarios=usuarios)

@admin_bp.route('/admin/crear_vehiculo', methods=['POST'])
@login_required
def crear_vehiculo():
    if current_user.rol not in ['admin', 'webmaster', 'analista']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('admin.dashboard'))

    codigo = request.form.get('codigo_vehiculo')
    descripcion = request.form.get('descripcion')

    if VehiculoMovil.query.filter_by(codigo_vehiculo=codigo).first():
        flash('El código de vehículo ya existe.', 'warning')
    else:
        nuevo_v = VehiculoMovil(codigo_vehiculo=codigo, descripcion=descripcion)
        db.session.add(nuevo_v)
        db.session.commit()
        flash(f'¡Vehículo {codigo} registrado con éxito!', 'success')

    return redirect(url_for('admin.gestion_vendedores'))

@admin_bp.route('/admin/eliminar_vehiculo/<int:vehiculo_id>', methods=['POST'])
@login_required
def eliminar_vehiculo(vehiculo_id):
    if current_user.rol not in ['admin', 'webmaster']:
        flash('Solo el Webmaster o Administrador puede eliminar almacenes móviles.', 'danger')
        return redirect(url_for('admin.gestion_vendedores'))

    vehiculo = VehiculoMovil.query.get_or_404(vehiculo_id)
    codigo = vehiculo.codigo_vehiculo

    try:
        vendedores_asociados = Usuario.query.filter_by(vehiculo_id=vehiculo.id).all()
        for v in vendedores_asociados:
            v.vehiculo_id = None
        
        db.session.delete(vehiculo)
        db.session.commit()
        flash(f'¡El Almacén Móvil "{codigo}" ha sido eliminado exitosamente!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al intentar eliminar el vehículo: {str(e)}', 'danger')

    return redirect(url_for('admin.gestion_vendedores'))

@admin_bp.route('/admin/crear_usuario', methods=['POST'])
@login_required
def crear_usuario():
    if current_user.rol not in ['admin', 'webmaster']:
        flash('Acceso no autorizado.', 'danger')
        return redirect(url_for('admin.dashboard'))

    nombre_completo = request.form.get('nombre_completo')
    username = request.form.get('username')
    password = request.form.get('password')
    rol = request.form.get('rol')
    vehiculo_id = request.form.get('vehiculo_id')

    if Usuario.query.filter_by(username=username).first():
        flash('El nombre de usuario ya está registrado.', 'warning')
    else:
        v_id = int(vehiculo_id) if vehiculo_id and rol == 'vendedor' else None
        nuevo_u = Usuario(
            nombre_completo=nombre_completo,
            username=username,
            password=generate_password_hash(password),
            rol=rol,
            activo=True,
            vehiculo_id=v_id
        )
        db.session.add(nuevo_u)
        db.session.commit()
        flash(f'¡Usuario {nombre_completo} creado con éxito!', 'success')

    return redirect(url_for('admin.gestion_vendedores'))

@admin_bp.route('/admin/cambiar_rol_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def cambiar_rol_usuario(usuario_id):
    if current_user.rol not in ['admin', 'webmaster']:
        flash('Solo el Webmaster o Administrador puede cambiar roles.', 'danger')
        return redirect(url_for('admin.gestion_vendedores'))

    usuario = Usuario.query.get_or_404(usuario_id)
    nuevo_rol = request.form.get('nuevo_rol')

    if nuevo_rol in ['vendedor', 'almacenista', 'admin', 'webmaster', 'analista']:
        usuario.rol = nuevo_rol
        if nuevo_rol != 'vendedor':
            usuario.vehiculo_id = None
        db.session.commit()
        flash(f'¡Rol de {usuario.nombre_completo} actualizado a {nuevo_rol.capitalize()}!', 'success')
    else:
        flash('Rol no válido.', 'danger')

    return redirect(url_for('admin.gestion_vendedores'))

@admin_bp.route('/admin/toggle_estado_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def toggle_estado_usuario(usuario_id):
    if current_user.rol not in ['admin', 'webmaster']:
        flash('Solo el Webmaster o Administrador puede bloquear/activar usuarios.', 'danger')
        return redirect(url_for('admin.gestion_vendedores'))

    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('No puedes bloquear tu propia cuenta.', 'warning')
        return redirect(url_for('admin.gestion_vendedores'))

    usuario.activo = not usuario.activo
    db.session.commit()

    estado = "activado" if usuario.activo else "bloqueado"
    flash(f'El usuario {usuario.nombre_completo} ha sido {estado}.', 'info')

    return redirect(url_for('admin.gestion_vendedores'))

@admin_bp.route('/admin/eliminar_usuario/<int:usuario_id>', methods=['POST'])
@login_required
def eliminar_usuario(usuario_id):
    if current_user.rol not in ['admin', 'webmaster']:
        flash('Solo el Webmaster o Administrador puede eliminar usuarios.', 'danger')
        return redirect(request.referrer or url_for('admin.gestion_vendedores'))

    usuario = Usuario.query.get_or_404(usuario_id)
    if usuario.id == current_user.id:
        flash('No puedes eliminar tu propia cuenta.', 'warning')
        return redirect(request.referrer or url_for('admin.gestion_vendedores'))

    try:
        db.session.delete(usuario)
        db.session.commit()
        flash(f'El usuario {usuario.nombre_completo} ha sido eliminado definitivamente.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('No se puede eliminar el usuario si posee pedidos asociados. Te sugerimos bloquearlo en su lugar.', 'warning')

    return redirect(request.referrer or url_for('admin.gestion_vendedores'))