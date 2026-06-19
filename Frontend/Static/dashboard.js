// ── Historial del chat (localStorage, 30 días) ──
const CHAT_KEY = "bravosgest_chat_historial";
const CHAT_DIAS = 30;

function guardarMensajeLocal(tipo, texto) {
  const historial = cargarMensajesLocales();
  historial.push({ tipo, texto, fecha: Date.now() });
  localStorage.setItem(CHAT_KEY, JSON.stringify(historial));
}

function cargarMensajesLocales() {
  try {
    const raw = localStorage.getItem(CHAT_KEY);
    if (!raw) return [];
    const todos = JSON.parse(raw);
    const limite = Date.now() - CHAT_DIAS * 24 * 60 * 60 * 1000;
    const recientes = todos.filter((m) => m.fecha > limite);
    if (recientes.length !== todos.length) {
      localStorage.setItem(CHAT_KEY, JSON.stringify(recientes));
    }
    return recientes;
  } catch (e) {
    return [];
  }
}

function renderizarHistorialGuardado() {
  const mensajes = cargarMensajesLocales();
  if (mensajes.length === 0) return;
  const historial = document.getElementById("chat-historial");
  historial.style.display = "";
  mensajes.forEach((m) => renderizarBurbuja(m.tipo, m.texto));
}

function renderizarBurbuja(tipo, texto) {
  const historial = document.getElementById("chat-historial");
  const esMio = tipo === "usuario";
  const burbuja = document.createElement("div");
  burbuja.className = `d-flex gap-2 align-items-start mb-2 ${esMio ? "flex-row-reverse" : ""}`;
  const colorClase = esMio
    ? "bg-success text-white"
    : "bg-secondary text-white";
  burbuja.innerHTML = `
    <span style="font-size:1.1rem;flex-shrink:0;">${esMio ? "👤" : "🤖"}</span>
    <div class="p-2 rounded ${colorClase}" style="max-width:80%;font-size:0.92rem;">
      ${texto.replace(/\n/g, "<br>")}
    </div>
  `;
  historial.appendChild(burbuja);
  historial.scrollTop = historial.scrollHeight;
}

function agregarMensajeChat(tipo, texto) {
  document.getElementById("chat-historial").style.display = "";
  renderizarBurbuja(tipo, texto);
  guardarMensajeLocal(tipo, texto);
}

function limpiarChat() {
  localStorage.removeItem(CHAT_KEY);
  const historial = document.getElementById("chat-historial");
  historial.innerHTML = "";
  historial.style.display = "none";
}

async function enviarPreguntaIA() {
  const input = document.getElementById("chat-pregunta");
  const btnEnviar = document.getElementById("chat-btn");
  const historial = document.getElementById("chat-historial");
  const pregunta = input.value.trim();
  if (!pregunta) return;

  historial.style.display = "";
  agregarMensajeChat("usuario", pregunta);
  input.value = "";
  btnEnviar.disabled = true;
  btnEnviar.textContent = "Pensando...";

  const typing = document.createElement("div");
  typing.id = "chat-typing";
  typing.className = "d-flex gap-2 align-items-center mb-2 text-secondary";
  typing.innerHTML = `<span>🤖</span><small>Escribiendo...</small>`;
  historial.appendChild(typing);
  historial.scrollTop = historial.scrollHeight;

  try {
    const data = await apiPost("/reportes/chat", { pregunta });
    document.getElementById("chat-typing")?.remove();
    agregarMensajeChat("ia", data.respuesta);
  } catch (e) {
    document.getElementById("chat-typing")?.remove();
    agregarMensajeChat("ia", "❌ Error al consultar la IA. Intenta de nuevo.");
  } finally {
    btnEnviar.disabled = false;
    btnEnviar.textContent = "Preguntar";
    input.focus();
  }
}

