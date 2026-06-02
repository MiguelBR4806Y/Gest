# NicaGest 🇳🇮

Sistema de gestión para negocios locales (inventario, ventas, facturación, clientes, IA).

## Stack
- **Backend**: Python 3.11+ · FastAPI · SQLite
- **Frontend**: HTML / CSS / JavaScript (Semana 2)
- **IA Dev**: Ollama + LLaMA 3.2 (local, gratis)
- **IA Prod**: OpenAI GPT-4o (con API key)

---

## Instalación

```bash
# 1. Clonar / descomprimir el proyecto
cd nicagest

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Edita .env si necesitas cambiar algo

# 5. Arrancar el servidor
uvicorn main:app --reload --port 8000
```

El servidor queda en: http://localhost:8000  
Documentación interactiva: http://localhost:8000/docs

---

## Instalar Ollama (IA local, desarrollo)

```bash
# Mac
brew install ollama

# O descarga desde: https://ollama.com

# Descargar modelo LLaMA 3.2 (2GB aprox)
ollama pull llama3.2

# Arrancar Ollama
ollama serve
```

---

## Cambiar a producción (OpenAI)

En el archivo `.env`:
```
NICAGEST_IA_MODO=openai
OPENAI_API_KEY=sk-tu-clave-aqui
```

Sin tocar nada más del código.

---

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | /productos/ | Listar productos |
| POST | /productos/ | Crear producto |
| POST | /productos/{id}/movimiento | Entrada/salida de inventario |
| GET | /productos/stock-bajo | Alertas de stock |
| POST | /ventas/ | Registrar venta completa |
| GET | /ventas/resumen-dia | Resumen del día |
| GET | /clientes/ | Listar clientes |
| POST | /clientes/ | Crear cliente |
| GET | /reportes/dashboard | Datos del dashboard |
| GET | /reportes/ventas | Reporte con análisis IA |
| GET | /health | Estado del sistema |

---

## Estructura del proyecto

```
nicagest/
├── main.py                    ← Entrada principal
├── requirements.txt
├── .env.example
├── nicagest.db                ← Se crea automáticamente
├── backend/
│   ├── db/
│   │   ├── database.py        ← Conexión SQLite
│   │   └── schema.sql         ← Esquema completo
│   ├── models/
│   │   └── schemas.py         ← Modelos Pydantic
│   ├── routers/
│   │   ├── productos.py       ← Inventario
│   │   ├── ventas.py          ← Punto de venta
│   │   ├── clientes.py        ← Clientes y crédito
│   │   └── reportes.py        ← Reportes + IA
│   └── ai/
│       └── ia_service.py      ← Switch Ollama/OpenAI
└── frontend/                  ← Semana 2
    ├── static/
    │   ├── css/
    │   └── js/
    └── templates/
        └── index.html
```