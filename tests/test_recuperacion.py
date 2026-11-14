import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from Backend.db.database import SessionLocal
from Backend.db.models import Usuario


@pytest.fixture
def enviados(monkeypatch):
    """Captura los enlaces en vez de enviar correo real."""
    capturados = []

    def falso(destinatario, token, nombre_negocio):
        capturados.append({
            "email": destinatario,
            "token": token,
            "negocio": nombre_negocio,
        })
        return True

    monkeypatch.setattr("Backend.routers.auth.enviar_reset", falso)
    return capturados


def solicitar(client, identificador):
    return client.post("/auth/recuperar", json={"identificador": identificador})


def test_la_respuesta_no_revela_si_la_cuenta_existe(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")

    existente = solicitar(cliente_api, "ana")
    inexistente = solicitar(cliente_api, "nadie@example.com")

    assert existente.status_code == inexistente.status_code == 200
    assert existente.json() == inexistente.json()
    assert len(enviados) == 1


def test_envia_enlace_y_guarda_solo_el_hash(cliente_api, crear_usuario, enviados):
    datos = crear_usuario("ana", email="ana@example.com")

    assert solicitar(cliente_api, "ana").status_code == 200
    assert len(enviados) == 1
    assert enviados[0]["email"] == "ana@example.com"
    assert enviados[0]["token"]

    with SessionLocal() as session:
        u = session.get(Usuario, datos["id"])
        esperado = hashlib.sha256(enviados[0]["token"].encode()).hexdigest()
        assert u.reset_token_hash == esperado
        assert u.reset_token_hash != enviados[0]["token"]
        assert len(u.reset_token_hash) == 64
        assert u.reset_expira is not None


def test_buscar_por_correo_tambien_funciona(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")
    assert solicitar(cliente_api, "ANA@example.com").status_code == 200
    assert len(enviados) == 1


def test_usuario_sin_correo_no_recibe_nada(cliente_api, crear_usuario, enviados):
    crear_usuario("ana")
    assert solicitar(cliente_api, "ana").status_code == 200
    assert enviados == []


def test_reset_cambia_la_contrasena_y_revoca_sesiones(cliente_api, crear_usuario, enviados):
    datos = crear_usuario("ana", password="Segura123", email="ana@example.com")
    headers = {"Authorization": f"Bearer {datos['token']}"}
    assert cliente_api.get("/productos/", headers=headers).status_code == 200

    solicitar(cliente_api, "ana")
    token = enviados[0]["token"]

    r = cliente_api.post("/auth/reset", json={
        "token": token,
        "password_nuevo": "NuevaClave789",
    })
    assert r.status_code == 200, r.text

    # La sesión anterior queda revocada.
    assert cliente_api.get("/productos/", headers=headers).status_code == 401

    # La contraseña vieja ya no entra; la nueva sí.
    assert cliente_api.post("/auth/login", json={
        "usuario": "ana", "password": "Segura123",
    }).status_code == 401
    assert cliente_api.post("/auth/login", json={
        "usuario": "ana", "password": "NuevaClave789",
    }).status_code == 200


def test_el_token_es_de_un_solo_uso(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")
    solicitar(cliente_api, "ana")
    token = enviados[0]["token"]

    primera = cliente_api.post("/auth/reset", json={
        "token": token, "password_nuevo": "NuevaClave789",
    })
    assert primera.status_code == 200

    segunda = cliente_api.post("/auth/reset", json={
        "token": token, "password_nuevo": "OtraClave987",
    })
    assert segunda.status_code == 400


def test_token_caducado_rechazado(cliente_api, crear_usuario, enviados):
    datos = crear_usuario("ana", email="ana@example.com")
    solicitar(cliente_api, "ana")
    token = enviados[0]["token"]

    with SessionLocal() as session:
        u = session.get(Usuario, datos["id"])
        u.reset_expira = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.commit()

    r = cliente_api.post("/auth/reset", json={
        "token": token, "password_nuevo": "NuevaClave789",
    })
    assert r.status_code == 400
    assert "expiró" in r.json()["detail"]

    with SessionLocal() as session:
        u = session.get(Usuario, datos["id"])
        assert u.reset_token_hash is None


def test_token_inventado_rechazado(cliente_api):
    r = cliente_api.post("/auth/reset", json={
        "token": "x" * 43, "password_nuevo": "NuevaClave789",
    })
    assert r.status_code == 400


def test_password_debil_rechazada(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")
    solicitar(cliente_api, "ana")

    r = cliente_api.post("/auth/reset", json={
        "token": enviados[0]["token"], "password_nuevo": "12345678",
    })
    assert r.status_code == 422


def test_enfriamiento_no_reenvia_correo(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")

    assert solicitar(cliente_api, "ana").status_code == 200
    assert solicitar(cliente_api, "ana").status_code == 200

    assert len(enviados) == 1


def test_queda_registro_en_auditoria(cliente_api, crear_usuario, enviados):
    crear_usuario("ana", email="ana@example.com")

    solicitar(cliente_api, "ana")
    cliente_api.post("/auth/reset", json={
        "token": enviados[0]["token"], "password_nuevo": "NuevaClave789",
    })

    # El token anterior está revocado, así que se consulta con uno nuevo.
    nuevo = cliente_api.post("/auth/login", json={
        "usuario": "ana", "password": "NuevaClave789",
    }).json()["token"]
    eventos = cliente_api.get(
        "/reportes/eventos", headers={"Authorization": f"Bearer {nuevo}"}
    ).json()
    tipos = {e["tipo"] for e in eventos}
    assert "recuperacion_solicitada" in tipos
    assert "password_restablecida" in tipos
