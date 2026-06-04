from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from Backend.db import inicializar_db
from Backend.routers import productos, clientes, ventas, reportes

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

# ── Archivos estáticos ──
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# ── Servir el frontend ──
@app.get("/")
def home():
    return FileResponse("frontend/templates/index.html")

@app.get("/{pagina}.html")
def paginas(pagina: str):
    path = f"frontend/templates/{pagina}.html"
    if os.path.exists(path):
        return FileResponse(path)
    return FileResponse("frontend/templates/index.html")

app.mount("/img", StaticFiles(directory="img"), name="img")
# ── Health check ──
@app.get("/health")
def health():
    return {"status": "ok"}