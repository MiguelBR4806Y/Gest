"""Envío de facturas por correo y enlaces de WhatsApp."""

from datetime import datetime, timedelta, timezone

from Backend.db.database import SessionLocal
from Backend.db.models import EnlaceFactura


def _producto(client, headers, nombre="Producto", stock=5, precio="100"):
    return client.post(
        "/productos/",
        json={"nombre": nombre, "stock": stock, "precio": precio},
        headers=headers,
    ).json()


def _cliente(client, headers, nombre="María", telefono=None, email=None):
    r = client.post(
        "/clientes/",
        json={"nombre": nombre, "telefono": telefono, "email": email},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _venta(client, headers, producto, cliente_id=None):
    r = client.post(
        "/ventas/",
        json={
            "metodo_pago": "efectivo",
            "cliente_id": cliente_id,
            "items": [{"producto_id": producto["id"], "cantidad": 1}],
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_el_cliente_guarda_su_correo(cliente_api, auth_admin):
    c = _cliente(cliente_api, auth_admin.headers, email="maria@example.com")
    assert c["email"] == "maria@example.com"

    r = cliente_api.post(
        "/clientes/", json={"nombre": "Mal", "email": "no-es-correo"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 422


def test_envio_por_correo_adjunta_la_factura(cliente_api, auth_admin, monkeypatch):
    import Backend.routers.facturas as modulo_facturas

    enviados = {}

    def falso_envio(destinatario, pdf_bytes, nombre_negocio, factura_id, enlace=None):
        enviados.update({
            "destinatario": destinatario,
            "pdf": pdf_bytes,
            "factura": factura_id,
            "enlace": enlace,
        })
        return True

    monkeypatch.setattr(modulo_facturas, "enviar_factura", falso_envio)
    monkeypatch.setattr(modulo_facturas, "smtp_configurado", lambda: True)

    producto = _producto(cliente_api, auth_admin.headers)
    cliente = _cliente(cliente_api, auth_admin.headers, email="maria@example.com")
    venta = _venta(cliente_api, auth_admin.headers, producto, cliente["id"])

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "email"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert enviados["destinatario"] == "maria@example.com"
    assert enviados["pdf"].startswith(b"%PDF-")
    assert enviados["factura"] == venta["id"]
    assert "/facturas/descarga/" in enviados["enlace"]


def test_sin_correo_ni_destinatario_es_400(cliente_api, auth_admin):
    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "email"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 400
    assert "correo" in r.json()["detail"]


def test_destinatario_manual_tiene_prioridad(cliente_api, auth_admin, monkeypatch):
    import Backend.routers.facturas as modulo_facturas

    monkeypatch.setattr(modulo_facturas, "smtp_configurado", lambda: True)
    capturado = {}
    monkeypatch.setattr(
        modulo_facturas,
        "enviar_factura",
        lambda destinatario, *a, **k: capturado.update({"d": destinatario}) or True,
    )

    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "email", "destinatario": "otro@example.com"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    assert capturado["d"] == "otro@example.com"


def test_sin_smtp_configurado_es_503(cliente_api, auth_admin, monkeypatch):
    import Backend.routers.facturas as modulo_facturas

    monkeypatch.setattr(modulo_facturas, "smtp_configurado", lambda: False)

    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "email", "destinatario": "x@example.com"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 503


def test_whatsapp_devuelve_enlace_con_telefono_normalizado(cliente_api, auth_admin):
    producto = _producto(cliente_api, auth_admin.headers)
    cliente = _cliente(cliente_api, auth_admin.headers, telefono="8888-1234")
    venta = _venta(cliente_api, auth_admin.headers, producto, cliente["id"])

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "whatsapp"},
        headers=auth_admin.headers,
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["telefono"] == "50588881234"
    assert datos["whatsapp_url"].startswith("https://wa.me/50588881234?text=")
    assert f"factura%20%23{venta['id']}" in datos["whatsapp_url"] or "factura" in datos["whatsapp_url"]
    assert "/facturas/descarga/" in datos["url"]


def test_el_enlace_publico_descarga_sin_sesion(cliente_api, auth_admin):
    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)

    datos = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "whatsapp", "destinatario": "88881234"},
        headers=auth_admin.headers,
    ).json()

    token = datos["url"].rsplit("/", 1)[-1]
    r = cliente_api.get(f"/facturas/descarga/{token}")
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF-")
    assert "application/pdf" in r.headers["content-type"]


def test_enlace_de_otro_negocio_no_expone_la_factura(
    cliente_api, auth_admin, crear_usuario
):
    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)

    enlace = cliente_api.get(
        f"/facturas/{venta['id']}/enlace", headers=auth_admin.headers
    ).json()
    token = enlace["url"].rsplit("/", 1)[-1]

    # Otro negocio no puede pedir facturas de este usuario con su sesión.
    otro = crear_usuario(usuario="ajeno", rol="admin")
    r = cliente_api.get(
        f"/facturas/{venta['id']}", headers={"Authorization": f"Bearer {otro['token']}"}
    )
    assert r.status_code == 404

    # El token, en cambio, es una capacidad: quien lo tiene descarga esa factura.
    assert cliente_api.get(f"/facturas/descarga/{token}").status_code == 200


def test_enlace_caducado_da_404(cliente_api, auth_admin):
    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, auth_admin.headers, producto)
    datos = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "whatsapp", "destinatario": "88881234"},
        headers=auth_admin.headers,
    ).json()
    token = datos["url"].rsplit("/", 1)[-1]

    with SessionLocal() as session:
        enlace = session.query(EnlaceFactura).first()
        enlace.expira = datetime.now(timezone.utc) - timedelta(days=1)
        session.commit()

    r = cliente_api.get(f"/facturas/descarga/{token}")
    assert r.status_code == 404
    assert "caducado" in r.json()["detail"]


def test_token_inventado_da_404(cliente_api):
    r = cliente_api.get("/facturas/descarga/" + "x" * 40)
    assert r.status_code == 404


def test_un_vendedor_puede_enviar_la_factura_que_cobro(cliente_api, auth_admin):
    creado = cliente_api.post(
        "/vendedores/", json={"nombre": "Vendedor Factura"}, headers=auth_admin.headers
    ).json()
    login = cliente_api.post(
        "/auth/login",
        json={"usuario": creado["usuario"], "password": creado["password"]},
    ).json()
    headers = {"Authorization": f"Bearer {login['token']}"}

    producto = _producto(cliente_api, auth_admin.headers)
    venta = _venta(cliente_api, headers, producto)

    r = cliente_api.post(
        f"/facturas/{venta['id']}/enviar",
        json={"canal": "whatsapp", "destinatario": "88881234"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
