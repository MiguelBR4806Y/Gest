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
| POS | Solo selección manual | **Escáner de código de barras** y **vuelto en efectivo** |
| Crédito | Un `float` editable a mano | **Abonos** con validación de saldo y auditoría |
| Contraseña | Sin recuperación ("pide al administrador") | **Enlace por correo** de un solo uso, 30 min, revoca sesiones |
| Costos | No existían | **Costo por producto** y **margen real** con el costo congelado al vender |
| Cobro | Un reintento podía duplicar la venta | **Idempotency-Key** en el POS |

### Novedades de 1.3

| Área | Ahora |
| --- | --- |
| Catálogo | **Importación CSV** con previsualización, modos crear/actualizar y plantilla descargable |
| Proveedores | Catálogo de proveedores con contacto y estado |
| Compras | Suben stock, **recalculan el costo promedio ponderado** y generan su gasto |
| Gastos | Registro por categorías, filtros por fecha y totales agregados |
| Facturas | Envío por **correo con PDF adjunto** y por **WhatsApp** con enlace de descarga |
| Roles | `admin` y **módulos por cuenta**: ventas, contabilidad y RRHH |
| Contabilidad | Resumen de ingresos, costo, gastos y **utilidad** con exportación CSV |
| Empleados | Plantilla única: vendedores + personal, con **acceso opcional** al sistema |
| Nómina | **Sueldo por persona** con INSS, IR y neto; resumen de planilla y calculadora |
| Bonos y comisiones | **Comisión %** sobre ventas propias y **bonos** puntuales o mensuales |
| Vacaciones | Saldo legal (art. 76) con registro de días tomados y valor en dinero |
| Vendedores | Hasta **10 por negocio**, credenciales generadas y consultables por el admin |
| Atribución | Cada venta guarda qué cuenta la cobró (`vendedor_id`) |

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

pytest                                  # 273 pruebas
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
- **Roles** (`test_roles.py`, `test_vendedores.py`): matriz de permisos admin/vendedor, límite de 10 vendedores, credenciales reversibles y revocación al editar.
- **Compras** (`test_compras.py`): stock, costo promedio ponderado, gasto vinculado, anulación y rechazo si la mercancía ya se vendió.
- **Importación** (`test_importacion.py`): separadores `;` y `,`, cabeceras con acentos, filas inválidas, simulación y modos crear/actualizar.
- **Envío de facturas** (`test_envio_facturas.py`): adjunto PDF, fallback de correo, enlace `wa.me`, descarga pública por token y caducidad.
- **Vuelto** (`test_vuelto.py`): cálculo del cambio, pago exacto, rechazo si el efectivo no alcanza, vuelto con promoción 2x1, redondeo al centavo y presencia en factura y CSV.
- **Empleados** (`test_empleados.py`): vendedores incluidos automáticamente, personal sin cuenta, puestos, aislamiento y borrado en cascada al eliminar la cuenta.
- **Nómina** (`test_nomina.py`, `test_nomina_api.py`): tramos de IR, INSS patronal pequeño/grande, límite exento, resumen de planilla y simulador; los ejemplos publicados de C$ 15 000 y C$ 35 000 cuadran al centavo.
- **Permisos** (`test_permisos.py`): matriz por módulo, 403 cruzados, retiro de permisos sin re-login, fallback de cuentas antiguas y escalada de privilegios bloqueada.
- **Contabilidad** (`test_contabilidad.py`): utilidad = ingresos − costo − gastos, anuladas fuera, compras sin duplicar gasto, serie, CSV y aislamiento.
- **Vacaciones** (`test_vacaciones.py`): 15 días por semestre, prorrateo de 2.5, tope de 30, resta de tomados, valor con salario diario y fechas en cualquier formato.
- **Bonos** (`test_bonos.py`): CRUD, recurrencia que aparece en meses posteriores, bono puntual solo en su mes, filtros, aislamiento y límite de permisos.
- **Comisiones** (`test_comisiones.py`): % sobre ventas propias, anuladas sin comisión, cambio de % que recalcula, suma al bruto y registro de vacaciones por API.

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

