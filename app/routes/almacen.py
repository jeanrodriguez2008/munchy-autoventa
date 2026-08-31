import os
from io import BytesIO
from datetime import datetime
import pytz
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from app.models import Pedido, Producto, DetallePedido, get_caracas_now
from app import db

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

almacen_bp = Blueprint('almacen', __name__)

@almacen_bp.route('/almacen/panel')
@login_required
def panel():
    if current_user.rol not in ['almacenista', 'admin', 'webmaster', 'analista']:
        flash('Acceso no autorizado para este rol.', 'danger')
        return redirect(url_for('auth.login'))
        
    pedidos = Pedido.query.order_by(Pedido.fecha_creacion.desc()).all()
    return render_template('almacen/panel.html', pedidos=pedidos)

@almacen_bp.route('/almacen/actualizar_despacho/<int:pedido_id>', methods=['POST'])
@login_required
def actualizar_despacho(pedido_id):
    if current_user.rol not in ['almacenista', 'admin', 'webmaster', 'analista']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('auth.login'))

    pedido = Pedido.query.get_or_404(pedido_id)

    try:
        for detalle in pedido.detalles:
            field_name = f"despachado_{detalle.id}"
            if field_name in request.form:
                nueva_cant = int(request.form.get(field_name, 0))
                detalle.cantidad_despachada = max(0, nueva_cant)
        
        db.session.commit()
        flash(f'¡Cantidades de despacho del Pedido #{pedido.id} guardadas con éxito!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al actualizar cantidades despachadas: {str(e)}', 'danger')

    return redirect(url_for('almacen.panel'))

@almacen_bp.route('/almacen/toggle_estatus/<int:pedido_id>', methods=['POST'])
@login_required
def toggle_estatus(pedido_id):
    if current_user.rol not in ['almacenista', 'admin', 'webmaster', 'analista']:
        flash('Acceso denegado.', 'danger')
        return redirect(url_for('auth.login'))

    pedido = Pedido.query.get_or_404(pedido_id)

    try:
        if pedido.estatus == 'Pendiente':
            # Pasar a ENTREGADO: Asignar hora de despacho en Venezuela y descontar de stock
            for detalle in pedido.detalles:
                producto = Producto.query.get(detalle.producto_id)
                if producto:
                    cant_a_descontar = detalle.cantidad_despachada if detalle.cantidad_despachada is not None else detalle.cantidad
                    producto.stock_almacen = max(0, producto.stock_almacen - cant_a_descontar)
            
            pedido.estatus = 'Entregado'
            pedido.fecha_despacho = get_caracas_now()
            flash(f'¡Pedido #{pedido.id} marcado como ENTREGADO!', 'success')

        else:
            # Revertir a PENDIENTE (Desmarcar): Devolver al stock, limpiar fecha y conformidad
            for detalle in pedido.detalles:
                producto = Producto.query.get(detalle.producto_id)
                if producto:
                    cant_a_devolver = detalle.cantidad_despachada if detalle.cantidad_despachada is not None else detalle.cantidad
                    producto.stock_almacen += cant_a_devolver

            pedido.estatus = 'Pendiente'
            pedido.fecha_despacho = None
            pedido.recibido_conforme = False
            pedido.fecha_recepcion = None
            flash(f'Pedido #{pedido.id} devuelto a estatus PENDIENTE.', 'info')

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Error al cambiar estatus del pedido: {str(e)}', 'danger')

    return redirect(url_for('almacen.panel'))

