from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import os

load_dotenv()

from Backend.db import inicializar_db
from Backend.routers import productos, clientes, ventas, reportes, auth, facturas, organizacion, promociones

@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_db()
    yield

app = FastAPI(title="NicaGest API", version="1.0.0", lifespan=lifespan)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