---

## Roles y vendedores

- Cada cuenta tiene `rol`: `admin` (dueño del negocio) o `vendedor`.
- Un vendedor es una cuenta hija (`dueno_id`) que opera sobre el **mismo** inventario, clientes y caja del admin.
- Límite de **10 vendedores por negocio**, aplicado con bloqueo de la fila del admin para que dos peticiones simultáneas no creen el número 11.
- Al crear un vendedor se generan credenciales (usuario derivado del nombre y contraseña aleatoria de 12 caracteres).
- El admin puede **ver la contraseña en cualquier momento**, editarla, desactivar la cuenta o borrarla. Para eso la contraseña se guarda dos veces: el hash bcrypt para el login y una copia cifrada con Fernet (clave derivada de `SECRET_KEY`).
- Editar usuario o contraseña, o desactivar la cuenta, incrementa `token_version`: la sesión del vendedor se revoca al instante.
- Borrar un vendedor con ventas **no borra**: lo desactiva, para no reescribir el historial.

### Empleados

`GET /empleados/` une dos fuentes en una sola plantilla:

| Tipo | Origen | Acceso al sistema |
| --- | --- | --- |
| Cuenta | `usuarios` con `rol='vendedor'` | Sí, con sus credenciales |
| Personal | tabla `empleados` | No |

- Al registrar un empleado se puede marcar **Dar acceso al sistema**: se elige ventas, contabilidad y/o RRHH, y se generan usuario y contraseña (o los defines tú). Las credenciales se muestran una vez y luego se consultan en Vendedores.
- El **puesto lo escribe el admin** (`Limpiador`, `Seguridad`, `Bodega`, `Cajera`…), con sugerencias en el formulario.
- El personal sin cuenta se crea, edita y borra desde RRHH; no puede iniciar sesión.
- `GET /empleados/exportar` devuelve el CSV de la planilla con INSS, IR, neto y costo de empresa.
- El listado devuelve `con_acceso`, `sin_acceso` y `resumen` para las tarjetas.

### Sueldo y cálculo de impuestos

Cada empleado y cada vendedor tiene un **salario bruto mensual** (`salario`). Con él se calcula:

| Concepto | Regla | Fuente |
| --- | --- | --- |
| INSS laboral | 7 % del bruto | Decreto 06-2019, art. 11 |
| IR | Tarifa progresiva sobre la renta anual proyectada | Ley 822, art. 23 |
| INSS patronal | 21.50 % (< 50 trabajadores) o 22.50 % | Decreto 06-2019, art. 11 |
| INATEC | 2 % de la planilla | Ley 1063, art. 24 |

El cálculo replica el procedimiento de la DGI: se descuenta el INSS, se proyecta la renta a 12 meses, se aplica la tabla y se divide entre 12.

| Renta neta anual | IR |
| --- | --- |
| hasta C$ 100 000 | 0 % |
| C$ 100 000.01 – 200 000 | 15 % sobre el exceso |
| C$ 200 000.01 – 350 000 | C$ 15 000 + 20 % sobre el exceso |
| C$ 350 000.01 – 500 000 | C$ 45 000 + 25 % sobre el exceso |
| más de C$ 500 000 | C$ 82 500 + 30 % sobre el exceso |

- `GET /empleados/nomina/tabla` expone las tasas y tramos vigentes (la UI los muestra).
- `POST /empleados/nomina/simular` calcula un salario sin guardar nada.
- El listado trae un `resumen` con totales de planilla y el **costo real para la empresa** (bruto + INSS patronal + INATEC).
- El aguinaldo se muestra como provisión informativa; no cotiza al INSS.
- Los empleados inactivos o sin salario no cuentan en el resumen.

> Es una ayuda de cálculo, no una liquidación oficial. Verifica las cifras con la DGI, el INSS y tu contador antes de declarar: la tabla y los porcentajes pueden cambiar por decreto.

