import logging
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada en el entorno")

logger = logging.getLogger("app")

from Backend.db import inicializar_db
from Backend.routers import productos, clientes, ventas, reportes, auth, facturas, organizacion, promociones
from Backend.security import dentro_de


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando base de datos...")
    inicializar_db()
    logger.info("Servidor listo")
    yield


app = FastAPI(
    title="NicaGest API",
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("EXPOSER_DOCS", "1") == "1" else None,
    redoc_url=None,
)

# Prefijos de API: cualquier otra ruta cae en el fallback de la SPA.
PREFIJOS_API = (
    "/productos", "/clientes", "/ventas", "/reportes",
    "/auth", "/facturas", "/organizacion", "/promociones",
    "/img", "/assets", "/health",
)

DIST = os.path.abspath("Frontend/dist")


# ── Request ID + logging middleware ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    logger.info("[%s] %s %s", req_id, request.method, request.url.path)
    response = await call_next(request)
    logger.info("[%s] %s %s -> %s", req_id, request.method, request.url.path, response.status_code)
    response.headers["X-Request-ID"] = req_id
    return response


# ── Cabeceras de seguridad ──
CSP_POR_DEFECTO = (
    "default-src 'self'; "
    "script-src 'self' https://accounts.google.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-src https://accounts.google.com; "
    "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'"
)
CONTENT_SECURITY_POLICY = os.getenv("CONTENT_SECURITY_POLICY", CSP_POR_DEFECTO)
ENABLE_HSTS = os.getenv("ENABLE_HSTS", "0") == "1"


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()"
    )
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    if ENABLE_HSTS:
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


# ── CORS ──
def _origenes_permitidos() -> list[str]:
    crudo = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000")
    origenes = [o.strip().rstrip("/") for o in crudo.split(",") if o.strip()]
    return [o for o in origenes if o != "*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_origenes_permitidos(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Manejadores de error: nunca filtran trazas ni detalles internos ──
@app.exception_handler(RequestValidationError)
async def error_validacion(request: Request, exc: RequestValidationError):
    campos = []
    for e in exc.errors():
        ubicacion = ".".join(str(p) for p in e.get("loc", [])[1:]) or "dato"
        campos.append(f"{ubicacion}: {e.get('msg', 'inválido')}")
    return JSONResponse(status_code=422, content={"detail": "; ".join(campos)})


@app.exception_handler(Exception)
async def error_no_controlado(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})


# ── Routers ──
app.include_router(productos.router)
app.include_router(clientes.router)
app.include_router(ventas.router)
app.include_router(reportes.router)
app.include_router(auth.router)
app.include_router(facturas.router)
app.include_router(organizacion.router)
app.include_router(promociones.router)

# ── Archivos estáticos del backend ──
if os.path.isdir("img"):
    app.mount("/img", StaticFiles(directory="img"), name="img")

if os.path.isdir(os.path.join(DIST, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")


# ── Health check (debe ir antes del catch-all) ──
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def home():
    index = os.path.join(DIST, "index.html")
    if not os.path.isfile(index):
        return JSONResponse(status_code=503, content={"detail": "Frontend no compilado"})
    return FileResponse(index)


@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    """Sirve la SPA rechazando cualquier ruta que escape de Frontend/dist."""
    # `full_path` llega sin la barra inicial, así que hay que reponerla para
    # comparar contra los prefijos de API.
    ruta = "/" + full_path
    if ruta.startswith(PREFIJOS_API):
        return JSONResponse(status_code=404, content={"detail": "Recurso no encontrado"})

    candidato = os.path.abspath(os.path.join(DIST, full_path))
    if not dentro_de(DIST, candidato):
        return JSONResponse(status_code=404, content={"detail": "Recurso no encontrado"})
    if os.path.isfile(candidato):
        return FileResponse(candidato)

    index = os.path.join(DIST, "index.html")
    if not os.path.isfile(index):
        return JSONResponse(status_code=404, content={"detail": "Recurso no encontrado"})
    return FileResponse(index)
