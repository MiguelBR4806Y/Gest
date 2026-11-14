from Backend.tiempo import hoy_local


def _producto(client, headers, stock=10, precio="10.00"):
    return client.post(
        "/productos/",
        json={"nombre": "P", "stock": stock, "precio": precio},
        headers=headers,
    ).json()


def _cliente(client, headers, limite="100.00"):
    return client.post(
        "/clientes/", json={"nombre": "Cliente", "credito_limite": limite}, headers=headers
    ).json()


def test_codigo_unico_de_seis_caracteres(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers)
    assert len(c["codigo"]) == 6
    assert c["codigo"].isalnum()

    otro = cliente_api.post(
        "/clientes/", json={"nombre": "Otro", "credito_limite": "0"}, headers=auth.headers
    ).json()
    assert otro["codigo"] != c["codigo"]


def test_ultima_compra_ignora_ventas_anuladas(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers)
    p = _producto(cliente_api, auth.headers)
    venta = cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "cliente_id": c["id"],
              "items": [{"producto_id": p["id"], "cantidad": 1}]},
        headers=auth.headers,
    ).json()

    cliente_api.request("DELETE", f"/ventas/{venta['id']}", json={"motivo": "x"}, headers=auth.headers)

    listado = cliente_api.get("/clientes/", headers=auth.headers).json()
    assert listado[0]["ultima_compra"] == "Sin compras"


def test_abono_reduce_el_saldo(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers, limite="200.00")
    p = _producto(cliente_api, auth.headers, precio="50.00")

    cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "credito", "cliente_id": c["id"],
              "items": [{"producto_id": p["id"], "cantidad": 2}]},
        headers=auth.headers,
    )

    r = cliente_api.post(
        f"/clientes/{c['id']}/abono", json={"monto": "40.00", "nota": "pago"}, headers=auth.headers
    )
    assert r.status_code == 200, r.text
    assert r.json()["credito_usado"] == 60.0
    assert r.json()["credito_disponible"] == 140.0

    exceso = cliente_api.post(
        f"/clientes/{c['id']}/abono", json={"monto": "1000.00"}, headers=auth.headers
    )
    assert exceso.status_code == 400


def test_abono_sin_saldo_es_rechazado(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers)
    r = cliente_api.post(
        f"/clientes/{c['id']}/abono", json={"monto": "10.00"}, headers=auth.headers
    )
    assert r.status_code == 400


def test_no_elimina_cliente_con_historial(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers)
    p = _producto(cliente_api, auth.headers, stock=5)

    cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "cliente_id": c["id"],
              "items": [{"producto_id": p["id"], "cantidad": 1}]},
        headers=auth.headers,
    )

    r = cliente_api.delete(f"/clientes/{c['id']}", headers=auth.headers)
    assert r.status_code == 409
    assert cliente_api.get(f"/clientes/{c['id']}", headers=auth.headers).status_code == 200


def test_elimina_cliente_sin_historial(cliente_api, auth):
    c = _cliente(cliente_api, auth.headers)
    assert cliente_api.delete(f"/clientes/{c['id']}", headers=auth.headers).status_code == 200
    assert cliente_api.get(f"/clientes/{c['id']}", headers=auth.headers).status_code == 404


def test_no_elimina_producto_vendido(cliente_api, auth):
    p = _producto(cliente_api, auth.headers, stock=5)
    cliente_api.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": p["id"], "cantidad": 1}]},
        headers=auth.headers,
    )
    r = cliente_api.delete(f"/productos/{p['id']}", headers=auth.headers)
    assert r.status_code == 409


def test_recargar_inventario_suma_stock(cliente_api, auth):
    p = _producto(cliente_api, auth.headers, stock=2)
    r = cliente_api.post(
        f"/productos/{p['id']}/recargar", json={"cantidad": 5}, headers=auth.headers
    )
    assert r.status_code == 200
    assert r.json()["stock_actual"] == 7
    assert cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()["stock"] == 7


