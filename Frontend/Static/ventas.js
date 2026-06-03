const BASE = "http://localhost:8000";

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

// Cargar resumen del día
async function cargarResumen() {
  try {
    const data = await apiGet("/ventas/resumen-dia");
    const total = data.total_ventas ?? data.ventas_total ?? 0;
    const cantidad = data.numero_ventas ?? data.cantidad_ventas ?? 0;
    const promedio = cantidad > 0 ? total / cantidad : 0;

    document.getElementById("v-total").textContent = formatearCordobas(total);
    document.getElementById("v-cantidad").textContent = cantidad;
    document.getElementById("v-promedio").textContent =
      formatearCordobas(promedio);
  } catch (e) {
    document.getElementById("v-total").textContent = "Error";
    document.getElementById("v-cantidad").textContent = "Error";
    document.getElementById("v-promedio").textContent = "Error";
  }
}

// Cargar tabla de ventas
async function cargarVentas() {
  try {
    const data = await apiGet("/ventas/resumen-dia");
    const ventas = data.ultimas_ventas ?? data.ventas ?? [];
    const tbody = document.getElementById("tabla-ventas");

    if (ventas.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center text-secondary">Sin ventas hoy</td></tr>';
      return;
    }

    tbody.innerHTML = ventas
      .map(
        (v, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${v.cliente_nombre ?? v.cliente ?? "Cliente"}</td>
                <td>${v.productos ?? "—"}</td>
                <td>${v.hora ?? v.fecha_hora?.slice(11, 16) ?? "—"}</td>
                <td>${formatearCordobas(v.total ?? v.monto ?? 0)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-info" 
                            onclick="verVenta(${v.id})">Ver</button>
                </td>
            </tr>
        `,
      )
      .join("");
  } catch (e) {
    document.getElementById("tabla-ventas").innerHTML =
      '<tr><td colspan="6" class="text-center text-danger">Error al cargar</td></tr>';
  }
}

// Ver detalle de una venta
function verVenta(id) {
  // Por implementar en Semana 3
  alert("Ver venta #" + id);
}

// Ejecutar al cargar la página
async function cargarPagina() {
  await Promise.allSettled([cargarResumen(), cargarVentas()]);
}

cargarPagina();
