const BASE = "http://127.0.0.1:8000";

async function apiGet(ruta) {
  const respuesta = await fetch(BASE + ruta);
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

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
    const total = Array.isArray(data) ? data.length : (data.total ?? "—");
    document.getElementById("m-productos").textContent = total;
  } catch (e) {
    document.getElementById("m-productos").textContent = "Error";
  }
}

async function cargarVentas() {
  try {
    const data = await apiGet("/ventas/resumen-dia");
    const total = data.total_ventas ?? data.ventas_total ?? 0;
    document.getElementById("m-ventas").textContent = formatearCordobas(total);

    const ventas = data.ultimas_ventas ?? data.ventas ?? [];
    const tbody = document.getElementById("tabla-ventas");

    if (ventas.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="3" class="text-center text-secondary">Sin ventas hoy</td></tr>';
      return;
    }

    tbody.innerHTML = ventas
      .slice(0, 5)
      .map(
        (v) => `
      <tr>
        <td>${v.cliente_nombre ?? v.cliente ?? "Cliente"}</td>
        <td>${v.hora ?? v.fecha_hora?.slice(11, 16) ?? "—"}</td>
        <td>${formatearCordobas(v.total ?? v.monto ?? 0)}</td>
      </tr>
    `,
      )
      .join("");
  } catch (e) {
    document.getElementById("m-ventas").textContent = "Error";
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

async function cargarAnalisisIA() {
  try {
    const data = await apiGet("/reportes/ventas");
    if (data.analisis_ia) {
      document.getElementById("ia-texto").textContent = data.analisis_ia;
      document.getElementById("ia-seccion").style.display = "";
    }
  } catch (e) {
    // Si falla la IA no rompemos el dashboard
  }
}

async function cargarDashboard() {
  await Promise.allSettled([
    cargarProductos(),
    cargarVentas(),
    cargarClientes(),
    cargarStockBajo(),
    cargarAnalisisIA(),
  ]);
}

cargarDashboard();
