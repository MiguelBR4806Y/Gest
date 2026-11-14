# Bravo's Gest

Sistema de gestión para negocios locales: inventario, ventas, facturación, clientes, crédito, promociones, cierre de caja y análisis con IA.

La prioridad de la versión 1.2 es que **los números cuadren**: importes exactos, ventas que se anulan sin borrarse y stock que no se puede sobrevender.

## Stack

- **Backend**: Python 3.11+ · FastAPI · PostgreSQL · SQLAlchemy
- **Frontend**: React 19 + Vite 8 + Tailwind CSS 3 + react-router-dom v7 + lucide-react
- **IA**: **Gesti** — asistente con Groq (Llama 3.3 70B), OpenAI u Ollama
- **Pruebas**: pytest contra PostgreSQL real (84 pruebas)

---

## Lo que cambió en 1.2

| Área | Antes | Ahora |
| --- | --- | --- |
| Dinero | `FLOAT` en toda la base | `NUMERIC(12,2)` + `Decimal` con redondeo comercial |
| Anular venta | `DELETE` de la venta y sus líneas | Estado `anulada`, motivo, autor y fecha; stock y crédito revertidos |
| Stock | Validar y luego restar | Bloqueo de fila + `UPDATE` condicional + `CHECK (stock >= 0)` |
| Sesiones | Revocación por marca de tiempo (±1 s) | `token_version` en el JWT: revocación exacta |
| Día del negocio | Resta fija de 6 horas (UTC-6) | `zoneinfo` con la zona configurada (soporta horario de verano) |
| Dashboard | Varias consultas por petición | Una sola pasada con agregados `FILTER` |
| Listado de clientes | Una consulta por cliente (N+1) | Una sola agregación |
| Índices | Ninguno | Índices compuestos por `usuario_id` y fecha |
| Borrados | Ventas y clientes desaparecían | Se bloquea borrar historial; solo se anula |
| Auditoría | No existía | Tabla `eventos` + página **Actividad** |
| Caja | No existía | **Cierre de caja** por método de pago |
| Contabilidad | Sin exportación | **CSV** de ventas por rango de fechas |
| POS | Solo selección manual | **Escáner de código de barras** |
| Crédito | Un `float` editable a mano | **Abonos** con validación de saldo y auditoría |
| Contraseña | Sin recuperación ("pide al administrador") | **Enlace por correo** de un solo uso, 30 min, revoca sesiones |
| Costos | No existían | **Costo por producto** y **margen real** con el costo congelado al vender |
| Cobro | Un reintento podía duplicar la venta | **Idempotency-Key** en el POS |

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

> Para producción, ejecutar `npm run build` en `Frontend/` y FastAPI sirve los estáticos.

---

## Pruebas

Las pruebas corren contra **PostgreSQL real** (no SQLite): las consultas usan `AT TIME ZONE`, `STRING_AGG` y `FILTER`, que SQLite no implementa igual.

```bash
pip install -r requirements-dev.txt

# Una sola vez: crear la base de pruebas
psql -U postgres -c "CREATE DATABASE nicagest_test;"

pytest                                  # 84 pruebas
pytest tests/test_ventas.py -v          # solo ventas
ruff check Backend main.py tests --select E,F,W,I --ignore E501
```

La URL se toma de `TEST_DATABASE_URL` (si no, `postgresql://postgres:1234@localhost:5432/nicagest_test`). Cada prueba limpia las tablas con `TRUNCATE ... RESTART IDENTITY CASCADE`.

### Qué cubren

- **Dinero** (`test_dinero.py`): redondeo half-up, `0.1 + 0.2`, entradas inválidas, tasas de 4 decimales, rangos de día por zona horaria y día de 23 h por cambio de horario.
- **Ventas** (`test_ventas.py`): descuento de stock, sobreventa, líneas repetidas fusionadas, precio del cliente ignorado, promociones, crédito, anulación reversible, doble anulación, **dos cajas vendiendo la última unidad a la vez** y métodos de pago.
- **Seguridad** (`test_seguridad.py`): login, política de contraseñas, revocación de tokens, aislamiento entre cuentas, promociones ajenas, `Cache-Control`, límite de cuerpo.
- **Clientes e inventario** (`test_clientes.py`): códigos únicos, última compra, abonos, bloqueo de borrado con historial, stock mínimo, búsqueda, código de barras y cierre de caja.
- **Reportes** (`test_reportes.py`): dashboard sin anuladas, auditoría, CSV, paginación y aislamiento.
- **Recuperación** (`test_recuperacion.py`): respuesta que no enumera cuentas, token hasheado, un solo uso, caducidad, revocación de sesiones y auditoría.
- **Margen** (`test_margen.py`): costo congelado al vender, reparto de descuentos, reporte por producto y CSV.
- **Idempotencia** (`test_idempotencia.py`): reintento con la misma clave, claves por usuario, clave inválida y **dos cobros simultáneos**.