### Bonos, comisiones y vacaciones

**Comisiones**: cada cuenta con módulo de ventas tiene un `comision_pct` (0–100 %) que el admin edita cuando quiera. La comisión es ese porcentaje sobre sus **ventas completadas** del periodo; las anuladas no comisionan. Se calcula con `calcular_comision()` en `Backend/nomina.py` y no se guarda en una tabla: se deriva del histórico.

**Bonos**: se registran con persona, concepto, monto y fecha, con recurrencia opcional:

- Un bono puntual cuenta solo en el mes de su fecha.
- Un bono `recurrente` cuenta en todos los meses desde su fecha en adelante. No se duplica en la base: se reconstruye en cada consulta, así que editar el monto afecta también al histórico mostrado.

**Vacaciones** (art. 76, Ley 185): 15 días por cada 6 meses ininterrumpidos, es decir **2.5 días por mes** y **30 al año** (tope). El saldo es devengado menos tomados, nunca negativo, y su valor usa el salario diario (mensual / 30, criterio del MITRAB).

- La antigüedad sale de `fecha_ingreso`; si falta, se usa la fecha de creación de la cuenta.
- `GET /empleados/vacaciones?persona_tipo&persona_id` devuelve el historial y el saldo.
- Registrar más días que el saldo devuelve **409**.

**Impuestos**: bonos y comisiones **se suman al bruto del periodo antes de INSS e IR**, porque son renta del trabajo. `calcular_nomina(base, plantilla, extra)` conserva el resultado anterior cuando `extra = 0`.

| Método | Ruta | Uso |
| --- | --- | --- |
| GET/POST/PUT/DELETE | `/empleados/bonos` | CRUD de bonos |
| GET/POST/DELETE | `/empleados/vacaciones` | Saldo y registros de días |
| GET | `/empleados/resumen-pago?persona_tipo&persona_id&desde&hasta` | Nómina + comisión + bonos + vacaciones |

La exportación de planilla añade `Comisión %`, `Comisión C$`, `Bonos C$`, `Vacaciones días` y `Vacaciones C$`.

> Vacaciones y aguinaldo son **provisiones**: la app calcula el saldo y su valor, pero no genera asientos contables ni pagos.

### Roles, módulos y permisos

El dueño del negocio (`rol='admin'`) tiene todo. Las cuentas hijas reciben un subconjunto de **módulos**:

| Módulo | Da acceso a |
| --- | --- |
| `ventas` | Ventas, inventario, clientes, facturas |
| `contabilidad` | Resumen contable, gastos, compras, proveedores, reportes |
| `rrhh` | Plantilla, sueldos, nómina y exportación de planilla |

- `rol` indica **jerarquía** (dueño vs. subordinado) y `usuarios.modulos` indica **qué puede hacer**.
- Los módulos se leen de la base en cada petición, así que **retirar un permiso surte efecto al instante**, sin esperar a que caduque el token.
- Las cuentas anteriores a esta versión conservan `modulos='ventas'` por migración automática.
- El **admin** sigue siendo el único que gestiona cuentas, configuración y anulación de ventas.
- Quien registra personal con RRHH **no puede conceder módulos que no tiene** (evita la escalada de privilegios).
- El límite de **10 cuentas con acceso** es compartido entre ventas, contabilidad y RRHH; el personal sin cuenta no cuenta para el límite.

### Permisos por endpoint

| Recurso | Admin | ventas | contabilidad | rrhh |
| --- | --- | --- | --- | --- |
| Ver productos / clientes | ✅ | ✅ | ✅ | ❌ |
| Escribir productos / clientes | ✅ | ❌ | ❌ | ❌ |
| Crear y ver ventas | ✅ | ✅ | ❌ | ❌ |
| Anular ventas, cierre de caja | ✅ | ❌ | ❌ | ❌ |
| Facturas (ver y enviar) | ✅ | ✅ | ❌ | ❌ |
| Dashboard, organización, promociones | ✅ | ❌ | ❌ | ❌ |
| Gastos, compras, proveedores | ✅ | ❌ | ✅ | ❌ |
| Reportes y Gesti IA | ✅ | ❌ | ✅ | ❌ |
| Empleados, nómina y planilla | ✅ | ❌ | ❌ | ✅ |
| Vendedores y auditoría | ✅ | ❌ | ❌ | ❌ |