// ── Reportes predictivos ──
async function cargarPredictivos() {
  const seccion = document.getElementById("predictivos-seccion");
  if (!seccion) return;

  try {
    const data = await apiGet("/reportes/predictivos");

    const tarjetas = [
      {
        id: "pred-reabastecimiento",
        icono: "📦",
        titulo: "Productos a reabastecer",
        valor: data.reabastecimiento,
      },
      {
        id: "pred-mejor-dia",
        icono: "📅",
        titulo: "Mejor día de la semana",
        valor: data.mejor_dia,
      },
      {
        id: "pred-proyeccion",
        icono: "📈",
        titulo: "Proyección próximos 7 días",
        valor: data.proyeccion,
      },
    ];

    seccion.innerHTML = tarjetas
      .map(
        (t) => `
      <div class="col-12 col-md-4">
        <div class="card h-100 p-3 border-0" style="background:rgba(255,255,255,0.05);">
          <div class="card-body">
            <p class="text-secondary mb-1" style="font-size:0.8rem;">
              ${t.icono} ${t.titulo}
            </p>
            <p class="mb-0" style="font-size:0.92rem;">${t.valor}</p>
          </div>
        </div>
      </div>
    `,
      )
      .join("");

    seccion.closest(".row")?.previousElementSibling?.remove(); // quitar spinner si existe
  } catch (e) {
    console.error("Error al cargar predictivos:", e);
  }
}

// ── Métricas ──
function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

async function cargarProductos() {
  try {
    const data = await apiGet("/productos/");
    document.getElementById("m-productos").textContent = Array.isArray(data)
      ? data.length
      : (data.total ?? "—");
  } catch (e) {
    document.getElementById("m-productos").textContent = "Error";
  }
}

async function cargarClientes() {
  try {
    const data = await apiGet("/clientes/");
    document.getElementById("m-clientes").textContent = Array.isArray(data)
      ? data.length
      : (data.total ?? "—");
  } catch (e) {
    document.getElementById("m-clientes").textContent = "Error";
  }
}

async function cargarStockBajo() {
  try {
    const data = await apiGet("/productos/stock-bajo");
    const items = Array.isArray(data) ? data : (data.productos ?? []);
    document.getElementById("m-alertas").textContent = items.length;

    const lista = document.getElementById("lista-stock");
    if (!lista) return;

    lista.innerHTML =
      items.length === 0
        ? '<li class="list-group-item text-secondary">Sin alertas de stock</li>'
        : items
            .slice(0, 5)
            .map(
              (p) => `
        <li class="list-group-item d-flex justify-content-between align-items-center">
          ${p.nombre ?? p.name}
          <span class="badge bg-danger">${p.stock ?? 0} uds.</span>
        </li>
      `,
            )
            .join("");
  } catch (e) {
    document.getElementById("m-alertas").textContent = "Error";
  }
}

async function cargarDatosVentasYReportes() {
  try {
    const dashData = await apiGet("/reportes/dashboard");
    if (dashData?.resumen_dia) {
      document.getElementById("m-ventas").textContent = formatearCordobas(
        dashData.resumen_dia.total_ventas ?? 0,
      );
    }

    const ventasData = await apiGet("/reportes/ventas");
    const ventas = ventasData.ventas ?? [];
    const tbody = document.getElementById("tabla-ventas");

    if (tbody) {
      tbody.innerHTML =
        ventas.length === 0
          ? '<tr><td colspan="3" class="text-center text-secondary">Sin ventas hoy</td></tr>'
          : ventas
              .slice(0, 5)
              .map(
                (v) => `
          <tr>
            <td>${v.cliente_nombre ?? "Consumidor Final"}</td>
            <td>${formatearHora12(v.fecha_hora)}</td>
            <td>${formatearCordobas(v.total ?? 0)}</td>
          </tr>
        `,
              )
              .join("");
    }

    if (ventasData.analisis_ia) {
      const textoIA = document.getElementById("ia-texto");
      const seccionIA = document.getElementById("ia-seccion");
      if (textoIA) textoIA.textContent = ventasData.analisis_ia;
      if (seccionIA) seccionIA.style.display = "";
    }
  } catch (e) {
    console.error("Error al cargar los reportes de ventas:", e);
    document.getElementById("m-ventas").textContent = "Error";
  }
}