def test_movimiento_salida_sin_stock_rechazado(cliente_api, auth):
    p = _producto(cliente_api, auth.headers, stock=1)
    r = cliente_api.post(
        f"/productos/{p['id']}/movimiento", json={"tipo": "salida", "cantidad": 5}, headers=auth.headers
    )
    assert r.status_code == 400
    assert cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()["stock"] == 1


def test_stock_bajo_usa_el_minimo_del_producto(cliente_api, auth):
    cliente_api.post(
        "/productos/",
        json={"nombre": "Alto mínimo", "stock": 8, "stock_minimo": 10, "precio": "1"},
        headers=auth.headers,
    )
    cliente_api.post(
        "/productos/",
        json={"nombre": "Bajo mínimo", "stock": 8, "stock_minimo": 2, "precio": "1"},
        headers=auth.headers,
    )
    nombres = [p["nombre"] for p in cliente_api.get("/productos/stock-bajo", headers=auth.headers).json()]
    assert nombres == ["Alto mínimo"]


def test_busqueda_de_productos(cliente_api, auth):
    for nombre in ("Coca Cola", "Pan dulce", "Coca Zero"):
        cliente_api.post(
            "/productos/",
            json={"nombre": nombre, "stock": 1, "precio": "1"},
            headers=auth.headers,
        )
    r = cliente_api.get("/productos/?q=coca", headers=auth.headers).json()
    assert {p["nombre"] for p in r} == {"Coca Cola", "Coca Zero"}

    vacio = cliente_api.get("/productos/?q=zzz", headers=auth.headers).json()
    assert vacio == []


def test_codigo_de_barras_unico_y_buscable(cliente_api, auth):
    codigo = "7501234567890"
    r = cliente_api.post(
        "/productos/",
        json={"nombre": "Con código", "stock": 3, "precio": "10", "codigo_barras": codigo},
        headers=auth.headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["codigo_barras"] == codigo

    escaneado = cliente_api.get(f"/productos/codigo/{codigo}", headers=auth.headers)
    assert escaneado.status_code == 200
    assert escaneado.json()["nombre"] == "Con código"

    duplicado = cliente_api.post(
        "/productos/",
        json={"nombre": "Otro", "stock": 1, "precio": "1", "codigo_barras": codigo},
        headers=auth.headers,
    )
    assert duplicado.status_code == 409

    # El código es único por negocio, no global.
    otro = auth.otro("beto")
    ajeno = cliente_api.post(
        "/productos/",
        json={"nombre": "Ajeno", "stock": 1, "precio": "1", "codigo_barras": codigo},
        headers={"Authorization": f"Bearer {otro['token']}"},
    )
    assert ajeno.status_code == 200


def test_codigo_de_barras_invalido_rechazado(cliente_api, auth):
    r = cliente_api.post(
        "/productos/",
        json={"nombre": "Raro", "stock": 1, "precio": "1", "codigo_barras": "ABC<script>"},
        headers=auth.headers,
    )
    assert r.status_code == 422


def test_cierre_de_caja_desglosa_por_metodo(cliente_api, auth):
    p = _producto(cliente_api, auth.headers, stock=20, precio="10.00")

    for metodo in ("efectivo", "efectivo", "tarjeta"):
        cliente_api.post(
            "/ventas/",
            json={"metodo_pago": metodo, "items": [{"producto_id": p["id"], "cantidad": 1}]},
            headers=auth.headers,
        )

    fecha = hoy_local("America/Managua").isoformat()
    cierre = cliente_api.get(f"/ventas/cierre?fecha={fecha}", headers=auth.headers).json()

    assert cierre["total"] == 30.0
    assert cierre["cantidad"] == 3
    assert cierre["efectivo_esperado"] == 20.0
    por_metodo = {m["metodo_pago"]: m for m in cierre["por_metodo"]}
    assert por_metodo["efectivo"]["total"] == 20.0
    assert por_metodo["tarjeta"]["total"] == 10.0
    assert por_metodo["transferencia"]["total"] == 0.0
    assert cierre["ticket_promedio"] == 10.0