## Contabilidad

`GET /contabilidad/resumen?desde&hasta` (por defecto, el mes en curso):

- Ingresos de ventas completadas, **costo congelado** de sus líneas, gastos del periodo.
- **Utilidad = ingresos − costo − gastos** y margen sobre ingresos.
- Desglose de gastos por categoría.

`GET /contabilidad/serie` agrupa por día o mes para el gráfico; `GET /contabilidad/exportar` devuelve un CSV con ventas y gastos consolidados y una fila de totales.

Una compra a proveedor genera **un** gasto, así que no se cuenta dos veces.

> Es un resumen de gestión: **no calcula IVA ni lleva partida doble**. No sustituye una declaración fiscal.

El filtrado es siempre por `negocio_id`: el JWT del vendedor resuelve al id de su admin, así que ninguna consulta existente cambió de forma.

## Compras, costo promedio y gastos

Registrar una compra (`POST /compras/`) hace todo en una transacción:

1. Bloquea los productos y agrupa las líneas repetidas.
2. Recalcula el **costo promedio ponderado**:
   `costo_nuevo = (costo_previo × stock_previo + costo_compra × cantidad) / (stock_previo + cantidad)`
3. Suma el stock con `UPDATE` condicional y crea un movimiento de entrada por línea.
4. Registra un **gasto** con `categoria="compra"` y `compra_id` enlazado.

El total de la compra lo calcula el servidor: se ignora cualquier importe que mande el cliente.

Anular una compra revierte el stock y elimina su gasto. El costo promedio **no** se recalcula hacia atrás (ya se usó para los márgenes de ventas posteriores), y la anulación falla con `409` si parte de la mercancía ya se vendió.

Un gasto que proviene de una compra no se puede editar ni borrar a mano: se anula la compra.

## Importación de catálogo CSV

`POST /productos/importar?modo=crear|actualizar|ambos&simular=true|false` con `multipart/form-data`.

- Detecta el separador (`;` o `,`) y tolera cabeceras con acentos, mayúsculas y espacios (`Código de barras`, `Precio C$`).
- Solo `nombre` es obligatoria; el resto se completa con valores por defecto.
- Upsert por `codigo_barras` dentro del negocio; sin código, siempre crea.
- Las filas inválidas se reportan en `errores` y **no** abortan la importación.
- `simular=true` devuelve el informe sin escribir nada (lo usa la previsualización).
- Límites: 5 MB, 5 000 filas y 5 importaciones cada 5 minutos.

`GET /productos/plantilla-csv` devuelve un ejemplo con BOM UTF-8 para abrirlo en Excel.

## Envío de facturas

`POST /facturas/{venta_id}/enviar` con `{"canal": "email" | "whatsapp", "destinatario": "..."}`.

- **Correo**: adjunta el PDF (`MIMEApplication`), usa el correo del cliente si no se indica otro y devuelve `503` si SMTP no está configurado.
- **WhatsApp**: no usa la API de Meta. Crea un enlace con token aleatorio (válido 7 días) y devuelve la URL `wa.me` con el mensaje ya escrito; el frontend la abre.
- `GET /facturas/descarga/{token}` es **pública**: valida el SHA-256 del token, la caducidad y sirve el PDF. Es la única ruta de facturas sin JWT y solo expone la factura de ese token.
- El teléfono se normaliza a formato internacional (8 dígitos → prefijo `505`).
- Ambos canales quedan en la auditoría (`factura_enviada`).

