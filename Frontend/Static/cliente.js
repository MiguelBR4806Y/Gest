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

async function apiPost(ruta, datos) {
  const respuesta = await fetch(BASE + ruta, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
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

async function agregarCliente() {
  const nombre = document.getElementById("c-nombre").value.trim();
  const telefono = document.getElementById("c-telefono").value.trim();
  const credito_limite =
    parseFloat(document.getElementById("c-credito").value) || 0;

  if (!nombre) {
    alert("El nombre es obligatorio");
    return;
  }

  try {
    await apiPost("/clientes/", { nombre, telefono, credito_limite });
    bootstrap.Modal.getInstance(
      document.getElementById("modalAgregarCliente"),
    ).hide();
    document.getElementById("c-nombre").value = "";
    document.getElementById("c-telefono").value = "";
    document.getElementById("c-credito").value = "0";
    cargarPagina();
  } catch (e) {
    alert("Error al guardar el cliente");
  }
}

// Ejecutar al cargar la página
async function cargarPagina() {
  await Promise.allSettled([cargarResumen(), cargarClientes()]);
}

cargarPagina();
