# Bravo's Gest 🇳🇮

Sistema de gestión para negocios locales (inventario, ventas, facturación, clientes, IA).

## Stack
- **Backend**: Python 3.11+ · FastAPI · SQLite
- **Frontend**: HTML / CSS / JavaScript · Bootstrap 5.3
- **IA Dev**: Ollama + LLaMA 3.2 (local, gratis)
- **IA Prod**: OpenAI GPT-4o (con API key)

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/MiguelBR4806Y/Gest.git
cd Gest

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# venv\Scripts\activate         # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env

# 5. Arrancar el servidor
uvicorn main:app --reload --port 8000
```

El servidor queda en: http://127.0.0.1:8000  
Documentación interactiva: http://127.0.0.1:8000/docs

---

## Credenciales por defecto

| Usuario | Contraseña |
|---------|------------|
| root    | 1234       |

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

NICAGEST_IA_MODO=openai
OPENAI_API_KEY=sk-tu-clave-aqui


Sin tocar nada más del código.

---

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | /auth/login | Iniciar sesión |
| GET | /productos/ | Listar productos |
| POST | /productos/ | Crear producto |
| PUT | /productos/{id} | Editar producto |
| DELETE | /productos/{id} | Eliminar producto |
| POST | /productos/{id}/movimiento | Entrada/salida de inventario |
| GET | /productos/stock-bajo | Alertas de stock |
| POST | /ventas/ | Registrar venta completa |
| GET | /ventas/resumen-dia | Resumen del día |
| GET | /clientes/ | Listar clientes |
| POST | /clientes/ | Crear cliente |
| PUT | /clientes/{id} | Editar cliente |
| DELETE | /clientes/{id} | Eliminar cliente |
| GET | /reportes/dashboard | Datos del dashboard |
| GET | /reportes/ventas | Reporte con análisis IA |
| GET | /health | Estado del sistema |

---

## Estructura del proyecto
Gest/
├── main.py                        ← Entrada principal
├── requirements.txt
├── .env.example
├── .gitignore
├── nicagest.db                    ← Se crea automáticamente
├── Backend/
│   ├── ai/
│   │   └── ia_service.py          ← Switch Ollama/OpenAI
│   ├── db/
│   │   ├── database.py            ← Conexión SQLite
│   │   └── schema.sql             ← Esquema completo
│   ├── models/
│   │   └── schema.py              ← Modelos Pydantic
│   └── routers/
│       ├── auth.py                ← Autenticación
│       ├── productos.py           ← Inventario
│       ├── ventas.py              ← Punto de venta
│       ├── clientes.py            ← Clientes y crédito
│       └── reportes.py            ← Reportes + IA
└── Frontend/
    ├── static/
    │   ├── style.css
    │   ├── Script.js              ← Auth + sesión global
    │   ├── dashboard.js
    │   ├── inventario.js
    │   ├── cliente.js
    │   └── ventas.js
    └── Templates/
    ├── index.html             ← Landing + login
├── dashboard.html
├── inventario.html
├── clientes.html
└── ventas.html

---

## Progreso

| Semana | Descripción | Estado |
|--------|-------------|--------|
| 1 | Backend — FastAPI, SQLite, endpoints | ✅ Completa |
| 2 | Frontend — HTML, CSS, JS, Bootstrap | ✅ Completa |
| 3 | CRUD completo, modales, auth real | ✅ Completa |
| 4 | Facturación, historial, UX | ⬜ Pendiente |
| 5 | Deploy, OpenAI en producción | ⬜ Pendiente |
| 6 | Pruebas finales, pulido | ⬜ Pendiente |