Configura `PUBLIC_BASE_URL` con el dominio real para que los enlaces compartidos funcionen fuera de localhost.

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
| Validación | El token se comprueba contra la base en cada petición; una cuenta borrada o desactivada deja de valer al instante |
| Roles | `admin` / `vendedor`; el vendedor hereda el negocio del admin y solo puede vender y consultar |
| Contraseñas de vendedores | Hash bcrypt para el login + copia cifrada con Fernet (clave derivada de `SECRET_KEY`) para que el admin pueda revelarla |
| Enumeración | El login compara contra un hash ficticio cuando el usuario no existe |
| Fuerza bruta | Rate limiting por IP |
| Login con Google | Valida `aud`, `iss` y `email_verified`; falla cerrado sin `GOOGLE_CLIENT_ID` |

### Aislamiento entre cuentas

Todas las consultas filtran por `usuario_id`: productos, clientes, ventas, movimientos, promociones, facturas, reportes y auditoría. Las promociones y clientes referenciados se validan contra el dueño. Con roles, el filtro usa el `negocio_id` de la sesión, así que un vendedor nunca escapa del negocio de su admin.

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

Ventana deslizante en memoria por IP: login 10/min, registro 5/h, OAuth 10/min, contraseña 5/15 min, código 5/15 min, chat IA 20/5 min, descargas 30/5 min, exportación 10/5 min, subidas 10/5 min, perfil 30/min, importación CSV 5/5 min y descarga por token 60/5 min.

> Vive en memoria: con varios workers cada uno lleva su cuenta. Para multi-instancia hay que moverlo a Redis manteniendo la interfaz de `Backend/security.py`.

---

## Interfaz

- **Navegación agrupada** por Principal, Operación, Compras, Análisis, Documentos y Administración. Cada grupo se **abre y cierra** desde su cabecera (se guarda en `localStorage` y el grupo de la ruta activa se despliega solo). El vendedor solo ve Ventas e Inventario.
- **Barra inferior en móvil** con los accesos de uso diario y "Más" para el resto (zona del pulgar); se adapta al rol. El drawer móvil se abre siempre expandido.
- **Gráfico de tendencia** de 7 días con ventas y ganancia, en SVG puro (sin dependencias).
- **Cabeceras de tabla fijas**, filtros segmentados y **steppers de cantidad** en el carrito del POS.
- **Atajos**: `F2` abre Nueva venta y `Cmd/Ctrl + Enter` cobra.
- **Ergonomía táctil**: objetivos de 44 px y campos de 16 px en pantallas táctiles (evita el zoom automático de iOS).
- **Estados completos**: skeletons con shimmer, vacío, error, carga y deshabilitado; se respeta `prefers-reduced-motion`.
- Entrar directo o refrescar `/ventas`, `/clientes`, `/promociones`, `/organizacion`, `/vendedores`, `/empleados`, `/proveedores`, `/compras` o `/gastos` sirve la SPA (antes devolvía 404).

## Funcionalidades

### Punto de venta

- Carrito con cliente, método de pago y **escáner de código de barras** (Enter agrega el producto).
- **Cobro en efectivo con vuelto**: el cajero escribe cuánto entregó el cliente, la app calcula el cambio en vivo y el servidor lo vuelve a calcular sobre el total real (con promociones aplicadas). Si el efectivo no cubre el total, la venta se rechaza con `400`.
- Botones de **pago exacto** y de billete (C$50, 100, 200, 500, 1000) que redondean al siguiente múltiplo.
- El efectivo recibido y el vuelto se guardan en la venta, salen en la factura PDF y en el CSV de ventas.
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
- Envío por correo (PDF adjunto) o WhatsApp (enlace con token válido 7 días).

### Proveedores, compras y gastos