@almacen_bp.route('/almacen/exportar_pdf/<int:pedido_id>')
@login_required
def exportar_pdf(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'HeaderTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#D9534F'),
        alignment=0
    )

    subtitle_style = ParagraphStyle(
        'HeaderSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#6C757D')
    )
    
    normal_style = ParagraphStyle(
        'NormalStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#212529')
    )

    header_table_style = ParagraphStyle(
        'HeaderTableStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=12,
        fontName='Helvetica-Bold',
        textColor=colors.whitesmoke
    )

    story = []

    # Encabezado con Logo oficial desde app/static/img/logo.png
    logo_path = os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
    textos_header = [
        Paragraph("<b>ALIMENTOS MUNCHY, C.A.</b>", title_style),
        Paragraph(f"<b>Comprobante de Despacho - Pedido #{pedido.id}</b>", subtitle_style)
    ]

    if os.path.exists(logo_path):
        img_logo = RLImage(logo_path, width=120, height=45)
        encabezado_data = [[img_logo, textos_header]]
    else:
        encabezado_data = [[Paragraph("<b>MUNCHY</b>", title_style), textos_header]]

    tabla_encabezado = Table(encabezado_data, colWidths=[130, 410])
    tabla_encabezado.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(tabla_encabezado)
    story.append(Spacer(1, 10))

    # Información del Pedido y Horas de Venezuela
    almacen_movil_nombre = pedido.vendedor.vehiculo.codigo_vehiculo if pedido.vendedor and pedido.vendedor.vehiculo else 'N/A'
    fecha_pedido_fmt = pedido.fecha_creacion.strftime('%d/%m/%Y %I:%M %p')
    fecha_despacho_fmt = pedido.fecha_despacho.strftime('%d/%m/%Y %I:%M %p') if pedido.fecha_despacho else 'Pendiente por despachar'
    fecha_recepcion_fmt = pedido.fecha_recepcion.strftime('%d/%m/%Y %I:%M %p') if pedido.fecha_recepcion else 'Pendiente'

    info_text = f"""
    <b>Vendedor:</b> {pedido.vendedor.nombre_completo if pedido.vendedor else 'N/A'}<br/>
    <b>Almacén Móvil:</b> {almacen_movil_nombre}<br/>
    <b>Hora de Pedido (Vendedor):</b> {fecha_pedido_fmt}<br/>
    <b>Hora de Despacho (Almacén):</b> {fecha_despacho_fmt}<br/>
    <b>Hora Conformidad Vendedor:</b> {fecha_recepcion_fmt}<br/>
    <b>Estatus:</b> {pedido.estatus}
    """
    story.append(Paragraph(info_text, normal_style))
    story.append(Spacer(1, 15))

    # Tabla con Columnas
    data_tabla = [[
        Paragraph("<b>Código</b>", header_table_style),
        Paragraph("<b>Descripción del Producto</b>", header_table_style),
        Paragraph("<b>Cant. Solicitada</b>", header_table_style),
        Paragraph("<b>Cant. Despachada</b>", header_table_style)
    ]]

    for d in pedido.detalles:
        prod_codigo = d.producto.codigo if d.producto else 'N/A'
        prod_desc = d.producto.descripcion if d.producto else 'Producto no disponible'
        prod_unidad = d.producto.unidad_medida if d.producto else 'UND'
        cant_sol = f"{d.cantidad} {prod_unidad}"
        cant_desp = f"{d.cantidad_despachada if d.cantidad_despachada is not None else d.cantidad} {prod_unidad}"

        data_tabla.append([
            Paragraph(prod_codigo, normal_style),
            Paragraph(prod_desc, normal_style),
            Paragraph(cant_sol, normal_style),
            Paragraph(f"<b>{cant_desp}</b>", normal_style)
        ])

    tabla_productos = Table(data_tabla, colWidths=[80, 260, 100, 100])
    tabla_productos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#212529')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DEE2E6')),
    ]))
    story.append(tabla_productos)
    story.append(Spacer(1, 40))

    # Conformidad o Línea de Firma
    if pedido.recibido_conforme:
        firma_vendedor_text = f"<b>[ RECIBIDO CONFORME ]</b><br/>Confirmado digitalmente el {fecha_recepcion_fmt}<br/><b>Firma del Vendedor</b>"
    else:
        firma_vendedor_text = "____________________________________<br/><b>Firma del Vendedor</b>"

    data_firmas = [
        [
            Paragraph(firma_vendedor_text, normal_style),
            Paragraph("____________________________________<br/><b>Firma del Despachador</b>", normal_style)
        ]
    ]

    tabla_firmas = Table(data_firmas, colWidths=[270, 270])
    tabla_firmas.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    story.append(tabla_firmas)

    doc.build(story)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=False,
        download_name=f"Pedido_{pedido.id}_MunchyAutoventa.pdf",
        mimetype='application/pdf'
    )