CI (`.github/workflows/ci.yml`) ejecuta lint + pruebas con un servicio PostgreSQL y compila el frontend en cada push.

---

## Dinero: precisión exacta

- Todas las columnas monetarias son `NUMERIC(12,2)` (`total`, `precio`, `precio_dolar`, `credito_limite`, `credito_usado`, `precio_unitario`, `valor`).
- En Python se calcula con `Decimal` y `ROUND_HALF_UP` (`Backend/dinero.py`). El precio de la tasa de cambio usa 4 decimales.
- El `float` aparece **solo** al serializar la respuesta JSON (`a_float`), nunca en un cálculo.
- Los datos antiguos en `FLOAT` se convierten una sola vez al arrancar:

```sql
ALTER TABLE ventas ALTER COLUMN total TYPE NUMERIC(12,2)
USING ROUND(total::numeric, 2);
```

Ejemplo real de la migración: `2.675 → 2.68`, `0.30000000000000004 → 0.30`.

## Anulación de ventas (sin borrar)

Anular **no elimina** la venta. Se marca y se revierte:

- `estado = 'anulada'`, `anulada_en`, `anulada_por`, `motivo_anulacion`.
- Se devuelve el stock (con movimiento de entrada) y se revierte el crédito usado.
- La venta sigue existiendo y su factura se genera con el aviso **VENTA ANULADA**.
- Los totales del dashboard, reportes y cierre de caja excluyen las anuladas.
- Anular dos veces devuelve `409`.

La UI pide el motivo y lo guarda; queda en **Actividad**.

## Concurrencia de stock

Crear una venta sigue este orden:

1. Se agrupan las líneas por producto y se validan contra el stock.
2. `SELECT ... FOR UPDATE OF productos` ordenado por `id` (evita interbloqueos).
3. Se recalcula el subtotal en el servidor con `Decimal` (se ignoran precios del cliente).
4. `UPDATE productos SET stock = stock - :n WHERE id = :id AND stock >= :n`; si no afecta a una fila, la venta se aborta con `409`.
5. La base tiene `CHECK (stock >= 0)` como última red.

Resultado: dos cajas simultáneas sobre la última unidad → una vende, la otra recibe `409`.

## Recuperación de contraseña

1. El usuario pide el enlace con su usuario **o** correo (`POST /auth/recuperar`).
2. La respuesta es idéntica exista o no la cuenta (no se pueden enumerar usuarios).
3. Se genera un token con `secrets.token_urlsafe(32)`; en la base solo se guarda su **SHA-256**.
4. Caduca a los **30 minutos**, es de **un solo uso** y hay un enfriamiento de 60 s entre solicitudes.
5. `POST /auth/reset` cambia la contraseña, incrementa `token_version` y **revoca todas las sesiones**.
6. Queda registrado en la auditoría (`recuperacion_solicitada`, `password_restablecida`).

Sin SMTP configurado el flujo no envía nada; para desarrollo se puede poner
`LOG_RESET_LINK=1` y el enlace aparece en el log (nunca en la respuesta HTTP).

## Costo, margen y rentabilidad

- Cada producto tiene `costo` (`NUMERIC(12,2)`).
- Al vender se guarda `costo_unitario` en la línea: **el costo queda congelado**. Cambiar el costo del producto después no reescribe el margen histórico.
- El dashboard y el cierre de caja muestran **ganancia** y **margen %** del día.
- `GET /reportes/margenes?desde&hasta` devuelve ingresos, costo, ganancia y margen por producto. El descuento de la venta se reparte entre sus líneas en proporción al importe bruto.
- El CSV exportado incluye `Costo C$` y `Ganancia C$` por factura.

## Idempotencia del cobro

El POS envía una cabecera `Idempotency-Key` por intento de cobro:

- Si la venta ya existe con esa clave, devuelve la original con `repetida: true` y **no descuenta stock otra vez**.
- La clave es única por usuario (`UNIQUE (usuario_id, idempotency_key) WHERE idempotency_key IS NOT NULL`).
- Dos peticiones simultáneas con la misma clave: una crea la venta y la otra recibe la misma, sin duplicar.
- Si la venta original fue anulada, el reintento devuelve `409`.

## Crédito y abonos