- Catálogo de proveedores con contacto, correo y estado.
- Compra con líneas repetibles: sube stock, actualiza costo promedio y crea el gasto.
- Gastos por categoría, con filtros por fecha y totales agregados.
- Un proveedor con compras o gastos no se borra: se desactiva.

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
| `SECRET_KEY` | — | **Obligatoria**, 32+ caracteres. También cifra las contraseñas de vendedores |
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
| `PUBLIC_BASE_URL` | `FRONTEND_URL` | Base de los enlaces de descarga de facturas compartidas |
| `GOOGLE_CLIENT_ID` | — | Google OAuth |
| `SMTP_*` | — | Códigos de verificación |
| `NICAGEST_IA_MODO` | — | `groq`, `openai` u `ollama` |
| `TEST_DATABASE_URL` | `.../nicagest_test` | Base usada por pytest |
| `LOG_RESET_LINK` | `0` | `1` registra el enlace de recuperación en el log (solo desarrollo) |

---

## Migraciones

No hay Alembic. `Backend/db/database.py` aplica DDL idempotente al arrancar:

1. `Base.metadata.create_all` crea lo que falte (incluidas las tablas nuevas).
2. `ADD COLUMN IF NOT EXISTS` para columnas nuevas.
3. Conversión `FLOAT → NUMERIC` **solo si la columna aún no es numeric**.
4. `BACKFILL` de `estado`, `costo` y `rol/activo`, y sus `SET NOT NULL`.
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
│   ├── nomina.py                   ← INSS, IR (Ley 822) y costo patronal
│   ├── tiempo.py                   ← Rangos de día por zona horaria (DST)
│   ├── auditoria.py                ← Registro de eventos
│   ├── security.py                 ← Rate limiting, subidas, saneado
│   ├── ai/ia_service.py            ← Gesti (Groq / OpenAI / Ollama)
│   ├── db/
│   │   ├── database.py             ← Engine, sesión y migraciones idempotentes
│   │   └── models.py               ← ORM: NUMERIC, estado, eventos, índices
│   ├── models/schema.py            ← Pydantic con Decimal
│   ├── services/
│   │   ├── email_service.py        ← OTP, reset y facturas con adjunto
│   │   └── credenciales.py         ← Generación y cifrado Fernet
│   └── routers/
│       ├── auth.py                 ← JWT con token_version, sesión y roles
│       ├── productos.py            ← Inventario, código de barras e importación CSV
│       ├── ventas.py               ← POS, anulación, resumen y cierre de caja
│       ├── clientes.py             ← Clientes, crédito y abonos
│       ├── reportes.py             ← Dashboard, IA, CSV, auditoría
│       ├── facturas.py             ← PDF, envío por correo y enlaces para WhatsApp
│       ├── organizacion.py         ← Navegación jerárquica y ZIP
│       ├── promociones.py
│       ├── vendedores.py           ← Cuentas hijas y credenciales
│       ├── empleados.py            ← Vendedores + personal sin cuenta
│       ├── proveedores.py
│       ├── compras.py              ← Stock y costo promedio
│       └── gastos.py
├── tests/
│   ├── conftest.py
│   ├── test_dinero.py
│   ├── test_ventas.py
│   ├── test_seguridad.py
│   ├── test_clientes.py
│   ├── test_reportes.py
│   ├── test_recuperacion.py
│   ├── test_margen.py
│   ├── test_idempotencia.py
│   ├── test_roles.py
│   ├── test_vendedores.py
│   ├── test_empleados.py
│   ├── test_nomina.py
│   ├── test_nomina_api.py
│   ├── test_compras.py
│   ├── test_importacion.py
│   └── test_envio_facturas.py
├── .github/workflows/ci.yml
└── Frontend/
    └── src/
        ├── pages/                  ← Dashboard, Ventas, Inventario, Clientes,
        │                              Promociones, Organización, Gesti, Actividad,
        │                              Rentabilidad, Vendedores, Empleados,
        │                              Proveedores, Compras, Gastos y Reset
        ├── components/ui/          ← Button, Card, Field, Feedback
        ├── components/             ← Layout, Modal, CredencialesBox, EnviarFacturaModal
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
| `POST` | `/ventas/` | Venta con `efectivo_recibido` opcional → devuelve `vuelto` |
| `GET` | `/reportes/exportar?desde&hasta` | CSV de ventas |
| `GET` | `/reportes/eventos?tipo&limite` | Auditoría |
| `GET` | `/reportes/tendencia?dias=7` | Ventas y ganancia por día (rellena días sin ventas) |
| `GET` | `/productos/codigo/{codigo}` | Búsqueda por código de barras |
| `GET` | `/productos/categorias` | Categorías con conteo |
| `POST` | `/clientes/{id}/abono` | Pago parcial de crédito |
| `POST` | `/auth/recuperar` | Solicita enlace de recuperación (respuesta genérica) |
| `POST` | `/auth/reset` | Cambia la contraseña con el token del enlace |
| `GET` | `/reportes/margenes?desde&hasta` | Ingresos, costo, ganancia y margen por producto |