// ── Inicialización ──
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-pregunta");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        enviarPreguntaIA();
      }
    });
  }
  renderizarHistorialGuardado();
});

async function cargarDashboard() {
  cargarPredictivos();
  await Promise.allSettled([
    cargarProductos(),
    cargarClientes(),
    cargarStockBajo(),
    cargarDatosVentasYReportes(),
    cargarPredictivos(),
  ]);
}

cargarDashboard();

// ── Reportes predictivos ──
async function cargarPredictivos() {
  try {
    const data = await apiGet("/reportes/predictivos");
    renderizarReabastecimiento(data.reabastecer ?? []);
    renderizarDiasSemana(data.dias_semana ?? []);
    renderizarProyeccion(data.proyeccion ?? {});
    document.getElementById("seccion-predictivos").style.display = "";
  } catch (e) {
    console.error("Error al cargar reportes predictivos:", e);
  }
}

function renderizarReabastecimiento(items) {
  const el = document.getElementById("pred-reabastecer");
  if (items.length === 0) {
    el.innerHTML =
      '<p class="text-secondary mb-0">Sin productos urgentes por ahora.</p>';
    return;
  }
  el.innerHTML = items
    .map((p) => {
      const urgente = p.dias_restantes <= 3;
      const badge = urgente ? "bg-danger" : "bg-warning text-dark";
      return `
      <div class="d-flex justify-content-between align-items-center mb-2">
        <span>${p.nombre}</span>
        <div class="text-end">
          <span class="badge ${badge}">${p.dias_restantes} días</span>
          <small class="text-secondary d-block">${p.stock_actual} uds · ${p.unidades_por_dia}/día</small>
        </div>
      </div>`;
    })
    .join("");
}

function renderizarDiasSemana(dias) {
  const el = document.getElementById("pred-dias");
  if (dias.length === 0) {
    el.innerHTML =
      '<p class="text-secondary mb-0">Sin datos suficientes aún.</p>';
    return;
  }
  const maxTotal = Math.max(...dias.map((d) => d.total_ventas));
  el.innerHTML = dias
    .map((d, i) => {
      const pct =
        maxTotal > 0 ? Math.round((d.total_ventas / maxTotal) * 100) : 0;
      const color =
        i === 0 ? "bg-success" : i === 1 ? "bg-info" : "bg-secondary";
      return `
      <div class="mb-2">
        <div class="d-flex justify-content-between mb-1">
          <small>${d.dia}</small>
          <small class="text-secondary">C$ ${Number(d.total_ventas).toLocaleString("es-NI", { minimumFractionDigits: 2 })}</small>
        </div>
        <div class="progress" style="height:8px;">
          <div class="progress-bar ${color}" style="width:${pct}%"></div>
        </div>
      </div>`;
    })
    .join("");
}

function renderizarProyeccion(proy) {
  const el = document.getElementById("pred-proyeccion");
  if (!proy.promedio_diario) {
    el.innerHTML =
      '<p class="text-secondary mb-0">Sin datos suficientes aún.</p>';
    return;
  }
  const fmt = (n) =>
    "C$ " + Number(n).toLocaleString("es-NI", { minimumFractionDigits: 2 });
  el.innerHTML = `
    <div class="text-center mb-3">
      <p class="text-secondary mb-1">Proyección próximos 7 días</p>
      <h3 class="text-success mb-0">${fmt(proy.proyeccion_7_dias)}</h3>
    </div>
    <div class="d-flex justify-content-between">
      <div class="text-center">
        <small class="text-secondary d-block">Promedio diario</small>
        <span class="fw-bold">${fmt(proy.promedio_diario)}</span>
      </div>
      <div class="text-center">
        <small class="text-secondary d-block">Días con ventas (30d)</small>
        <span class="fw-bold">${proy.dias_con_ventas_30d}</span>
      </div>
    </div>`;
}