- Límite y saldo por cliente, ambos `NUMERIC`.
- `POST /clientes/{id}/abono` descuenta saldo, rechaza montos mayores al pendiente y deja evento de auditoría.
- Editar el saldo a mano sigue disponible para correcciones, pero también queda auditado.

---

## Seguridad

### Autenticación y sesiones

| Medida | Detalle |
| --- | --- |
| Hash de contraseñas | bcrypt |
| Política | Mínimo 8 caracteres, letras y números; lista negra; máximo 72 bytes |
| Token | JWT HS256 con `sub`, `ver`, `iat`, `exp` |
| Revocación | `token_version`: cambiar la contraseña incrementa la versión e invalida **todos** los tokens anteriores, sin heurísticas de tiempo |
| Validación | El token se comprueba contra la base en cada petición; una cuenta borrada deja de valer al instante |
| Enumeración | El login compara contra un hash ficticio cuando el usuario no existe |
| Fuerza bruta | Rate limiting por IP |
| Login con Google | Valida `aud`, `iss` y `email_verified`; falla cerrado sin `GOOGLE_CLIENT_ID` |

### Aislamiento entre cuentas

Todas las consultas filtran por `usuario_id`: productos, clientes, ventas, movimientos, promociones, facturas, reportes y auditoría. Las promociones y clientes referenciados se validan contra el dueño.

### Endurecimiento del servidor

- **Límite de cuerpo**: `MAX_BODY_BYTES` (12 MB por defecto) → `413` antes de leer el JSON.
- **Cabeceras**: CSP, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, `X-Permitted-Cross-Domain-Policies` y HSTS opcional.
- **Sin caché**: `Cache-Control: no-store` en todas las rutas de API.
- **Compresión**: GZip para respuestas grandes.
- **Hosts**: `ALLOWED_HOSTS` activa `TrustedHostMiddleware`.
- **Path traversal**: el fallback de la SPA comprueba que la ruta resuelta quede dentro de `Frontend/dist`.
- **CORS**: orígenes explícitos, `*` ignorado.
- **Errores**: los 500 son genéricos; los 422 traducen el error de validación.
- El contenedor Docker corre sin privilegios y con `HEALTHCHECK`.

### Subidas de archivos

Se valida la firma de bytes real, no el `Content-Type`: logo PNG/JPG hasta 2 MB, plantilla PDF hasta 10 MB. El nombre en disco se deriva del id de usuario.

### Rate limiting

Ventana deslizante en memoria por IP: login 10/min, registro 5/h, OAuth 10/min, contraseña 5/15 min, código 5/15 min, chat IA 20/5 min, descargas 30/5 min, exportación 10/5 min, subidas 10/5 min, perfil 30/min.

> Vive en memoria: con varios workers cada uno lleva su cuenta. Para multi-instancia hay que moverlo a Redis manteniendo la interfaz de `Backend/security.py`.

---

## Interfaz

- **Navegación agrupada** por Principal, Operación, Análisis y Documentos, con indicador de sección activa.
- **Barra inferior en móvil** con los cuatro accesos de uso diario y "Más" para el resto (zona del pulgar).
- **Gráfico de tendencia** de 7 días con ventas y ganancia, en SVG puro (sin dependencias).
- **Cabeceras de tabla fijas**, filtros segmentados y **steppers de cantidad** en el carrito del POS.
- **Atajos**: `F2` abre Nueva venta y `Cmd/Ctrl + Enter` cobra.
- **Ergonomía táctil**: objetivos de 44 px y campos de 16 px en pantallas táctiles (evita el zoom automático de iOS).
- **Estados completos**: skeletons con shimmer, vacío, error, carga y deshabilitado; se respeta `prefers-reduced-motion`.
- Entrar directo o refrescar `/ventas`, `/clientes`, `/promociones` u `/organizacion` sirve la SPA (antes devolvía 404).

## Funcionalidades

### Punto de venta

- Carrito con cliente, método de pago y **escáner de código de barras** (Enter agrega el producto).
- Búsqueda por código exacto (`GET /productos/codigo/{codigo}`) o por nombre.
- Promociones automáticas (porcentaje, monto fijo, 2x1) calculadas en el servidor.
- Validación de stock y de crédito antes de confirmar.
- Anulación con motivo, visible en el historial.

### Cierre de caja

`GET /ventas/cierre?fecha=YYYY-MM-DD` devuelve:

- Total vendido, cantidad de operaciones y ticket promedio.
- Desglose por método de pago y **efectivo esperado**.
- Anuladas del día (cantidad e importe).
- Primera y última venta.

Desde Ventas se abre en un modal y se puede exportar el CSV del día.

### Exportación CSV