### 1.3

| Método | Ruta | Uso |
| --- | --- | --- |
| `GET` | `/vendedores/` | Lista con contador `n/10` y ventas por vendedor |
| `POST` | `/vendedores/` | Crea la cuenta y devuelve sus credenciales |
| `GET` | `/vendedores/{id}/credenciales` | El admin revela la contraseña |
| `PUT` | `/vendedores/{id}` | Nombre, usuario, contraseña o activar/desactivar |
| `DELETE` | `/vendedores/{id}` | Borra o desactiva si tiene ventas |
| `GET` | `/vendedores/{id}/ventas?desde&hasta` | Totales vendidos por ese vendedor |
| `GET`/`POST`/`PUT`/`DELETE` | `/empleados/…` | Plantilla: vendedores + personal sin cuenta |
| `GET` | `/empleados/nomina/tabla` | Tramos de IR y tasas de INSS/INATEC vigentes |
| `POST` | `/empleados/nomina/simular` | Desglose de un salario sin guardar |
| `GET` | `/empleados/exportar` | CSV de la planilla con totales |
| `GET` | `/contabilidad/resumen?desde&hasta` | Ingresos, costo, gastos y utilidad |
| `GET` | `/contabilidad/serie?agrupacion=dia\|mes` | Serie para el gráfico |
| `GET` | `/contabilidad/exportar?desde&hasta` | CSV contable con totales |
| `GET`/`POST`/`PUT`/`DELETE` | `/proveedores/…` | Catálogo de proveedores |
| `GET`/`POST`/`PUT`/`DELETE` | `/gastos/…` | Gastos con filtros y agregados |
| `GET`/`POST` | `/compras/`, `/compras/{id}` | Compra con stock y costo promedio |
| `POST` | `/compras/{id}/anular` | Revierte stock y elimina el gasto |
| `GET` | `/compras/resumen/por-proveedor` | Total comprado por proveedor |
| `GET` | `/productos/plantilla-csv` | CSV de ejemplo |
| `POST` | `/productos/importar?modo&simular` | Importación con informe de errores |
| `POST` | `/facturas/{id}/enviar` | Envía por correo o devuelve enlace de WhatsApp |
| `GET` | `/facturas/{id}/enlace` | Enlace de descarga y URL `wa.me` |
| `GET` | `/facturas/descarga/{token}` | Descarga pública de la factura (sin JWT) |

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
8. Define `PUBLIC_BASE_URL` con tu dominio HTTPS: los enlaces de facturas compartidas por WhatsApp salen de ahí.
9. No cambies `SECRET_KEY` sin avisar: cambia la clave que cifra las contraseñas de los vendedores y habrá que asignarles una nueva.

## Limitaciones conocidas

- **Un admin = un negocio**. Hay roles `admin`/`vendedor`, pero no permisos granulares configurables.
- Anular una compra revierte el stock pero **no** el costo promedio histórico.
- Sin multi-sucursal ni impuestos/facturación fiscal (CAI, series).
- Sin modo offline/PWA ni impresión térmica de ticket (solo PDF A4).
- Las migraciones son idempotentes, no versionadas con rollback.
