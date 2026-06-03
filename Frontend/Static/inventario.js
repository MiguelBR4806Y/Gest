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

// Cargar tabla de productos
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
                    <button class="btn btn-sm btn-outline-warning me-1" 
                            onclick="editarProducto(${p.id})">Editar</button>
                    <button class="btn btn-sm btn-outline-danger" 
                            onclick="eliminarProducto(${p.id})">Eliminar</button>
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

// Editar producto
function editarProducto(id) {
  // Por implementar en Semana 3
  alert("Editar producto #" + id);
}

// Eliminar producto
async function eliminarProducto(id) {
  if (!confirm("¿Seguro que quieres eliminar este producto?")) return;
  try {
    await fetch(BASE + "/productos/" + id, { method: "DELETE" });
    cargarInventario(); // Recargar tabla
  } catch (e) {
    alert("Error al eliminar");
  }
}

// Ejecutar al cargar la página
cargarInventario();
