const BASE = "http://localhost:8000";

// Función reutilizable para llamar a la API
async function apiGet(ruta) {
  const respuesta = await fetch(BASE + ruta);
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

// Formatear números en córdobas
function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

// Cargar total de productos
async function cargarProductos() {
  try {
    const data = await apiGet("/productos/");
    const total = Array.isArray(data) ? data.length : (data.total ?? "—");
    document.getElementById("m-productos").textContent = total;
  } catch (e) {
    document.getElementById("m-productos").textContent = "Error";
  }
}

// Cargar ventas del día
async function cargarVentas() {
  try {
    const data = await apiGet("/ventas/resumen-dia");
    const total = data.total_ventas ?? data.ventas_total ?? 0;
    const cantidad = data.numero_ventas ?? data.cantidad_ventas ?? 0;
    document.getElementById("m-ventas").textContent = formatearCordobas(total);

    // Rellenar tabla de últimas ventas
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

// Cargar total de clientes
async function cargarClientes() {
  try {
    const data = await apiGet("/clientes/");
    const total = Array.isArray(data) ? data.length : (data.total ?? "—");
    document.getElementById("m-clientes").textContent = total;
  } catch (e) {
    document.getElementById("m-clientes").textContent = "Error";
  }
}

// Cargar stock bajo
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

// Cargar todo al mismo tiempo
async function cargarDashboard() {
  await Promise.allSettled([
    cargarProductos(),
    cargarVentas(),
    cargarClientes(),
    cargarStockBajo(),
  ]);
}

// Ejecutar al cargar la página
cargarDashboard();
