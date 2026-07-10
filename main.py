import logging
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY no está configurada en el entorno")

logger = logging.getLogger("app")

from Backend.db import inicializar_db
from Backend.routers import productos, clientes, ventas, reportes, auth, facturas, organizacion, promociones

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando base de datos...")
    inicializar_db()
    logger.info("Servidor listo")
    yield

app = FastAPI(title="NicaGest API", version="1.0.0", lifespan=lifespan)

# ── Request ID + logging middleware ──
@app.middleware("http")
async def log_requests(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    logger.info("[%s] %s %s", req_id, request.method, request.url.path)
    response = await call_next(request)
    logger.info("[%s] %s %s -> %s", req_id, request.method, request.url.path, response.status_code)
    return response

# ── CORS ──
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(productos.router)
app.include_router(clientes.router)
app.include_router(ventas.router)
app.include_router(reportes.router)
app.include_router(auth.router)
app.include_router(facturas.router)
app.include_router(organizacion.router)
app.include_router(promociones.router)

# ── Archivos estáticos del backend (facturas generadas) ──
app.mount("/img", StaticFiles(directory="img"), name="img")

DIST = "Frontend/dist"

# ── Assets del build de Vite ──
if os.path.isdir(f"{DIST}/assets"):
    app.mount("/assets", StaticFiles(directory=f"{DIST}/assets"), name="assets")

# ── Health check (debe ir antes del catch-all) ──
@app.get("/health")
def health():
    return {"status": "ok"}

# ── Servir la SPA (index.html para cualquier ruta no-API) ──
@app.get("/")
def home():
    return FileResponse(f"{DIST}/index.html")

@app.get("/{full_path:path}")
def spa_fallback(full_path: str):
    static_file = f"{DIST}/{full_path}"
    if os.path.isfile(static_file):
        return FileResponse(static_file)
    return FileResponse(f"{DIST}/index.html")
