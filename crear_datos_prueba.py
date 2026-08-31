from app import create_app, db
from app.models import Usuario, VehiculoMovil, Categoria, Producto
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    # 1. Eliminar todas las tablas viejas para aplicar la nueva columna usuarios.activo
    db.drop_all()
    
    # 2. Crear las tablas nuevamente con la estructura actualizada
    db.create_all()

    # 3. Crear Vehículo Móvil (Almacén Móvil)
    vehiculo = VehiculoMovil(
        codigo_vehiculo='CAMION-01',
        descripcion='Camión Autoventa Ruta Maracay - Placa A12B34'
    )
    db.session.add(vehiculo)
    db.session.commit()

    # 4. Crear Usuarios de prueba (Webmaster, Almacenista y Vendedor)
    webmaster_user = Usuario(
        username='webmaster',
        password=generate_password_hash('123456'),
        nombre_completo='Jean Carlos (Webmaster)',
        cedula='V-00000000',
        telefono='0414-0000000',
        rol='webmaster',
        activo=True,
        pregunta_secreta='¿En qué ciudad naciste?',
        respuesta_secreta=generate_password_hash('maracaibo')
    )
    db.session.add(webmaster_user)

    admin_user = Usuario(
        username='admin',
        password=generate_password_hash('123456'),
        nombre_completo='Pedro Almacenista',
        cedula='V-11111111',
        telefono='0414-1111111',
        rol='almacenista',
        activo=True,
        pregunta_secreta='¿En qué ciudad naciste?',
        respuesta_secreta=generate_password_hash('maracay')
    )
    db.session.add(admin_user)

    vendedor_user = Usuario(
        username='jean',
        password=generate_password_hash('123456'),
        nombre_completo='Vendedor Prueba',
        cedula='V-22222222',
        telefono='0412-2222222',
        rol='vendedor',
        activo=True,
        vehiculo_id=vehiculo.id,
        pregunta_secreta='¿En qué ciudad naciste?',
        respuesta_secreta=generate_password_hash('maracaibo')
    )
    db.session.add(vendedor_user)

    # 5. Crear Categorías de prueba
    cat_galletas = Categoria(nombre='Galletas')
    cat_snacks = Categoria(nombre='Snacks')
    db.session.add(cat_galletas)
    db.session.add(cat_snacks)
    db.session.commit()

    # 6. Crear Productos de prueba
    p1 = Producto(
        codigo='G-001',
        descripcion='Galletas Munchy ChocoChips 120g',
        categoria_id=cat_galletas.id,
        unidad_medida='Unidades',
        stock_almacen=500
    )
    p2 = Producto(
        codigo='S-001',
        descripcion='Papas Munchy Onduladas 45g',
        categoria_id=cat_snacks.id,
        unidad_medida='Unidades',
        stock_almacen=300
    )
    db.session.add(p1)
    db.session.add(p2)

    db.session.commit()
    print("==================================================")
    print(" ¡Base de datos recreada con Perfil Webmaster!")
    print(" Cuentas de acceso:")
    print("  - Webmaster:   Usuario: webmaster | Clave: 123456")
    print("  - Almacenista: Usuario: admin     | Clave: 123456")
    print("  - Vendedor:    Usuario: jean      | Clave: 123456")
    print("==================================================")