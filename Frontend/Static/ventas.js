

function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function getFecha() {
  const input = document.getElementById("filtro-fecha");
  if (!input || !input.value) {
    // Por defecto hoy
    return new Date().toISOString().slice(0, 10);
  }
  return input.value;
}

async function cargarResumen() {
  try {
    const fecha = getFecha();
    const data = await apiGet("/ventas/resumen-dia?fecha=" + fecha);
    const total = data.total_ventas ?? 0;
    const cantidad = data.numero_ventas ?? 0;
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

async function cargarVentas() {
  try {
    const fecha = getFecha();
    const data = await apiGet("/ventas/resumen-dia?fecha=" + fecha);
    const ventas = data.ultimas_ventas ?? [];
    const tbody = document.getElementById("tabla-ventas");

    if (ventas.length === 0) {
      tbody.innerHTML =
        '<tr><td colspan="6" class="text-center text-secondary">Sin ventas para esta fecha</td></tr>';
      return;
    }

    tbody.innerHTML = ventas
      .map(
        (v, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${v.cliente_nombre ?? "Cliente"}</td>
        <td>${v.productos ?? "—"}</td>
        <td>${v.fecha_hora?.slice(11, 16) ?? "—"}</td>
        <td>${formatearCordobas(v.total ?? 0)}</td>
        <td>
          <button class="btn btn-sm btn-outline-success" onclick="verVenta(${v.id})">
            Factura
          </button>
        </td>
      </tr>
    `,
      )
      .join("");
  } 
  catch (e) {
    document.getElementById("tabla-ventas").innerHTML =
      '<tr><td colspan="6" class="text-center text-danger">Error al cargar</td></tr>';
  }
}

// CAMBIO: ahora abre el PDF de la factura en nueva pestaña
function verVenta(id) {
  const usuario = sessionStorage.getItem("usuario") ?? "root";
  window.open(
    "http://127.0.0.1:8000/facturas/" + id + "?usuario=" + usuario,
    "_blank",
  );
}

let itemsVenta = [];

async function cargarSelectores() {
  const clientes = await apiGet("/clientes/");
  const selectCliente = document.getElementById("v-cliente");
  selectCliente.innerHTML = '<option value="">Sin cliente</option>';
  clientes.forEach((c) => {
    selectCliente.innerHTML += `<option value="${c.id}">${c.nombre}</option>`;
  });

  const productos = await apiGet("/productos/");
  const selectProducto = document.getElementById("v-producto");
  selectProducto.innerHTML = '<option value="">Seleccionar...</option>';
  productos.forEach((p) => {
    selectProducto.innerHTML += `<option value="${p.id}" data-precio="${p.precio}">${p.nombre} (C$ ${p.precio})</option>`;
  });

  itemsVenta = [];
  actualizarTablaItems();
}

function agregarItem() {
  const select = document.getElementById("v-producto");
  const id = parseInt(select.value);
  const nombre = select.options[select.selectedIndex].text;
  const precio = parseFloat(
    select.options[select.selectedIndex].dataset.precio,
  );
  const cantidad = parseInt(document.getElementById("v-cantidad").value) || 1;

  if (!id) {
    alert("Selecciona un producto");
    return;
  }

  const existente = itemsVenta.find((i) => i.producto_id === id);
  if (existente) {
    existente.cantidad += cantidad;
  } else {
    itemsVenta.push({
      producto_id: id,
      nombre,
      cantidad,
      precio_unitario: precio,
    });
  }

  actualizarTablaItems();
}

function actualizarTablaItems() {
  const tbody = document.getElementById("items-body");

  if (itemsVenta.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="5" class="text-center text-secondary">Sin productos agregados</td></tr>';
    document.getElementById("modal-total").textContent = "C$ 0.00";
    return;
  }

  tbody.innerHTML = itemsVenta
    .map(
      (item, i) => `
    <tr>
      <td>${item.nombre}</td>
      <td>${item.cantidad}</td>
      <td>C$ ${item.precio_unitario}</td>
      <td>C$ ${(item.cantidad * item.precio_unitario).toFixed(2)}</td>
      <td><button class="btn btn-sm btn-outline-danger" onclick="quitarItem(${i})">✕</button></td>
    </tr>
  `,
    )
    .join("");

  const total = itemsVenta.reduce(
    (acc, i) => acc + i.cantidad * i.precio_unitario,
    0,
  );
  document.getElementById("modal-total").textContent = formatearCordobas(total);
}

function quitarItem(index) {
  itemsVenta.splice(index, 1);
  actualizarTablaItems();
}

async function registrarVenta() {
  if (itemsVenta.length === 0) {
    alert("Agrega al menos un producto");
    return;
  }

  const cliente_id = document.getElementById("v-cliente").value || null;

  try {
    await apiPost("/ventas/", {
      cliente_id: cliente_id ? parseInt(cliente_id) : null,
      items: itemsVenta.map((i) => ({
        producto_id: i.producto_id,
        cantidad: i.cantidad,
        precio_unitario: i.precio_unitario,
      })),
    });
    bootstrap.Modal.getInstance(
      document.getElementById("modalNuevaVenta"),
    ).hide();
    itemsVenta = [];
    cargarPagina();
  } catch (e) {
    alert("Error al registrar la venta");
  }
}

async function cargarPagina() {
  await Promise.allSettled([cargarResumen(), cargarVentas()]);
}

cargarPagina();
