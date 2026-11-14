from Backend.tiempo import hoy_local


def crear_producto(client, headers, nombre="Producto", precio="100.00", costo="60.00", stock=10):
    r = client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio, "costo": costo},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def vender(client, headers, producto_id, cantidad=1):
    r = client.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [
            {"producto_id": producto_id, "cantidad": cantidad}
        ]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_producto_devuelve_costo_y_margen(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    assert p["costo"] == 60.0
    assert p["margen"] == 40.0
    assert p["margen_pct"] == 40.0


def test_producto_sin_costo_margen_es_el_precio(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="50.00", costo="0")
    assert p["margen"] == 50.0
    assert p["margen_pct"] == 100.0


def test_venta_registra_ganancia_en_resumen_y_cierre(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    vender(cliente_api, auth.headers, p["id"], cantidad=2)

    fecha = hoy_local("America/Managua").isoformat()
    resumen = cliente_api.get(f"/ventas/resumen-dia?fecha={fecha}", headers=auth.headers).json()
    assert resumen["total_ventas"] == 200.0
    assert resumen["ganancia"] == 80.0
    assert resumen["margen_pct"] == 40.0

    cierre = cliente_api.get(f"/ventas/cierre?fecha={fecha}", headers=auth.headers).json()
    assert cierre["ganancia"] == 80.0
    assert cierre["margen_pct"] == 40.0

    dash = cliente_api.get("/reportes/dashboard", headers=auth.headers).json()
    assert dash["resumen_dia"]["ganancia"] == 80.0
    assert dash["resumen_dia"]["margen_pct"] == 40.0


def test_el_costo_historico_no_se_reescribe(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    vender(cliente_api, auth.headers, p["id"], cantidad=1)

    # El dueño actualiza el costo después de la venta.
    cliente_api.put(
        f"/productos/{p['id']}",
        json={"nombre": "Producto", "stock": 9, "precio": "100.00", "costo": "90.00"},
        headers=auth.headers,
    )

    margenes = cliente_api.get("/reportes/margenes", headers=auth.headers).json()
    fila = next(x for x in margenes["productos"] if x["producto_id"] == p["id"])
    # La venta antigua conserva el costo de 60.
    assert fila["costo"] == 60.0
    assert fila["ganancia"] == 40.0

    # Una venta nueva sí usa el costo nuevo.
    vender(cliente_api, auth.headers, p["id"], cantidad=1)
    margenes2 = cliente_api.get("/reportes/margenes", headers=auth.headers).json()
    fila2 = next(x for x in margenes2["productos"] if x["producto_id"] == p["id"])
    assert fila2["costo"] == 150.0  # 60 + 90
    assert fila2["ganancia"] == 50.0  # 200 ingresos - 150 costo


def test_margenes_por_producto_y_totales(cliente_api, auth):
    a = crear_producto(cliente_api, auth.headers, nombre="A", precio="100.00", costo="50.00")
    b = crear_producto(cliente_api, auth.headers, nombre="B", precio="40.00", costo="30.00")
    vender(cliente_api, auth.headers, a["id"], cantidad=2)
    vender(cliente_api, auth.headers, b["id"], cantidad=5)

    datos = cliente_api.get("/reportes/margenes", headers=auth.headers).json()
    assert datos["totales"]["ingresos"] == 400.0  # 200 + 200
    assert datos["totales"]["costo"] == 250.0  # 100 + 150
    assert datos["totales"]["ganancia"] == 150.0
    assert datos["totales"]["unidades"] == 7

    por_id = {x["producto_id"]: x for x in datos["productos"]}
    assert por_id[a["id"]]["ganancia"] == 100.0
    assert por_id[b["id"]]["ganancia"] == 50.0


def test_margenes_excluyen_anuladas(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    venta = vender(cliente_api, auth.headers, p["id"], cantidad=1)
    cliente_api.request(
        "DELETE", f"/ventas/{venta['id']}", json={"motivo": "x"}, headers=auth.headers
    )

    datos = cliente_api.get("/reportes/margenes", headers=auth.headers).json()
    assert datos["productos"] == []
    assert datos["totales"]["ganancia"] == 0.0


def test_promocion_reparte_el_descuento_en_el_margen(cliente_api, auth):
    promo = cliente_api.post(
        "/promociones/",
        json={"nombre": "10%", "tipo": "porcentaje", "valor": "10.00", "activa": True},
        headers=auth.headers,
    ).json()
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    cliente_api.put(
        f"/productos/{p['id']}",
        json={
            "nombre": "Producto", "stock": 10, "precio": "100.00",
            "costo": "60.00", "promocion_id": promo["id"],
        },
        headers=auth.headers,
    )

    vender(cliente_api, auth.headers, p["id"], cantidad=1)

    datos = cliente_api.get("/reportes/margenes", headers=auth.headers).json()
    fila = datos["productos"][0]
    assert fila["ingresos"] == 90.0  # con el 10% aplicado
    assert fila["costo"] == 60.0
    assert fila["ganancia"] == 30.0
    assert fila["margen_pct"] == 33.33

    # El resumen, el cierre y el dashboard usan el total realmente cobrado,
    # no el precio bruto de la línea.
    fecha = hoy_local("America/Managua").isoformat()
    resumen = cliente_api.get(f"/ventas/resumen-dia?fecha={fecha}", headers=auth.headers).json()
    assert resumen["total_ventas"] == 90.0
    assert resumen["ganancia"] == 30.0

    cierre = cliente_api.get(f"/ventas/cierre?fecha={fecha}", headers=auth.headers).json()
    assert cierre["ganancia"] == 30.0

    dash = cliente_api.get("/reportes/dashboard", headers=auth.headers).json()
    assert dash["resumen_dia"]["ganancia"] == 30.0


def test_csv_incluye_costo_y_ganancia(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, precio="100.00", costo="60.00")
    vender(cliente_api, auth.headers, p["id"], cantidad=1)

    fecha = hoy_local("America/Managua").isoformat()
    r = cliente_api.get(f"/reportes/exportar?desde={fecha}&hasta={fecha}", headers=auth.headers)
    texto = r.content.decode("utf-8-sig")
    cabecera = texto.splitlines()[0]
    assert "Costo C$" in cabecera
    assert "Ganancia C$" in cabecera
    assert "60.00" in texto
    assert "40.00" in texto