`GET /reportes/exportar?desde=...&hasta=...` — separador `;`, BOM UTF-8 para Excel, importes con dos decimales y estado de cada venta. Máximo 50 000 filas y 10 descargas cada 5 minutos.

### Auditoría

Tabla `eventos` con `usuario_id`, tipo, entidad, id y detalle, escrita en la misma transacción que la operación. Eventos: venta creada/anulada, producto creado/editado/eliminado, recarga de inventario, cliente creado/editado/eliminado y abono de crédito.

`GET /reportes/eventos` alimenta la página **Actividad**, con filtro por tipo y búsqueda libre.

### Inventario

- Producto con categoría, **código de barras único por negocio**, stock, stock mínimo y precio.
- Recarga, movimientos de entrada/salida y alertas de stock bajo usando el mínimo de cada producto.
- No se puede eliminar un producto con ventas registradas (`409`): las facturas históricas conservan sus líneas.

### Clientes

- Código único de 6 caracteres, inmutable.
- Crédito con límite, saldo y disponible; abonos auditados.
- Historial de compras.
- No se puede eliminar un cliente con ventas (`409`).

### Facturas PDF

- Doble moneda (C$/US$), formato de miles y zona horaria del negocio.
- Logo, color de acento y organización por año/semestre/trimestre/mes/semana/día.
- Descarga individual o ZIP por periodo (tope de 3 000 facturas por ZIP).
- Las anuladas se generan con el aviso **VENTA ANULADA**.

### Dashboard

- Ventas del día, ticket promedio, variación frente a ayer y anuladas.
- Productos, clientes y stock bajo en una sola consulta.
- Últimas ventas, métodos de pago, promociones activas y resumen anual.

### Gesti IA

Chat con historial persistente, análisis del día y proyecciones. El contexto va acotado (300 ventas, 100 movimientos) y los datos del negocio se envían como datos, no como instrucciones.

---

## Variables de entorno

| Variable | Por defecto | Descripción |
| --- | --- | --- |
| `DATABASE_URL` | — | Conexión a PostgreSQL |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE` | `10` / `20` / `30` / `1800` | Pool de conexiones |
| `SECRET_KEY` | — | **Obligatoria**, 32+ caracteres |
| `TOKEN_EXPIRE_HOURS` | `12` | Validez del JWT |
| `ROOT_PASSWORD` | aleatoria | Contraseña inicial de `root` |
| `CORS_ORIGINS` | `localhost:5173,localhost:8000` | Orígenes permitidos |
| `ALLOWED_HOSTS` | vacío | Hosts aceptados (`TrustedHostMiddleware`) |
| `MAX_BODY_BYTES` | `12582912` | Tamaño máximo del cuerpo |
| `TRUST_PROXY_HEADERS` | `0` | Confiar en `X-Forwarded-For` |
| `ENABLE_HSTS` | `0` | Activar HSTS (solo con HTTPS) |
| `EXPOSER_DOCS` | `1` | `0` desactiva `/docs` |
| `CONTENT_SECURITY_POLICY` | política por defecto | Solo si añades recursos externos |
| `NOMBRE_NEGOCIO` | `Mi Negocio` | Nombre por defecto en facturas |
| `FRONTEND_URL` | `http://localhost:5173` | Enlaces en correos |
| `GOOGLE_CLIENT_ID` | — | Google OAuth |
| `SMTP_*` | — | Códigos de verificación |
| `NICAGEST_IA_MODO` | — | `groq`, `openai` u `ollama` |
| `TEST_DATABASE_URL` | `.../nicagest_test` | Base usada por pytest |
| `LOG_RESET_LINK` | `0` | `1` registra el enlace de recuperación en el log (solo desarrollo) |

---

## Migraciones

No hay Alembic. `Backend/db/database.py` aplica DDL idempotente al arrancar:

1. `Base.metadata.create_all` crea lo que falte.
2. `ADD COLUMN IF NOT EXISTS` para columnas nuevas.
3. Conversión `FLOAT → NUMERIC` **solo si la columna aún no es numeric**.
4. `BACKFILL` de `estado` y `SET NOT NULL`.
5. Restricciones `CHECK` solo si no existen (consulta a `pg_constraint`).
6. `CREATE INDEX IF NOT EXISTS` para los índices.

En bases nuevas `create_all` genera el esquema definitivo y los pasos 2–6 no hacen nada.

---

## Estructura

