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

// Cargar resumen de clientes
async function cargarResumen() {
  try {
    const data = await apiGet("/clientes/");
    const clientes = Array.isArray(data) ? data : (data.clientes ?? []);

    const total = clientes.length;
    const conCredito = clientes.filter(
      (c) => (c.credito ?? c.saldo_credito ?? 0) > 0,
    ).length;
    const montoTotal = clientes.reduce(
      (acc, c) => acc + (c.credito ?? c.saldo_credito ?? 0),
      0,
    );

    document.getElementById("c-total").textContent = total;
    document.getElementById("c-credito").textContent = conCredito;
    document.getElementById("c-monto").textContent =
      formatearCordobas(montoTotal);
  } catch (e) {
    document.getElementById("c-total").textContent = "Error";
    document.getElementById("c-credito").textContent = "Error";
    document.getElementById("c-monto").textContent = "Error";
  }
}

// Cargar tabla de clientes
async function cargarClientes() {
  try {
    const data = await apiGet("/clientes/");
    const clientes = Array.isArray(data) ? data : (data.clientes ?? []);
    const tbody = document.getElementById("tabla-clientes");

    if (clientes.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center text-secondary">Sin clientes registrados</td></tr>';
      return;
    }

    tbody.innerHTML = clientes
      .map(
        (c, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${c.nombre ?? c.name ?? "—"}</td>
                <td>${c.telefono ?? c.phone ?? "—"}</td>
                <td>
                    <span class="badge ${(c.credito ?? c.saldo_credito ?? 0) > 0 ? "bg-warning text-dark" : "bg-success"}">
                        ${formatearCordobas(c.credito ?? c.saldo_credito ?? 0)}
                    </span>
                </td>
                <td>${c.ultima_compra ?? c.last_purchase ?? "—"}</td>
                <td>
                    <button class="btn btn-sm btn-outline-warning me-1"
                            onclick="editarCliente(${c.id})">Editar</button>
                    <button class="btn btn-sm btn-outline-danger"
                            onclick="eliminarCliente(${c.id})">Eliminar</button>
                </td>
            </tr>
        `,
      )
      .join("");
  } catch (e) {
    document.getElementById("tabla-clientes").innerHTML =
      '<tr><td colspan="6" class="text-center text-danger">Error al cargar</td></tr>';
  }
}

// Editar cliente
function editarCliente(id) {
  // Por implementar en Semana 3
  alert("Editar cliente #" + id);
}

// Eliminar cliente
async function eliminarCliente(id) {
  if (!confirm("¿Seguro que quieres eliminar este cliente?")) return;
  try {
    await fetch(BASE + "/clientes/" + id, { method: "DELETE" });
    cargarPagina();
  } catch (e) {
    alert("Error al eliminar");
  }
}

// Ejecutar al cargar la página
async function cargarPagina() {
  await Promise.allSettled([cargarResumen(), cargarClientes()]);
}

cargarPagina();
