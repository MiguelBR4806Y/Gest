# Bravo's Gest 🇳🇮

Sistema de gestión para negocios locales (inventario, ventas, facturación, clientes, IA) adaptado al comercio de Nicaragua. Proyecto desarrollado como parte del plan de estudio de Ingeniería de Sistemas (Ciclo 5).

## Stack
- **Backend**: Python 3.11+ · FastAPI · SQLite
- **Frontend**: HTML / CSS / JavaScript · Bootstrap 5.3
- **IA**: Groq (Llama 3.3 70B) — análisis de ventas, chat inteligente y reportes predictivos, gratis sin tarjeta. También soporta OpenAI y Ollama como alternativas configurables.

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

### Funcionalidades de IA disponibles

- **Análisis del día**: resumen automático de ventas al cargar el dashboard.
- **Chat inteligente**: el dueño del negocio puede hacer preguntas en lenguaje natural sobre ventas, inventario, clientes y movimientos. El historial persiste 30 días en el navegador.
- **Reportes predictivos**: tres tarjetas automáticas que muestran productos a reabastecer pronto (según ritmo de ventas), días de mayor venta histórica, y proyección de ingresos para los próximos 7 días.

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
| POST | /auth/registro | Crear cuenta nueva |
| GET | /auth/perfil | Obtener configuración del negocio |
| PUT | /auth/perfil | Actualizar nombre y color de acento |
| POST | /auth/perfil/logo | Subir logo del negocio |
| GET | /productos/ | Listar productos |
| POST | /productos/ | Crear producto |
| PUT | /productos/{id} | Editar producto |
| DELETE | /productos/{id} | Eliminar producto |
| GET | /productos/stock-bajo | Alertas de stock |
| POST | /productos/{id}/recargar | Recargar inventario |
| POST | /ventas/ | Registrar venta completa (validación de stock y crédito) |
| GET | /ventas/resumen-dia | Resumen del día con métricas agrupadas |
| GET | /clientes/ | Listar clientes |
| POST | /clientes/ | Crear cliente |
| PUT | /clientes/{id} | Editar cliente |
| DELETE | /clientes/{id} | Eliminar cliente |
| GET | /clientes/{id}/compras | Historial de compras del cliente |
| GET | /reportes/dashboard | Métricas generales del dashboard |
| GET | /reportes/ventas | Ventas del día con análisis IA |
| GET | /reportes/predictivos | Reportes predictivos (reabastecimiento, días, proyección) |
| POST | /reportes/chat | Chat con IA usando contexto completo del negocio |
| GET | /facturas/{venta_id} | Generar PDF de factura |
| GET | /facturas/preview | Vista previa de factura con configuración actual |
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
│       ├── auth.py                ← Autenticación JWT + configuración del negocio
│       ├── productos.py           ← Inventario y movimientos
│       ├── ventas.py              ← Punto de venta
│       ├── clientes.py            ← Clientes y crédito
│       ├── reportes.py            ← Reportes, IA, chat y predictivos
│       └── facturas.py            ← Generación de PDF con reportlab
└── Frontend/
    ├── static/
    │   ├── style.css
    │   ├── Script.js              ← Auth, sesión global y helpers de API
    │   ├── dashboard.js           ← Métricas, IA, chat y reportes predictivos
    │   ├── inventario.js
    │   ├── cliente.js
    │   └── ventas.js              ← Control de interfaz y resumen diario
    └── Templates/
        ├── index.html             ← Landing + login + registro
        ├── dashboard.html         ← Dashboard con IA integrada
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
| 4 | Facturación relacional, historial detallado, formato regional (`es-NI`), horario 12h AM/PM | ✅ Completa |
| 5 | Integración con Groq (Llama 3.3 70B): análisis del día, chat con historial de 30 días y reportes predictivos (reabastecimiento, días de mayor venta, proyección 7 días) | ✅ Completa |
| 6 | Pruebas finales, pulido de interfaz y despliegue | ⬜ Pendiente |