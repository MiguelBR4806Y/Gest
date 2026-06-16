function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

// CORRECCIÓN: Parsea la cadena de texto de forma estricta evitando desfases nativos de JS
function formatearHora12(fechaStr) {
  try {
    if (!fechaStr) return "—";

    const limpia = fechaStr.replace("T", " ");
    const partes = limpia.split(" ");
    if (partes.length < 2) return fechaStr;

    const horaPartes = partes[1].split(":");
    let horas = parseInt(horaPartes[0], 10);
    const minutos = horaPartes[1];
    const ampm = horas >= 12 ? "PM" : "AM";

    horas = horas % 12;
    horas = horas ? horas : 12; // Si es 0 se transforma en 12

    return `${horas}:${minutos} ${ampm}`;
  } catch (e) {
    console.error("Error al formatear hora:", e);
    return fechaStr;
  }
}

async function cargarProductos() {
  try {
    const data = await apiGet("/productos/");
    const total = Array.isArray(data) ? data.length : (data.total ?? "—");
    document.getElementById("m-productos").textContent = total;
  } catch (e) {
    document.getElementById("m-productos").textContent = "Error";
  }
}

async function cargarClientes() {
  try {
    const data = await apiGet("/clientes/");
    const total = Array.isArray(data) ? data.length : (data.total ?? "—");
    document.getElementById("m-clientes").textContent = total;
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

    if (items.length === 0) {
      lista.innerHTML =
        '<li class="list-group-item text-secondary">Sin alertas de stock</li>';
      return;
    }

    lista.innerHTML = items
      .slice(0, 5)
      .map(
        (p) => `
      <li class="list-group-item d-flex justify-content-between align-items-center">
        ${p.nombre ?? p.name}
        <span class="badge bg-danger">${p.stock ?? p.cantidad ?? 0} uds.</span>
      </li>
    `,
      )
      .join("");
  } catch (e) {
    document.getElementById("m-alertas").textContent = "Error";
  }
}

// CORRECCIÓN: Unificación de endpoints válidos del backend para las tarjetas, la tabla e IA
async function cargarDatosVentasYReportes() {
  try {
    // 1. Cargamos las tarjetas informativas del día
    const dashData = await apiGet("/reportes/dashboard");

    if (dashData && dashData.resumen_dia) {
      const totalHoy = dashData.resumen_dia.total_ventas ?? 0;
      document.getElementById("m-ventas").textContent =
        formatearCordobas(totalHoy);
    }

    // 2. Cargamos el listado detallado de hoy para la tabla y la IA
    const ventasData = await apiGet("/reportes/ventas");
    const ventas = ventasData.ventas ?? [];
    const tbody = document.getElementById("tabla-ventas");

    if (tbody) {
      if (ventas.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="3" class="text-center text-secondary">Sin ventas hoy</td></tr>';
      } else {
        tbody.innerHTML = ventas
          .slice(0, 5)
          .map(
            (v) => `
          <tr>
            <td>${v.cliente_nombre ?? v.cliente ?? "Consumidor Final"}</td>
            <td>${formatearHora12(v.fecha_hora)}</td>
            <td>${formatearCordobas(v.total ?? 0)}</td>
          </tr>
        `,
          )
          .join("");
      }
    }

    // 3. Renderizado del análisis de Inteligencia Artificial (Ollama / OpenAI)
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

async function cargarDashboard() {
  await Promise.allSettled([
    cargarProductos(),
    cargarClientes(),
    cargarStockBajo(),
    cargarDatosVentasYReportes(),
  ]);
}

// Inicialización de la pantalla al cargar el script
cargarDashboard();
