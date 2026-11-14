import asyncio

import httpx

import main


def crear_producto(client, headers, stock=10):
    r = client.post(
        "/productos/",
        json={"nombre": "P", "stock": stock, "precio": "10.00"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def cobrar(client, headers, producto_id, clave=None, cantidad=1):
    cabeceras = dict(headers)
    if clave is not None:
        cabeceras["Idempotency-Key"] = clave
    return client.post(
        "/ventas/",
        json={"metodo_pago": "efectivo", "items": [
            {"producto_id": producto_id, "cantidad": cantidad}
        ]},
        headers=cabeceras,
    )


def test_misma_clave_no_duplica_la_venta(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)

    primera = cobrar(cliente_api, auth.headers, p["id"], clave="cobro-abc-1", cantidad=2)
    segunda = cobrar(cliente_api, auth.headers, p["id"], clave="cobro-abc-1", cantidad=2)

    assert primera.status_code == segunda.status_code == 200
    assert primera.json()["id"] == segunda.json()["id"]
    assert primera.json()["repetida"] is False
    assert segunda.json()["repetida"] is True

    lista = cliente_api.get("/ventas/", headers=auth.headers).json()
    assert lista["total"] == 1

    producto = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert producto["stock"] == 8  # se descontó una sola vez


def test_claves_distintas_crean_ventas_distintas(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)

    a = cobrar(cliente_api, auth.headers, p["id"], clave="cobro-1")
    b = cobrar(cliente_api, auth.headers, p["id"], clave="cobro-2")

    assert a.json()["id"] != b.json()["id"]
    assert cliente_api.get("/ventas/", headers=auth.headers).json()["total"] == 2
    assert cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()["stock"] == 8


def test_la_clave_es_por_usuario(cliente_api, auth):
    otro = auth.otro("beto")
    otras = {"Authorization": f"Bearer {otro['token']}"}
    p = crear_producto(cliente_api, auth.headers, stock=10)
    p_otro = crear_producto(cliente_api, otras, stock=10)

    a = cobrar(cliente_api, auth.headers, p["id"], clave="misma-clave")
    b = cobrar(cliente_api, otras, p_otro["id"], clave="misma-clave")

    # El mismo texto de clave en dos cuentas no colisiona.
    assert a.status_code == 200
    assert b.status_code == 200
    assert a.json()["id"] != b.json()["id"]


def test_clave_invalida_rechazada(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)
    r = cobrar(cliente_api, auth.headers, p["id"], clave="clave con espacios")
    assert r.status_code == 400

    r2 = cobrar(cliente_api, auth.headers, p["id"], clave="x" * 65)
    assert r2.status_code == 400


def test_sin_clave_se_comporta_como_siempre(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)
    a = cobrar(cliente_api, auth.headers, p["id"])
    b = cobrar(cliente_api, auth.headers, p["id"])
    assert a.status_code == b.status_code == 200
    assert a.json()["id"] != b.json()["id"]


def test_carrera_de_dos_cobros_iguales(cliente_api, auth):
    p = crear_producto(cliente_api, auth.headers, stock=10)

    async def cobrar_async():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(
                "/ventas/",
                json={"metodo_pago": "efectivo", "items": [
                    {"producto_id": p["id"], "cantidad": 1}
                ]},
                headers={**auth.headers, "Idempotency-Key": "carrera-1"},
            )

    async def carrera():
        return await asyncio.gather(cobrar_async(), cobrar_async())

    respuestas = asyncio.run(carrera())
    assert all(r.status_code == 200 for r in respuestas), [r.text for r in respuestas]
    ids = {r.json()["id"] for r in respuestas}
    assert len(ids) == 1

    lista = cliente_api.get("/ventas/", headers=auth.headers).json()
    assert lista["total"] == 1

    producto = cliente_api.get(f"/productos/{p['id']}", headers=auth.headers).json()
    assert producto["stock"] == 9
