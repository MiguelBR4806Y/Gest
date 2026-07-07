# Bravo's Gest

Sistema de gestión para negocios locales (inventario, ventas, facturación, clientes, organización, IA).

## Stack

- **Backend**: Python 3.11+ · FastAPI · PostgreSQL · SQLAlchemy
- **Frontend**: React 19 + Vite 8 + Tailwind CSS 3 + react-router-dom v7
- **IA**: **Gesti** — asistente inteligente amigable con Groq (Llama 3.3 70B), OpenAI u Ollama. Análisis de ventas, chat conversacional con historial persistente y reportes predictivos.

---

## Requisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+ corriendo

## Instalación

```bash
# 1. Clonar
git clone <repo-url>
cd Gest

# 2. Backend — entorno virtual
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
pip install -r requirements.txt

# 3. Frontend — dependencias
cd Frontend
npm install
cd ..

# 4. Variables de entorno
cp .env.example .env
# Editar DATABASE_URL si es necesario
```

### Crear la base de datos

```bash
psql -U postgres -c "CREATE DATABASE nicagest;"
```

### Ejecutar (desarrollo)

```bash
# Terminal 1 — Backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend (hot reload)
cd Frontend
npm run dev
```

- Backend: http://127.0.0.1:8000
- Frontend (dev): http://127.0.0.1:5173
- Docs API: http://127.0.0.1:8000/docs

> El frontend en dev se sirve en `:5173` con hot reload. Las llamadas API se redirigen automáticamente al backend via proxy de Vite.
>
> Para producción, primero ejecutar `npm run build` en `Frontend/` para generar los archivos estáticos que sirve FastAPI.

## Credenciales por defecto

| Usuario | Contraseña |
| --- | --- |
| root | 1234 |

---

## Configurar la IA (Gesti)

Crea una cuenta gratis en [console.groq.com](https://console.groq.com) y agrega en `.env`:

```env
NICAGEST_IA_MODO=groq
GROQ_API_KEY=tu_key_aqui
```

Alternativas: OpenAI (`NICAGEST_IA_MODO=openai`) u Ollama (`NICAGEST_IA_MODO=ollama`).

> Gesti es el asistente IA de la plataforma. Responde con tono amigable, conoce tu inventario, clientes, ventas y la **tasa de cambio** configurada. Las conversaciones se guardan automáticamente y se recuperan al volver al Dashboard.

---

## Configuración del negocio

Desde el panel de configuración (icono de engranaje en el sidebar) se puede ajustar:

| Campo | Descripción |
| --- | --- |
| **Nombre del negocio** | Se muestra en el sidebar y en las facturas PDF |
| **Color de acento** | Color principal de la interfaz y las facturas |
| **Tasa de cambio** | Tasa C$/USD usada en facturas y cotizaciones |
| **Zona horaria** | Zona horaria para mostrar horas en ventas, detalle y facturas PDF. Por defecto `America/Managua` |

---

## Funcionalidades

### Clientes con código único

Cada cliente registrado recibe automáticamente un **código único de 6 caracteres alfanuméricos** (ej. `9DP7Q0`). Este código:
- Se genera automáticamente al crear el cliente.
- Es fijo e inamovible (no se puede editar).
- Se muestra en la tabla de clientes y en el modal de edición.
- Se puede buscar por código en el campo de búsqueda.

### Zona horaria configurable

Todas las horas en el sistema (ventas, detalle, facturas PDF) se muestran según la **zona horaria** configurada por el usuario, utilizando `Intl.DateTimeFormat` en el frontend y `zoneinfo` en el backend.

---

## Estructura

```
Gest/
├── main.py                         ← Entrada FastAPI
├── requirements.txt
├── .env
├── Backend/
│   ├── ai/ia_service.py            ← Gesti (Groq / OpenAI / Ollama)
│   ├── db/
│   │   ├── database.py             ← SQLAlchemy engine + session + migraciones
│   │   ├── models.py               ← Modelos ORM (Usuario, Producto, Venta, Cliente…)
│   │   └── schema.sql              ← (legacy, ya no se usa)
│   ├── models/schema.py            ← Modelos Pydantic
│   └── routers/
│       ├── auth.py                 ← JWT + perfil + tasa de cambio + zona horaria
│       ├── productos.py            ← Inventario y movimientos
│       ├── ventas.py               ← Punto de venta con promociones
│       ├── clientes.py             ← Clientes, crédito y código único
│       ├── reportes.py             ← Dashboard, Gesti, predictivos, chat con historial
│       ├── facturas.py             ← PDF con reportlab (C$ + US$, formato miles, zona horaria)
│       ├── organizacion.py         ← Navegación jerárquica de facturas
│       └── promociones.py          ← Promociones y descuentos
└── Frontend/
    ├── package.json
    ├── tailwind.config.js
    ├── vite.config.js               ← Proxy de API para desarrollo
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx                 ← Rutas
    │   ├── index.css               ← Tema claro/oscuro + componentes
    │   ├── components/
    │   │   ├── Layout.jsx          ← Sidebar + theme toggle + configuración
    │   │   └── Modal.jsx
    │   ├── hooks/useTheme.js
    │   ├── context/AuthContext.jsx  ← Auth + zona horaria
    │   ├── lib/api.js              ← Cliente HTTP, formato de moneda y hora
    │   └── pages/
    │       ├── LoginPage.jsx
    │       ├── DashboardPage.jsx   ← Gesti + predictivos + resumen
    │       ├── InventarioPage.jsx
    │       ├── VentasPage.jsx
    │       ├── ClientesPage.jsx    ← Código único visible
    │       ├── PromocionesPage.jsx
    │       └── OrganizacionPage.jsx
```

---

## Facturas PDF

Las facturas generadas incluyen:
- **Doble moneda**: montos en C$ (córdobas) y US$ (dólares), convertidos según la tasa de cambio configurada.
- **Formato de miles**: todos los valores numéricos separados con coma (ej. `C$ 20,500.00`).
- Logo del negocio, color de acento y organización por semana/día.
- **Zona horaria del usuario**: la hora de la factura respeta la zona horaria configurada.

## Historial de chat

Las conversaciones con Gesti se guardan automáticamente en la base de datos. Al volver al Dashboard, el historial se carga y puedes retomar la conversación donde la dejaste.

## Temas

La aplicación soporta **tema claro y oscuro** (y modo sistema). El toggle está en el sidebar. La preferencia se guarda en `localStorage`.

## Tasa de cambio

Cada usuario puede configurar su propia tasa de cambio C$/USD desde el perfil. Gesti la conoce y la usa al responder preguntas sobre valores en dólares. También se usa en las facturas PDF para mostrar el equivalente en US$.
