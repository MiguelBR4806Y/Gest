# Bravo's Gest 🇳🇮

Sistema de gestión para negocios locales (inventario, ventas, facturación, clientes, IA) adaptado al comercio de Nicaragua. Proyecto desarrollado como parte del plan de estudio de Ingeniería de Sistemas (Ciclo 5).

## Stack
- **Backend**: Python 3.11+ · FastAPI · SQLite
- **Frontend**: HTML / CSS / JavaScript · Bootstrap 5.3
- **IA**: Groq (Llama 3.3 70B) — análisis de ventas en tiempo real, gratis sin tarjeta. También soporta OpenAI y Ollama como alternativas configurables.

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
```

El servidor queda en: http://127.0.0.1:8000

Documentación interactiva: http://127.0.0.1:8000/docs

---

## Credenciales por defecto

| Usuario | Contraseña |
| --- | --- |
| root | 1234 |

---

## Configurar la IA (Groq — modo por defecto)

1. Crea una cuenta gratis en [console.groq.com](https://console.groq.com) (no pide tarjeta).
2. Genera una API key en la sección **API Keys**.
3. En tu archivo `.env`, agrega:

```env
NICAGEST_IA_MODO=groq
GROQ_API_KEY=tu_key_aqui
GROQ_MODEL=llama-3.3-70b-versatile
```

4. Arranca el servidor:

```bash
uvicorn main:app --reload --port 8000
```

El análisis de IA aparece en el dashboard, en la sección "✨ Análisis IA", generado a partir de las ventas del día.

### Alternativas de proveedor de IA

El switch en `Backend/ai/ia_service.py` permite cambiar de proveedor sin tocar código, solo editando `.env`:

**OpenAI** (de pago):
```env
NICAGEST_IA_MODO=openai
OPENAI_API_KEY=sk-tu-clave-aqui
```

**Ollama** (100% local y gratis, requiere tenerlo corriendo en tu máquina):
```bash
# Mac
brew install ollama
# O descarga desde: https://ollama.com

ollama pull llama3.2
ollama serve
```
```env
NICAGEST_IA_MODO=ollama
```

---

## Endpoints principales

| Método | Ruta | Descripción |
| --- | --- | --- |
| POST | /auth/login | Iniciar sesión |
| GET | /productos/ | Listar productos |
| POST | /productos/ | Crear producto |
| PUT | /productos/{id} | Editar producto |
| DELETE | /productos/{id} | Eliminar producto |
| POST | /productos/{id}/movimiento | Entrada/salida de inventario |
| GET | /productos/stock-bajo | Alertas de stock |
| POST | /ventas/ | Registrar venta completa (Validación de stock) |
| GET | /ventas/resumen-dia | Resumen del día (Métricas agrupadas) |
| GET | /clientes/ | Listar clientes |
| POST | /clientes/ | Crear cliente |
| PUT | /clientes/{id} | Editar cliente |
| DELETE | /clientes/{id} | Eliminar cliente |
| GET | /reportes/dashboard | Datos del dashboard |
| GET | /reportes/ventas | Reporte con análisis IA (Groq) |
| GET | /health | Estado del sistema |

---

## Estructura del proyecto

```text
Gest/
├── main.py                        ← Entrada principal
├── requirements.txt
├── .env.example
├── .gitignore
├── nicagest.db                    ← Se crea automáticamente
├── Backend/
│   ├── ai/
│   │   └── ia_service.py          ← Switch Groq / OpenAI / Ollama
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
    │   ├── dashboard.js            ← Manejo de tiempos locales (12h)
    │   ├── inventario.js
    │   ├── cliente.js
    │   └── ventas.js              ← Control de interfaz y resumen diario
    └── Templates/
        ├── index.html             ← Landing + login
        ├── dashboard.html
        ├── inventario.html
        ├── clientes.html
        └── ventas.html
```

---

## Progreso del Proyecto

| Semana | Descripción | Estado |
| --- | --- | --- |
| 1 | Backend — FastAPI, SQLite, endpoints núcleo | ✅ Completa |
| 2 | Frontend — HTML, CSS, JS, Bootstrap modular | ✅ Completa |
| 3 | CRUD completo, modales reactivos, auth real con JWT | ✅ Completa |
| 4 | Facturación relacional, Historial detallado, Formato regional (`es-NI`) y UX (Horario 12h AM/PM) | ✅ Completa |
| 5 | Integración de IA — Conexión con Groq (Llama 3.3 70B) para análisis de ventas en el dashboard. Reportes predictivos aún pendientes | 🟡 En progreso |
| 6 | Pruebas finales, pulido de interfaz y despliegue | ⬜ Pendiente |