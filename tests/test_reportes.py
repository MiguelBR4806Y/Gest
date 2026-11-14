from Backend.tiempo import hoy_local


def _escenario(client, headers):
    p = client.post(
        "/productos/",
        json={"nombre": "Café", "stock": 10, "precio": "15.00", "stock_minimo": 50},
        headers=headers,
    ).json()
    v1 = client.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": p["id"], "cantidad": 2}]},
        headers=headers,
    ).json()
    v2 = client.post(
        "/ventas/",
        json={"metodo_pago": "tarjeta", "items": [{"producto_id": p["id"], "cantidad": 1}]},
        headers=headers,
    ).json()
    client.request("DELETE", f"/ventas/{v1['id']}", json={"motivo": "devolución"}, headers=headers)
    return p, v1, v2


def test_tendencia_rellena_dias_sin_ventas(cliente_api, auth):
    _crear_venta_hoy(cliente_api, auth.headers)

    r = cliente_api.get("/reportes/tendencia?dias=7", headers=auth.headers)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert len(datos["dias"]) == 7
    # El día de hoy es el último y concentra la venta.
    assert datos["dias"][-1]["total"] == 20.0
    assert datos["dias"][-1]["ganancia"] == 8.0
    assert sum(d["total"] for d in datos["dias"]) == 20.0
    assert datos["total_periodo"] == 20.0


def _crear_venta_hoy(client, headers):
    p = client.post(
        "/productos/",
        json={"nombre": "Trend", "stock": 10, "precio": "10.00", "costo": "6.00"},
        headers=headers,
    ).json()
    venta = client.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [{"producto_id": p["id"], "cantidad": 2}]},
        headers=headers,
    )
    assert venta.status_code == 200, venta.text
    return p


def test_dashboard_excluye_anuladas(cliente_api, auth):
    p, v1, v2 = _escenario(cliente_api, auth.headers)

    datos = cliente_api.get("/reportes/dashboard", headers=auth.headers).json()
    assert datos["resumen_dia"]["numero_ventas"] == 1
    assert datos["resumen_dia"]["total_ventas"] == 15.0
    assert datos["resumen_dia"]["anuladas"]["numero"] == 1
    assert datos["resumen_dia"]["anuladas"]["total"] == 30.0
    # stock_minimo 50 y stock 7 -> cuenta como bajo (antes usaba el 5 fijo)
    assert datos["stock_bajo"] == 1
    assert datos["total_productos"] == 1


def test_eventos_de_auditoria(cliente_api, auth):
    _escenario(cliente_api, auth.headers)
    eventos = cliente_api.get("/reportes/eventos", headers=auth.headers).json()
    tipos = {e["tipo"] for e in eventos}
    assert "venta_creada" in tipos
    assert "venta_anulada" in tipos
    anulada = next(e for e in eventos if e["tipo"] == "venta_anulada")
    assert anulada["entidad"] == "venta"
    assert "devolución" in anulada["detalle"]


def test_exportacion_csv(cliente_api, auth):
    p, v1, v2 = _escenario(cliente_api, auth.headers)
    fecha = hoy_local("America/Managua").isoformat()

    r = cliente_api.get(f"/reportes/exportar?desde={fecha}&hasta={fecha}", headers=auth.headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")

    texto = r.content.decode("utf-8-sig")
    lineas = texto.strip().splitlines()
    assert lineas[0].startswith("Factura;")
    assert len(lineas) == 3  # cabecera + 2 ventas
    assert "anulada" in texto
    assert "completada" in texto
    # El importe sale exacto, con dos decimales.
    assert "30.00" in texto and "15.00" in texto


def test_exportacion_valida_fechas(cliente_api, auth):
    r = cliente_api.get(
        "/reportes/exportar?desde=2026-01-31&hasta=2026-01-01", headers=auth.headers
    )
    assert r.status_code == 400
    r2 = cliente_api.get("/reportes/exportar?desde=no-fecha", headers=auth.headers)
    assert r2.status_code == 400


def test_listado_de_ventas_paginado_y_filtrado(cliente_api, auth):
    _escenario(cliente_api, auth.headers)

    todas = cliente_api.get("/ventas/?estado=todas", headers=auth.headers).json()
    assert todas["total"] == 2
    assert len(todas["items"]) == 2

    anuladas = cliente_api.get("/ventas/?estado=anulada", headers=auth.headers).json()
    assert anuladas["total"] == 1
    assert anuladas["items"][0]["estado"] == "anulada"

    pagina = cliente_api.get("/ventas/?limite=1&offset=1", headers=auth.headers).json()
    assert len(pagina["items"]) == 1
    assert pagina["total"] == 2


def test_no_hay_ventas_de_otro_usuario_en_reportes(cliente_api, auth):
    otro = auth.otro("beto")
    otras = {"Authorization": f"Bearer {otro['token']}"}

    _escenario(cliente_api, auth.headers)

    datos = cliente_api.get("/reportes/dashboard", headers=otras).json()
    assert datos["resumen_dia"]["numero_ventas"] == 0
    assert cliente_api.get("/reportes/eventos", headers=otras).json() == []
