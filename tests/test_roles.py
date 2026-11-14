"""Matriz de permisos admin / vendedor."""


def _sesion_vendedor(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Vendedor Prueba"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    return creado, {"Authorization": f"Bearer {login['token']}"}


def test_vendedor_ve_el_inventario_del_admin(cliente_api, auth_admin):
    cliente_api.post(
        "/productos/", json={"nombre": "Camisa", "stock": 7, "precio": "150"},
        headers=auth_admin.headers,
    )
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    r = cliente_api.get("/productos/", headers=headers)
    assert r.status_code == 200, r.text
    assert [p["nombre"] for p in r.json()] == ["Camisa"]


def test_vendedor_puede_vender(cliente_api, auth_admin):
    producto = cliente_api.post(
        "/productos/", json={"nombre": "Gorra", "stock": 3, "precio": "100"},
        headers=auth_admin.headers,
    ).json()
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    r = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto["id"], "cantidad": 1}]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 100.0

    # El stock es el mismo del negocio: la venta del vendedor lo descuenta.
    actual = cliente_api.get(f"/productos/{producto['id']}", headers=auth_admin.headers).json()
    assert actual["stock"] == 2

    vendido = cliente_api.get("/ventas/", headers=headers).json()
    assert vendido["total"] == 1
    assert vendido["items"][0]["vendedor_nombre"] == "Vendedor Prueba"


def test_vendedor_no_crea_ni_edita_productos(cliente_api, auth_admin):
    producto = cliente_api.post(
        "/productos/", json={"nombre": "Bufanda", "stock": 2, "precio": "50"},
        headers=auth_admin.headers,
    ).json()
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    assert cliente_api.post(
        "/productos/", json={"nombre": "Nuevo", "precio": "1"}, headers=headers
    ).status_code == 403
    assert cliente_api.put(
        f"/productos/{producto['id']}",
        json={"nombre": "Cambiado", "precio": "1"},
        headers=headers,
    ).status_code == 403
    assert cliente_api.delete(f"/productos/{producto['id']}", headers=headers).status_code == 403
    assert cliente_api.post(
        f"/productos/{producto['id']}/recargar", json={"cantidad": 5}, headers=headers
    ).status_code == 403


def test_vendedor_no_edita_clientes_ni_abona(cliente_api, auth_admin):
    cliente = cliente_api.post(
        "/clientes/", json={"nombre": "Cliente", "credito_limite": "100"},
        headers=auth_admin.headers,
    ).json()
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    assert cliente_api.get("/clientes/", headers=headers).status_code == 200
    assert cliente_api.post(
        "/clientes/", json={"nombre": "Otro"}, headers=headers
    ).status_code == 403
    assert cliente_api.put(
        f"/clientes/{cliente['id']}", json={"nombre": "X"}, headers=headers
    ).status_code == 403
    assert cliente_api.post(
        f"/clientes/{cliente['id']}/abono", json={"monto": "10"}, headers=headers
    ).status_code == 403
    assert cliente_api.delete(f"/clientes/{cliente['id']}", headers=headers).status_code == 403


def test_vendedor_no_anula_ventas_ni_cierra_caja(cliente_api, auth_admin):
    producto = cliente_api.post(
        "/productos/", json={"nombre": "Short", "stock": 3, "precio": "90"},
        headers=auth_admin.headers,
    ).json()
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    venta = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto["id"], "cantidad": 1}]},
        headers=headers,
    ).json()

    assert cliente_api.delete(f"/ventas/{venta['id']}", headers=headers).status_code == 403
    assert cliente_api.get("/ventas/cierre", headers=headers).status_code == 403


def test_vendedor_no_accede_a_reportes_ni_organizacion(cliente_api, auth_admin):
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    for ruta in (
        "/reportes/dashboard",
        "/reportes/margenes",
        "/organizacion/anios",
        "/promociones/",
        "/proveedores/",
        "/gastos/",
        "/compras/",
    ):
        assert cliente_api.get(ruta, headers=headers).status_code == 403, ruta


def test_vendedor_no_cambia_la_configuracion_del_negocio(cliente_api, auth_admin):
    _, headers = _sesion_vendedor(cliente_api, auth_admin)

    perfil = cliente_api.get("/auth/perfil", headers=headers)
    assert perfil.status_code == 200
    assert perfil.json()["rol"] == "vendedor"
    assert perfil.json()["nombre_negocio"] == "Negocio jefe"

    assert cliente_api.put(
        "/auth/perfil",
        json={"nombre_negocio": "Robado", "tasa_cambio": 40},
        headers=headers,
    ).status_code == 403
    assert cliente_api.put(
        "/auth/tasa-cambio", json={"tasa_cambio": 40}, headers=headers
    ).status_code == 403


def test_aislamiento_entre_negocios_con_vendedores(cliente_api, auth_admin, crear_usuario):
    producto = cliente_api.post(
        "/productos/", json={"nombre": "Privado", "stock": 5, "precio": "10"},
        headers=auth_admin.headers,
    ).json()

    otro_admin = crear_usuario(usuario="otro_jefe", rol="admin")
    otro_hijo = crear_usuario(
        usuario="otro_vendedor", rol="vendedor", dueno_id=otro_admin["id"]
    )
    headers_ajenos = {"Authorization": f"Bearer {otro_hijo['token']}"}

    propios = cliente_api.get("/productos/", headers=headers_ajenos).json()
    assert propios == []

    r = cliente_api.get(f"/productos/{producto['id']}", headers=headers_ajenos)
    assert r.status_code == 404
