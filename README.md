# Bravo's Gest

Sistema de gestión para negocios locales: inventario, ventas, facturación, clientes, promociones y análisis con IA.

## Stack

- **Backend**: Python 3.11+ · FastAPI · PostgreSQL · SQLAlchemy
- **Frontend**: React 19 + Vite 8 + Tailwind CSS 3 + react-router-dom v7 + lucide-react
- **IA**: **Gesti** — asistente con Groq (Llama 3.3 70B), OpenAI u Ollama. Análisis de ventas, chat conversacional con historial persistente y reportes predictivos.

---

## Requisitos

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

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
# Genera una SECRET_KEY real (obligatoria, mínimo 32 caracteres):
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
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

> El frontend en dev se sirve en `:5173` con hot reload y redirige las llamadas API al backend mediante el proxy de Vite.
>
> Para producción, ejecutar `npm run build` en `Frontend/` para generar los estáticos que sirve FastAPI.

---

## Credenciales iniciales

**Ya no hay contraseña por defecto.** En el primer arranque, el usuario `root` se crea así:

1. Si definiste `ROOT_PASSWORD` en `.env`, se usa esa.
2. Si no, se genera una contraseña aleatoria y **se muestra una única vez en el log del servidor**.

Si el sistema detecta que `root` sigue con la contraseña antigua `1234`, lo avisa por log para que la cambies.

---

## Seguridad

### Autenticación y sesiones

| Medida | Detalle |
| --- | --- |
| Hash de contraseñas | bcrypt (coste por defecto) |
| Política de contraseñas | Mínimo 8 caracteres, letras **y** números; se rechazan las más comunes; máximo 72 bytes (límite real de bcrypt) |
| Token | JWT HS256 con `iat` y `exp`; 12 h por defecto (`TOKEN_EXPIRE_HOURS`) |
| Revocación | Cambiar la contraseña invalida **todos** los tokens emitidos antes (`password_cambiada_en`) |
| Validación de token | Se comprueba contra la base de datos en cada petición: una cuenta borrada deja de ser válida al instante |
| Enumeración de usuarios | El login compara contra un hash ficticio cuando el usuario no existe, para igualar el tiempo de respuesta |
| Fuerza bruta | Rate limiting por IP (ver tabla abajo) |
| Login con Google | Se validan `aud`, `iss` y `email_verified`, y falla cerrado si `GOOGLE_CLIENT_ID` no está configurado |

> Al cambiar la contraseña se cierran todas las sesiones, incluida la actual: la app te pide iniciar sesión de nuevo.

### Código de verificación por correo

- Generado con `secrets` (no con `random`).
- Caduca a los 15 minutos.
- Máximo 5 intentos; al agotarlos se invalida.
- Comparación en tiempo constante.
- **Nunca se devuelve al cliente.** Si SMTP no está configurado, el código solo aparece en el log del servidor.

### Aislamiento entre cuentas

Cada usuario solo ve y modifica sus propios datos. Todas las consultas de productos, clientes, ventas, promociones y facturas filtran por `usuario_id`, incluidas las que antes no lo hacían (movimientos de inventario, últimas compras, actualizaciones por id).

Las promociones y los clientes referenciados se validan contra el dueño antes de asignarlos.

### Precios e importes

**El precio de venta lo fija siempre el servidor** a partir del producto en base de datos. Lo que envíe el cliente en `precio_unitario` se ignora. Esto cierra la manipulación de importes desde el navegador.

Anular una venta devuelve el stock, registra la entrada de inventario y revierte el crédito usado si la venta fue a crédito.

### Subidas de archivos

Se valida la **firma de bytes real** del archivo, no el `Content-Type` (que lo controla el cliente), además del tamaño:

| Archivo | Tipos | Límite |
| --- | --- | --- |
| Logo del negocio | PNG, JPG | 2 MB |
| Plantilla de factura | PDF | 10 MB |

Los nombres en disco se derivan del id de usuario, sin usar entrada del cliente.