```
Gest/
├── main.py                         ← FastAPI, límite de cuerpo, cabeceras, GZip, SPA
├── requirements.txt / requirements-dev.txt
├── pytest.ini
├── Dockerfile / docker-compose.yml
├── Backend/
│   ├── dinero.py                   ← Decimal, redondeo half-up, tasas
│   ├── tiempo.py                   ← Rangos de día por zona horaria (DST)
│   ├── auditoria.py                ← Registro de eventos
│   ├── security.py                 ← Rate limiting, subidas, saneado
│   ├── ai/ia_service.py            ← Gesti (Groq / OpenAI / Ollama)
│   ├── db/
│   │   ├── database.py             ← Engine, sesión y migraciones idempotentes
│   │   └── models.py               ← ORM: NUMERIC, estado, eventos, índices
│   ├── models/schema.py            ← Pydantic con Decimal
│   ├── services/email_service.py
│   └── routers/
│       ├── auth.py                 ← JWT con token_version, perfil, seguridad
│       ├── productos.py            ← Inventario, código de barras, movimientos
│       ├── ventas.py               ← POS, anulación, resumen y cierre de caja
│       ├── clientes.py             ← Clientes, crédito y abonos
│       ├── reportes.py             ← Dashboard, IA, CSV, auditoría
│       ├── facturas.py             ← PDF con reportlab
│       ├── organizacion.py         ← Navegación jerárquica y ZIP
│       └── promociones.py
├── tests/
│   ├── conftest.py
│   ├── test_dinero.py
│   ├── test_ventas.py
│   ├── test_seguridad.py
│   ├── test_clientes.py
│   ├── test_reportes.py
│   ├── test_recuperacion.py
│   ├── test_margen.py
│   └── test_idempotencia.py
├── .github/workflows/ci.yml
└── Frontend/
    └── src/
        ├── pages/                  ← Dashboard, Ventas, Inventario, Clientes,
        │                              Promociones, Organización, Gesti, Actividad,
        │                              Rentabilidad y Reset de contraseña
        ├── components/ui/          ← Button, Card, Field, Feedback
        ├── context/ hooks/ lib/
        └── index.css
```

---

## API nueva o ampliada

| Método | Ruta | Uso |
| --- | --- | --- |
| `DELETE` | `/ventas/{id}` | Anular con `{"motivo": "..."}` (no borra) |
| `GET` | `/ventas/resumen-dia?fecha=` | Totales, ticket, anuladas y desglose por método |
| `GET` | `/ventas/cierre?fecha=` | Cierre de caja con efectivo esperado |
| `GET` | `/ventas/?desde&hasta&estado&busqueda&limite&offset` | Listado paginado |
| `GET` | `/reportes/exportar?desde&hasta` | CSV de ventas |
| `GET` | `/reportes/eventos?tipo&limite` | Auditoría |
| `GET` | `/reportes/tendencia?dias=7` | Ventas y ganancia por día (rellena días sin ventas) |
| `GET` | `/productos/codigo/{codigo}` | Búsqueda por código de barras |
| `GET` | `/productos/categorias` | Categorías con conteo |
| `POST` | `/clientes/{id}/abono` | Pago parcial de crédito |
| `POST` | `/auth/recuperar` | Solicita enlace de recuperación (respuesta genérica) |
| `POST` | `/auth/reset` | Cambia la contraseña con el token del enlace |
| `GET` | `/reportes/margenes?desde&hasta` | Ingresos, costo, ganancia y margen por producto |

---

## Docker

```bash
docker compose up --build
```

La app queda en http://localhost:8000.

## Recomendaciones para producción

1. **Rota los secretos** si alguna vez estuvieron en texto plano: `GROQ_API_KEY`, `SMTP_PASS`, contraseña de PostgreSQL y `SECRET_KEY`.
2. Sirve siempre por **HTTPS** y activa `ENABLE_HSTS=1`.
3. Pon `EXPOSER_DOCS=0` y fija `ALLOWED_HOSTS` y `CORS_ORIGINS` con tu dominio real.
4. Si usas proxy inverso, define `TRUST_PROXY_HEADERS=1` **solo** si ese proxy reescribe `X-Forwarded-For`.
5. Programa copias de seguridad de PostgreSQL y del directorio `facturas/`.
6. Con varios workers o instancias, mueve el rate limiting a Redis.
7. Deja `LOG_RESET_LINK=0` en producción: el enlace de recuperación no debe quedar en logs.

## Limitaciones conocidas

- **Un usuario = un negocio**. No hay roles (cajero/gerente) ni auditoría por empleado; es el siguiente paso natural.
- Sin compras a proveedores, gastos, impuestos ni multi-sucursal.
- Sin modo offline/PWA ni impresión térmica de ticket (solo PDF A4).
- Las migraciones son idempotentes, no versionadas con rollback.
