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

### Ejecutar

```bash
# Terminal 1 — Backend
source venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend (dev)
cd Frontend
npm run dev
```

- Backend: http://127.0.0.1:8000
- Frontend: http://127.0.0.1:5173
- Docs API: http://127.0.0.1:8000/docs

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

## Estructura

```
Gest/
├── main.py                         ← Entrada FastAPI
├── requirements.txt
├── .env
├── Backend/
│   ├── ai/ia_service.py            ← Gesti (Groq / OpenAI / Ollama)
│   ├── db/
│   │   ├── database.py             ← SQLAlchemy engine + session
│   │   ├── models.py               ← Modelos ORM (Usuario, Producto, Venta, ChatMensaje…)
│   │   └── schema.sql              ← (legacy, ya no se usa)
│   ├── models/schema.py            ← Modelos Pydantic
│   └── routers/
│       ├── auth.py                 ← JWT + perfil + tasa de cambio
│       ├── productos.py            ← Inventario y movimientos
│       ├── ventas.py               ← Punto de venta
│       ├── clientes.py             ← Clientes y crédito
│       ├── reportes.py             ← Dashboard, Gesti, predictivos, chat con historial
│       ├── facturas.py             ← PDF con reportlab (C$ + US$, formato miles)
│       ├── organizacion.py         ← Navegación jerárquica de facturas
│       └── promociones.py          ← Promociones y descuentos
└── Frontend/
    ├── package.json
    ├── tailwind.config.js
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx                 ← Rutas
    │   ├── index.css               ← Tema claro/oscuro + componentes
    │   ├── components/
    │   │   ├── Layout.jsx          ← Sidebar + theme toggle
    │   │   └── Modal.jsx
    │   ├── context/AuthContext.jsx
    │   ├── lib/api.js              ← Cliente HTTP
    │   └── pages/
    │       ├── LoginPage.jsx
    │       ├── DashboardPage.jsx
    │       ├── InventarioPage.jsx
    │       ├── VentasPage.jsx
    │       ├── ClientesPage.jsx
    │       └── OrganizacionPage.jsx
```

---

## Facturas PDF

Las facturas generadas incluyen:
- **Doble moneda**: montos en C$ (córdobas) y US$ (dólares), convertidos según la tasa de cambio configurada.
- **Formato de miles**: todos los valores numéricos separados con coma (ej. `C$ 20,500.00`).
- Logo del negocio, color de acento y organización por semana/día.

## Historial de chat

Las conversaciones con Gesti se guardan automáticamente en la base de datos. Al volver al Dashboard, el historial se carga y puedes retomar la conversación donde la dejaste.

## Temas

La aplicación soporta **tema claro y oscuro**. El toggle está en el sidebar. La preferencia se guarda en `localStorage`.

## Tasa de cambio

Cada usuario puede configurar su propia tasa de cambio C$/USD desde el perfil. Gesti la conoce y la usa al responder preguntas sobre valores en dólares. También se usa en las facturas PDF para mostrar el equivalente en US$.