### Servidor

- **Cabeceras**: `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy` y `Strict-Transport-Security` (con `ENABLE_HSTS=1`).
- **Path traversal**: el fallback de la SPA comprueba que la ruta resuelta quede dentro de `Frontend/dist`.
- **CORS**: orígenes explícitos; el comodín `*` se ignora. Los tokens van en la cabecera `Authorization`, así que `allow_credentials` está desactivado.
- **Errores**: las respuestas 500 son genéricas y no filtran trazas ni detalles de base de datos; las 422 traducen el error de validación a un mensaje legible.
- **Rutas de API inexistentes** devuelven 404 en JSON en lugar del `index.html`.
- **X-Request-ID** en cada respuesta para correlacionar logs.
- El contenedor Docker corre como usuario sin privilegios y con `HEALTHCHECK`.

### Validación de entrada

Todas las longitudes, rangos y formatos se validan con Pydantic antes de tocar la base de datos: color de acento hexadecimal, zona horaria existente en `zoneinfo`, tasa de cambio positiva, teléfonos, códigos de verificación numéricos y `metodo_pago` restringido a valores conocidos.

El texto que acaba en los PDF se sanea y escapa para que no inyecte marcado en reportlab.

### Rate limiting

Ventana deslizante en memoria, por IP:

| Ámbito | Límite |
| --- | --- |
| Login | 10 / minuto |
| Registro | 5 / hora |
| OAuth Google | 10 / minuto |
| Cambio de contraseña | 5 / 15 min |
| Envío de código | 5 / 15 min |
| Verificación de código | 10 / 15 min |
| Eliminación de cuenta | 3 / hora |
| Chat con IA | 20 / 5 min |
| Descarga de facturas | 30 / 5 min |
| Subidas | 10 / 5 min |
| Perfil y tasa de cambio | 30 / minuto |

> El limitador vive en memoria: con varios workers de uvicorn cada uno lleva su propia cuenta. Para despliegues multi-instancia hay que moverlo a Redis manteniendo la interfaz de `Backend/security.py`.
>
> Si la app está detrás de un proxy inverso, define `TRUST_PROXY_HEADERS=1` **solo** si ese proxy sobrescribe `X-Forwarded-For`. Si no, cualquiera podría falsear su IP y saltarse los límites.

---

