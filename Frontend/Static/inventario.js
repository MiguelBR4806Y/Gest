const BASE = "http://localhost:8000";

async function apiGet(ruta) {
  const respuesta = await fetch(BASE + ruta);
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
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

async function apiPut(ruta, datos) {
  const respuesta = await fetch(BASE + ruta, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

async function cargarInventario() {
  try {
    const data = await apiGet("/productos/");
    const productos = Array.isArray(data) ? data : (data.productos ?? []);
    const tbody = document.getElementById("tabla-inventario");

    if (productos.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center text-secondary">Sin productos registrados</td></tr>';
      return;
    }

    tbody.innerHTML = productos
      .map(
        (p, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${p.nombre ?? p.name}</td>
        <td>${p.categoria ?? "—"}</td>
        <td>
          <span class="badge ${p.stock <= 5 ? "bg-danger" : "bg-success"}">
            ${p.stock ?? 0}
          </span>
        </td>
        <td>C$ ${p.precio ?? 0}</td>
        <td>
          <button class="btn btn-sm btn-outline-warning me-1" onclick="editarProducto(${p.id})">Editar</button>
          <button class="btn btn-sm btn-outline-danger" onclick="eliminarProducto(${p.id})">Eliminar</button>
        </td>
      </tr>
    `,
      )
      .join("");
  } catch (e) {
    document.getElementById("tabla-inventario").innerHTML =
      '<tr><td colspan="6" class="text-center text-danger">Error al cargar</td></tr>';
  }
}

async function editarProducto(id) {
  try {
    const p = await apiGet("/productos/" + id);
    document.getElementById("ep-id").value = p.id;
    document.getElementById("ep-nombre").value = p.nombre;
    document.getElementById("ep-categoria").value = p.categoria ?? "";
    document.getElementById("ep-stock").value = p.stock;
    document.getElementById("ep-precio").value = p.precio;
    new bootstrap.Modal(document.getElementById("modalEditarProducto")).show();
  } catch (e) {
    alert("Error al cargar el producto");
  }
}

async function guardarEdicionProducto() {
  const id = document.getElementById("ep-id").value;
  const nombre = document.getElementById("ep-nombre").value.trim();
  const categoria = document.getElementById("ep-categoria").value.trim();
  const stock = parseInt(document.getElementById("ep-stock").value) || 0;
  const precio = parseFloat(document.getElementById("ep-precio").value) || 0;

  if (!nombre) {
    alert("El nombre es obligatorio");
    return;
  }

  try {
    await apiPut("/productos/" + id, { nombre, categoria, stock, precio });
    bootstrap.Modal.getInstance(
      document.getElementById("modalEditarProducto"),
    ).hide();
    cargarInventario();
  } catch (e) {
    alert("Error al guardar los cambios");
  }
}

async function eliminarProducto(id) {
  if (!confirm("¿Seguro que quieres eliminar este producto?")) return;
  try {
    await fetch(BASE + "/productos/" + id, { method: "DELETE" });
    cargarInventario();
  } catch (e) {
    alert("Error al eliminar");
  }
}

async function agregarProducto() {
  const nombre = document.getElementById("p-nombre").value.trim();
  const categoria = document.getElementById("p-categoria").value.trim();
  const stock = parseInt(document.getElementById("p-stock").value) || 0;
  const precio = parseFloat(document.getElementById("p-precio").value) || 0;

  if (!nombre) {
    alert("El nombre es obligatorio");
    return;
  }

  try {
    await apiPost("/productos/", { nombre, categoria, stock, precio });
    bootstrap.Modal.getInstance(
      document.getElementById("modalAgregarProducto"),
    ).hide();
    document.getElementById("p-nombre").value = "";
    document.getElementById("p-categoria").value = "";
    document.getElementById("p-stock").value = "0";
    document.getElementById("p-precio").value = "0";
    cargarInventario();
  } catch (e) {
    alert("Error al guardar el producto");
  }
}

cargarInventario();
