

function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

async function cargarResumen() {
  try {
    const data = await apiGet("/clientes/");
    const clientes = Array.isArray(data) ? data : (data.clientes ?? []);

    const total = clientes.length;
    const conCredito = clientes.filter(
      (c) => (c.credito_usado ?? 0) > 0,
    ).length;
    const montoTotal = clientes.reduce(
      (acc, c) => acc + (c.credito_usado ?? 0),
      0,
    );

    document.getElementById("c-total").textContent = total;
    document.getElementById("c-credito-total").textContent = conCredito;
    document.getElementById("c-monto").textContent =
      formatearCordobas(montoTotal);
  } catch (e) {
    document.getElementById("c-total").textContent = "Error";
    document.getElementById("c-credito-total").textContent = "Error";
    document.getElementById("c-monto").textContent = "Error";
  }
}

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
        <td>${c.nombre ?? "—"}</td>
        <td>${c.telefono ?? "—"}</td>
        <td>
          <span class="badge ${(c.credito_usado ?? 0) > 0 ? "bg-warning text-dark" : "bg-success"}">
            ${formatearCordobas(c.credito_usado ?? 0)}
          </span>
        </td>
        <td>${c.ultima_compra ?? "—"}</td>
        <td>
          <button class="btn btn-sm btn-outline-info me-1" onclick="verCompras(${c.id})">Compras</button>
          <button class="btn btn-sm btn-outline-warning me-1" onclick="editarCliente(${c.id})">Editar</button>
          <button class="btn btn-sm btn-outline-danger" onclick="eliminarCliente(${c.id})">Eliminar</button>
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

async function editarCliente(id) {
  try {
    const c = await apiGet("/clientes/" + id);
    document.getElementById("ec-id").value = c.id;
    document.getElementById("ec-nombre").value = c.nombre;
    document.getElementById("ec-telefono").value = c.telefono ?? "";
    document.getElementById("ec-credito").value = c.credito_limite ?? 0;
    new bootstrap.Modal(document.getElementById("modalEditarCliente")).show();
  } catch (e) {
    alert("Error al cargar el cliente");
  }
}

async function guardarEdicionCliente() {
  const id = document.getElementById("ec-id").value;
  const nombre = document.getElementById("ec-nombre").value.trim();
  const telefono = document.getElementById("ec-telefono").value.trim();
  const credito_limite =
    parseFloat(document.getElementById("ec-credito").value) || 0;

  if (!nombre) {
    alert("El nombre es obligatorio");
    return;
  }

  try {
    await apiPut("/clientes/" + id, { nombre, telefono, credito_limite });
    bootstrap.Modal.getInstance(
      document.getElementById("modalEditarCliente"),
    ).hide();
    cargarPagina();
  } catch (e) {
    alert("Error al guardar los cambios");
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

async function eliminarCliente(id) {
  if (!confirm("¿Seguro que quieres eliminar este cliente?")) return;
  try {
    await apiDelete("/clientes/" + id);
    cargarPagina();
  } catch (e) {
    alert("Error al eliminar");
  }
}

async function verCompras(id) {
  try {
    const data = await apiGet("/clientes/" + id + "/compras");
    const tbody = document.getElementById("tabla-compras");

    if (data.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="3" class="text-center text-secondary">Sin compras</td></tr>';
    } else {
      tbody.innerHTML = data
        .map(
          (c) => `
                <tr>
                    <td>${formatearCordobas(c.total)}</td>
                    <td><span class="badge bg-secondary">${c.metodo_pago}</span></td>
                    <td>${c.fecha_hora?.slice(0, 16) ?? "—"}</td>
                </tr>
            `,
        )
        .join("");
    }

    new bootstrap.Modal(document.getElementById("modalCompras")).show();
  } catch (e) {
    alert("Error al cargar las compras");
  }
}

async function cargarPagina() {
  await Promise.allSettled([cargarResumen(), cargarClientes()]);
}

cargarPagina();
