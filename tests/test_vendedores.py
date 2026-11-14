from Backend.routers.auth import crear_token
from Backend.routers.vendedores import MAX_VENDEDORES


def crear(client, headers, nombre="Ana Pérez", **extra):
    return client.post("/vendedores/", json={"nombre": nombre, **extra}, headers=headers)


def test_crea_vendedor_con_credenciales(cliente_api, auth_admin):
    r = crear(cliente_api, auth_admin.headers, nombre="Ana Pérez")
    assert r.status_code == 201, r.text
    datos = r.json()
    assert datos["usuario"] == "ana.perez"
    assert len(datos["password"]) >= 8
    assert datos["activo"] is True


def test_el_admin_puede_ver_la_contrasena_despues(cliente_api, auth_admin):
    creado = crear(cliente_api, auth_admin.headers, nombre="Beto Ruiz").json()

    r = cliente_api.get(
        f"/vendedores/{creado['id']}/credenciales", headers=auth_admin.headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["password"] == creado["password"]


def test_limite_de_diez_vendedores(cliente_api, auth_admin):
    for i in range(MAX_VENDEDORES):
        r = crear(cliente_api, auth_admin.headers, nombre=f"Vendedor {i}")
        assert r.status_code == 201, r.text

    r = crear(cliente_api, auth_admin.headers, nombre="Vendedor extra")
    assert r.status_code == 409
    assert "Límite alcanzado" in r.json()["detail"]

    listado = cliente_api.get("/vendedores/", headers=auth_admin.headers).json()
    assert listado["total"] == MAX_VENDEDORES
    assert listado["limite"] == MAX_VENDEDORES


def test_el_vendedor_puede_iniciar_sesion_con_las_credenciales(cliente_api, auth_admin):
    creado = crear(cliente_api, auth_admin.headers, nombre="Carla Mena").json()

    r = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    )
    assert r.status_code == 200, r.text
    sesion = r.json()
    assert sesion["rol"] == "vendedor"
    assert sesion["negocio_id"] == auth_admin.usuario_id


def test_usuario_duplicado_es_rechazado(cliente_api, auth_admin):
    primero = crear(cliente_api, auth_admin.headers, nombre="Dora Lau").json()

    r = crear(cliente_api, auth_admin.headers, nombre="Otra", usuario=primero["usuario"])
    assert r.status_code == 409
    assert "ya está en uso" in r.json()["detail"]


def test_editar_contrasena_revoca_la_sesion_anterior(cliente_api, auth_admin, crear_usuario):
    creado = crear(cliente_api, auth_admin.headers, nombre="Eva Sol").json()
    from Backend.db.database import SessionLocal
    from Backend.db.models import Usuario

    with SessionLocal() as session:
        v = session.query(Usuario).filter(Usuario.usuario == creado["usuario"]).first()
        token_viejo = crear_token(v.id, v.usuario, v.token_version or 0)
        v_id = v.id

    r = cliente_api.get(
        "/productos/", headers={"Authorization": f"Bearer {token_viejo}"}
    )
    assert r.status_code == 200

    r = cliente_api.put(
        f"/vendedores/{v_id}",
        json={"password": "NuevaClave123"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text

    r = cliente_api.get("/productos/", headers={"Authorization": f"Bearer {token_viejo}"})
    assert r.status_code == 401


def test_borrar_vendedor_con_ventas_lo_desactiva(cliente_api, auth_admin):
    creado = crear(cliente_api, auth_admin.headers, nombre="Fito Paz").json()

    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers_vendedor = {"Authorization": f"Bearer {login['token']}"}

    producto = cliente_api.post(
        "/productos/", json={"nombre": "Uniforme", "stock": 5, "precio": "20"},
        headers=auth_admin.headers,
    ).json()
    r = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto["id"], "cantidad": 1}]},
        headers=headers_vendedor,
    )
    assert r.status_code == 200, r.text

    r = cliente_api.delete(f"/vendedores/{creado['id']}", headers=auth_admin.headers)
    assert r.status_code == 200, r.text
    assert r.json()["desactivado"] is True

    r = cliente_api.get("/productos/", headers=headers_vendedor)
    assert r.status_code == 401


def test_vendedor_inactivo_no_puede_usar_su_token(cliente_api, crear_usuario):
    admin = crear_usuario(usuario="dueno", rol="admin")
    vendedor = crear_usuario(
        usuario="inactivo", rol="vendedor", dueno_id=admin["id"], activo=False
    )

    r = cliente_api.get(
        "/productos/", headers={"Authorization": f"Bearer {vendedor['token']}"}
    )
    assert r.status_code == 401
    assert "desactivada" in r.json()["detail"]


def test_un_admin_no_ve_vendedores_de_otro(cliente_api, auth_admin, crear_usuario):
    creado = crear(cliente_api, auth_admin.headers, nombre="Gina Rí­os").json()

    otro = crear_usuario(usuario="ajeno", rol="admin")
    r = cliente_api.get(
        f"/vendedores/{creado['id']}/credenciales",
        headers={"Authorization": f"Bearer {otro['token']}"},
    )
    assert r.status_code == 404


def test_vendedor_no_puede_gestionar_vendedores(cliente_api, auth_admin):
    creado = crear(cliente_api, auth_admin.headers, nombre="Hugo Cano").json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    assert cliente_api.get("/vendedores/", headers=headers).status_code == 403
    assert cliente_api.post(
        "/vendedores/", json={"nombre": "Otro"}, headers=headers
    ).status_code == 403


def test_borrar_la_cuenta_del_admin_borra_a_sus_vendedores(cliente_api, crear_usuario):
    admin = crear_usuario(usuario="dueno_total", password="Segura123", rol="admin")
    headers = {"Authorization": f"Bearer {admin['token']}"}

    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Hijo Temporal"}, headers=headers
    ).json()
    login_hijo = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers_hijo = {"Authorization": f"Bearer {login_hijo['token']}"}

    r = cliente_api.request(
        "DELETE", "/auth/cuenta", json={"password": "Segura123"}, headers=headers
    )
    assert r.status_code == 200, r.text

    # El token del vendedor deja de valer y su usuario ya no existe.
    assert cliente_api.get("/productos/", headers=headers_hijo).status_code == 401
    assert cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).status_code == 401