## Variables de entorno

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `DATABASE_URL` | — | Cadena de conexión a PostgreSQL |
| `SECRET_KEY` | — | **Obligatoria.** Firma de los JWT. 32+ caracteres |
| `TOKEN_EXPIRE_HOURS` | `12` | Horas de validez del token |
| `ROOT_PASSWORD` | aleatoria | Contraseña inicial del usuario `root` |
| `CORS_ORIGINS` | `localhost:5173,localhost:8000` | Orígenes permitidos, separados por coma |
| `TRUST_PROXY_HEADERS` | `0` | Confiar en `X-Forwarded-For` |
| `ENABLE_HSTS` | `0` | Activar `Strict-Transport-Security` (solo con HTTPS) |
| `EXPOSER_DOCS` | `1` | Poner `0` para desactivar `/docs` en producción |
| `CONTENT_SECURITY_POLICY` | política por defecto | Solo si añades recursos externos |
| `NOMBRE_NEGOCIO` | `Mi Negocio` | Nombre por defecto en las facturas |
| `FRONTEND_URL` | `http://localhost:5173` | Enlaces en los correos |
| `GOOGLE_CLIENT_ID` | — | Client ID de Google OAuth |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM` | — | Envío de códigos de verificación |

### Configurar la IA (Gesti)

Crea una cuenta gratuita en [console.groq.com](https://console.groq.com) y agrega en `.env`:

```env
NICAGEST_IA_MODO=groq
GROQ_API_KEY=tu_key_aqui
```

Alternativas: OpenAI (`NICAGEST_IA_MODO=openai`) u Ollama (`NICAGEST_IA_MODO=ollama`).

> Gesti responde con tono amigable y conoce tu inventario, clientes, ventas y la tasa de cambio configurada. Las conversaciones se guardan y se recuperan al volver al Dashboard.
>
> El contexto que se envía al modelo tiene un tope de filas (300 ventas, 100 movimientos) para acotar coste y tamaño del prompt. Los datos del negocio se mandan en un bloque separado con la instrucción explícita de tratarlos como datos y no como órdenes.

---

## Configuración del negocio

Desde el panel de configuración (engranaje en el sidebar) se puede ajustar:

| Campo | Descripción |
| --- | --- |
| **Nombre del negocio** | Se muestra en el sidebar y en las facturas PDF |
| **Color de acento** | Color principal de la interfaz y las facturas. Se aplica al instante en toda la app |
| **Tasa de cambio** | Tasa C$/USD usada en facturas, cotizaciones y precios en dólares |
| **Zona horaria** | Zona para mostrar horas en ventas, detalle y facturas PDF. Por defecto `America/Managua` |

### Color de acento

El color elegido genera una escala completa en tiempo de ejecución (`src/lib/color.js`) que sobrescribe las variables CSS del tema. Afecta a botones, enlaces, badges, el sidebar y los anillos de foco.

Si eliges un color claro, el texto de los botones cambia automáticamente a oscuro según la luminancia, para mantener el contraste.

---

## Interfaz

- **Tema claro / oscuro / sistema.** La preferencia se guarda en `localStorage` y se aplica antes del primer pintado (`public/theme-boot.js`) para que no haya destello al cargar.
- **Responsive.** Sidebar fijo y colapsable en escritorio; menú lateral deslizante en móvil, con cierre por Escape y al cambiar de ruta.
- **Accesibilidad.** Foco visible en todos los elementos interactivos, `aria-label` en los botones de icono, etiquetas asociadas a sus campos, trampa de foco y restauración al cerrar los modales, regiones `aria-live` para las notificaciones, y respeto de `prefers-reduced-motion` (que detiene las animaciones de fondo).
- **Carga.** Esqueletos con la forma del contenido en lugar de spinners genéricos.
- **Componentes compartidos.** `Button`, `Field`, `Input`, `Select`, `Checkbox`, `Card`, `StatCard`, `EmptyState`, `Skeleton`, `Modal` y `ConfirmDialog` en `src/components/ui/`.

---

## Funcionalidades

### Clientes con código único

Cada cliente recibe un **código único de 6 caracteres alfanuméricos** (ej. `9DP7Q0`):

- Se genera automáticamente y es inmutable.
- Se muestra en la tabla y en el modal de edición.
- Se puede buscar por código.

### Zona horaria configurable

Todas las horas (ventas, detalle, facturas PDF) se muestran según la zona configurada, con `Intl.DateTimeFormat` en el frontend y `zoneinfo` en el backend.

### Inventario

- Alta, edición y eliminación de productos con categoría, stock y stock mínimo.
- Recarga de stock e historial de movimientos (entradas y salidas).
- Alertas de stock bajo en el inventario y el dashboard.
- Asignación de promociones por producto.

### Ventas

- Punto de venta con carrito, selección de cliente y método de pago (efectivo, tarjeta, transferencia, crédito).
- Aplicación automática de promociones (porcentaje, monto fijo, 2x1).
- Validación de stock antes de confirmar y de crédito disponible en ventas a crédito.
- Anulación de ventas con devolución de stock y reversión de crédito.
- Filtro por fecha y búsqueda por cliente o producto.

### Facturas PDF

- **Doble moneda**: C$ y US$ según la tasa configurada.
- **Formato de miles** (ej. `C$ 20,500.00`).
- Logo del negocio, color de acento y organización por semana/día.
- Hora según la zona horaria del usuario.
- Navegación jerárquica y descarga por año, semestre, trimestre, mes, semana o día (ZIP).

### Dashboard

Métricas del día, últimas ventas, productos con stock bajo, desglose por método de pago, promociones activas y comparativa de ingresos con el año anterior.

### Gesti IA

Chat con historial persistente, análisis del día y proyecciones (reabastecimiento, mejores días, proyección a 7 días).

---

## Estructura

```
Gest/
├── main.py                         ← Entrada FastAPI + middleware y cabeceras de seguridad
├── requirements.txt
├── Dockerfile                      ← Multi-etapa; runtime sin privilegios
├── docker-compose.yml
├── .env
├── Backend/
│   ├── security.py                 ← Rate limiting, validación de subidas, saneado
│   ├── ai/ia_service.py            ← Gesti (Groq / OpenAI / Ollama)
│   ├── db/
│   │   ├── database.py             ← Engine, sesión y migraciones idempotentes
│   │   ├── models.py               ← Modelos ORM
│   │   └── schema.sql              ← (legacy, ya no se usa)
│   ├── models/schema.py            ← Modelos Pydantic con validación
│   ├── services/email_service.py   ← Códigos de verificación por correo
│   └── routers/
│       ├── auth.py                 ← JWT + perfil + seguridad de cuenta
│       ├── productos.py            ← Inventario y movimientos
│       ├── ventas.py               ← Punto de venta + anulación
│       ├── clientes.py             ← Clientes, crédito y código único
│       ├── reportes.py             ← Dashboard, Gesti, predictivos, chat
│       ├── facturas.py             ← PDF con reportlab
│       ├── organizacion.py         ← Navegación jerárquica de facturas
│       └── promociones.py          ← Promociones y descuentos
└── Frontend/
    ├── index.html
    ├── public/theme-boot.js        ← Tema antes del primer pintado
    ├── tailwind.config.js
    ├── vite.config.js               ← Proxy de API para desarrollo
    └── src/
        ├── main.jsx
        ├── App.jsx                 ← Rutas
        ├── index.css               ← Tokens de diseño, componentes y utilidades
        ├── components/
        │   ├── Layout.jsx          ← Sidebar, header y avisos
        │   ├── Modal.jsx           ← Diálogo accesible + ConfirmDialog
        │   ├── SettingsModal.jsx   ← Perfil y seguridad
        │   ├── Toast.jsx
        │   ├── AuroraBackground.jsx
        │   └── ui/                 ← Button, Field, Card, Feedback
        ├── context/
        │   ├── AuthContext.jsx     ← Sesión, revalidación y color de acento
        │   └── ToastContext.jsx
        ├── hooks/
        │   ├── useTheme.js
        │   └── useDebounce.js
        ├── lib/
        │   ├── api.js              ← Cliente HTTP, descargas y formato
        │   └── color.js            ← Escala de color de acento
        └── pages/
            ├── LoginPage.jsx
            ├── DashboardPage.jsx
            ├── InventarioPage.jsx
            ├── VentasPage.jsx
            ├── ClientesPage.jsx
            ├── PromocionesPage.jsx
            ├── OrganizacionPage.jsx
            └── GestiPage.jsx
```

---

## Docker

```bash
docker compose up --build
```

La app queda en http://localhost:8000. El `Dockerfile` compila el frontend en una etapa aparte, corre como usuario sin privilegios y expone un `HEALTHCHECK` contra `/health`.

---

## Recomendaciones para producción

1. **Rota los secretos** si estuvieron expuestos en texto plano: `GROQ_API_KEY`, `SMTP_PASS`, la contraseña de PostgreSQL y `SECRET_KEY`.
2. Sirve siempre por **HTTPS** y activa `ENABLE_HSTS=1`.
3. Pon `EXPOSER_DOCS=0` para no publicar `/docs`.
4. Define `CORS_ORIGINS` con tu dominio real.
5. Si usas proxy inverso, define `TRUST_PROXY_HEADERS=1` solo si ese proxy reescribe `X-Forwarded-For`.
6. Programa copias de seguridad de PostgreSQL y del directorio `facturas/`.
