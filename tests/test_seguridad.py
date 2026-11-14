import pytest


def test_login_correcto(cliente_api, crear_usuario):
    crear_usuario(usuario="carla", password="Segura123")
    r = cliente_api.post("/auth/login", json={"usuario": "carla", "password": "Segura123"})
    assert r.status_code == 200
    assert r.json()["token"]


def test_login_incorrecto(cliente_api, crear_usuario):
    crear_usuario(usuario="carla", password="Segura123")
    r = cliente_api.post("/auth/login", json={"usuario": "carla", "password": "otra12345"})
    assert r.status_code == 401
    # Mismo mensaje exista o no el usuario (no filtra cuentas).
    r2 = cliente_api.post("/auth/login", json={"usuario": "fantasma", "password": "otra12345"})
    assert r2.status_code == 401
    assert r.json()["detail"] == r2.json()["detail"]


def test_sin_token_no_se_accede(cliente_api):
    assert cliente_api.get("/productos/").status_code == 401
    assert cliente_api.get("/clientes/").status_code == 401
    assert cliente_api.get("/ventas/").status_code == 401
    assert cliente_api.get("/reportes/dashboard").status_code == 401


def test_token_falso_rechazado(cliente_api):
    r = cliente_api.get("/productos/", headers={"Authorization": "Bearer inventado"})
    assert r.status_code == 401


def test_cambio_de_password_revoca_tokens(cliente_api, crear_usuario):
    datos = crear_usuario(usuario="dora", password="Segura123")
    headers = {"Authorization": f"Bearer {datos['token']}"}

    r = cliente_api.put(
        "/auth/password",
        json={"password_actual": "Segura123", "password_nuevo": "NuevaClave456"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    # El token emitido antes del cambio deja de valer.
    assert cliente_api.get("/productos/", headers=headers).status_code == 401

    login = cliente_api.post("/auth/login", json={"usuario": "dora", "password": "NuevaClave456"})
    assert login.status_code == 200


def test_password_debil_rechazada_en_registro(cliente_api):
    r = cliente_api.post(
        "/auth/registro",
        json={"usuario": "nuevo", "password": "12345678", "nombre_negocio": "X"},
    )
    assert r.status_code == 422


def test_aislamiento_entre_cuentas(cliente_api, auth):
    otro = auth.otro("beto")
    otras = {"Authorization": f"Bearer {otro['token']}"}

    producto = cliente_api.post(
        "/productos/",
        json={"nombre": "Privado", "stock": 5, "precio": "10.00"},
        headers=auth.headers,
    ).json()
    cliente = cliente_api.post(
        "/clientes/", json={"nombre": "Privado", "credito_limite": "10.00"}, headers=auth.headers
    ).json()
    venta = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto["id"], "cantidad": 1}]},
        headers=auth.headers,
    ).json()

    # Lectura
    assert cliente_api.get(f"/productos/{producto['id']}", headers=otras).status_code == 404
    assert cliente_api.get(f"/clientes/{cliente['id']}", headers=otras).status_code == 404
    assert cliente_api.get(f"/ventas/{venta['id']}", headers=otras).status_code == 404
    assert cliente_api.get(f"/facturas/{venta['id']}").status_code == 401

    # Escritura
    assert cliente_api.put(
        f"/productos/{producto['id']}",
        json={"nombre": "Hackeado", "stock": 0, "precio": "0"},
        headers=otras,
    ).status_code == 404
    assert cliente_api.delete(f"/ventas/{venta['id']}", headers=otras).status_code == 404
    assert cliente_api.delete(f"/clientes/{cliente['id']}", headers=otras).status_code == 404

    # No puede vender un producto ajeno
    r = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": producto["id"], "cantidad": 1}]},
        headers=otras,
    )
    assert r.status_code == 404

    # Ni ver sus movimientos
    assert cliente_api.get(f"/productos/{producto['id']}/movimientos", headers=otras).status_code == 200
    assert cliente_api.get(f"/productos/{producto['id']}/movimientos", headers=otras).json() == []

    # El producto original sigue intacto
    original = cliente_api.get(f"/productos/{producto['id']}", headers=auth.headers).json()
    assert original["nombre"] == "Privado"
    assert original["stock"] == 4


def test_no_se_puede_enganchar_promo_ajena(cliente_api, auth):
    otro = auth.otro("beto")
    otras = {"Authorization": f"Bearer {otro['token']}"}

    promo = cliente_api.post(
        "/promociones/",
        json={"nombre": "De Ana", "tipo": "porcentaje", "valor": "50", "activa": True},
        headers=auth.headers,
    ).json()

    r = cliente_api.post(
        "/productos/",
        json={"nombre": "Intruso", "stock": 1, "precio": "10", "promocion_id": promo["id"]},
        headers=otras,
    )
    assert r.status_code == 400


def test_tokens_de_otra_cuenta_no_mezclan_datos(cliente_api, crear_usuario):
    a = crear_usuario("user_a")
    b = crear_usuario("user_b")
    for datos, nombre in ((a, "A"), (b, "B")):
        cliente_api.post(
            "/productos/",
            json={"nombre": f"Producto {nombre}", "stock": 1, "precio": "1"},
            headers={"Authorization": f"Bearer {datos['token']}"},
        )

    lista_a = cliente_api.get(
        "/productos/", headers={"Authorization": f"Bearer {a['token']}"}
    ).json()
    assert [p["nombre"] for p in lista_a] == ["Producto A"]


def test_codigo_de_verificacion_nunca_se_devuelve(cliente_api, crear_usuario):
    datos = crear_usuario("eva")
    headers = {"Authorization": f"Bearer {datos['token']}"}
    r = cliente_api.post("/auth/enviar-verificacion", headers=headers)
    # Sin email configurado no hay nada que enviar y el mensaje no filtra códigos.
    assert r.status_code == 400
    assert "codigo" not in r.text.lower()


@pytest.mark.parametrize("ruta", ["/productos/", "/clientes/", "/ventas/", "/reportes/dashboard"])
def test_respuestas_de_api_sin_cache(cliente_api, auth, ruta):
    r = cliente_api.get(ruta, headers=auth.headers)
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"


def test_cuerpo_demasiado_grande_rechazado(cliente_api, auth):
    from main import MAX_CUERPO_BYTES

    enorme = "x" * (MAX_CUERPO_BYTES + 10)
    r = cliente_api.post(
        "/productos/",
        content=enorme,
        headers={**auth.headers, "Content-Type": "application/json"},
    )
    assert r.status_code == 413
