// Variable global para almacenar el inventario completo temporalmente para control de stock
let productosInventarioLocal = [];
let itemsVenta = [];

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
    document.getElementById("v-transacciones").textContent = cantidad; // <-- CAMBIADO AQUÍ
    document.getElementById("v-promedio").textContent =
      formatearCordobas(promedio);
  } catch (e) {
    document.getElementById("v-total").textContent = "Error";
    document.getElementById("v-transacciones").textContent = "Error"; // <-- CAMBIADO AQUÍ
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
        '<tr><td colspan="7" class="text-center text-secondary">Sin ventas para esta fecha</td></tr>';
      return;
    }

    tbody.innerHTML = ventas
      .map((v, i) => {
        // --- CONTROL Y FORMATEO DE PRODUCTOS ---
        let productosStr = "—";

        if (v.productos) {
          if (Array.isArray(v.productos)) {
            // Si el backend manda un array de objetos: [{"nombre": "Producto A", "cantidad": 2}]
            productosStr = v.productos
              .map((p) => `${p.nombre ?? p.producto_nombre} (x${p.cantidad})`)
              .join(", ");
          } else if (typeof v.productos === "string") {
            // Si ya viene como texto desde el backend
            productosStr = v.productos;
          }
        } else if (v.items && Array.isArray(v.items)) {
          // Por si tu backend lo devuelve dentro de la propiedad "items"
          productosStr = v.items
            .map(
              (item) =>
                `${item.producto_nombre ?? "Producto"} (x${item.cantidad})`,
            )
            .join(", ");
        }

        return `
      <tr>
        <td>${i + 1}</td>
        <td>${v.cliente_nombre ?? "Cliente General"}</td>
        <td><small>${productosStr}</small></td>
        <td>${formatearHora12(v.fecha_hora)}</td>
        <td class="fw-bold text-success">${formatearCordobas(v.total ?? 0)}</td>
        <td><span class="badge bg-secondary">${v.metodo_pago ?? "—"}</span></td>
        <td>
          <button class="btn btn-sm btn-outline-success" onclick="verVenta(${v.id})">
            Factura
          </button>
        </td>
      </tr>
    `;
      })
      .join("");
  } catch (e) {
    document.getElementById("tabla-ventas").innerHTML =
      '<tr><td colspan="7" class="text-center text-danger">Error al cargar transacciones</td></tr>';
  }
}

function verVenta(id) {
  const usuario = sessionStorage.getItem("usuario") ?? "root";
  window.open(
    "http://127.0.0.1:8000/facturas/" + id + "?usuario=" + usuario,
    "_blank",
  );
}

async function cargarSelectores() {
  try {
    // 1. Cargar Clientes
    const clientes = await apiGet("/clientes/");
    const selectCliente = document.getElementById("v-cliente");
    selectCliente.innerHTML = '<option value="">Sin cliente</option>';
    clientes.forEach((c) => {
      selectCliente.innerHTML += `<option value="${c.id}">${c.nombre}</option>`;
    });

    // 2. Cargar Productos y mapear su stock para UX preventivo
    const dataProductos = await apiGet("/productos/");
    productosInventarioLocal = Array.isArray(dataProductos)
      ? dataProductos
      : (dataProductos.productos ?? []);

    const selectProducto = document.getElementById("v-producto");
    selectProducto.innerHTML = '<option value="">Seleccionar...</option>';
    productosInventarioLocal.forEach((p) => {
      const stockActual = p.stock ?? 0;
      // Deshabilitar visualmente opciones agotadas
      const statusText =
        stockActual <= 0
          ? "(Agotado)"
          : `(C$ ${p.precio} · Stock: ${stockActual})`;
      selectProducto.innerHTML += `<option value="${p.id}" data-precio="${p.precio}" data-stock="${stockActual}" ${stockActual <= 0 ? "disabled" : ""}>${p.nombre} ${statusText}</option>`;
    });

    itemsVenta = [];
    actualizarTablaItems();
  } catch (e) {
    console.error("Error al inicializar selectores del modal:", e);
  }
}

function agregarItem() {
  const select = document.getElementById("v-producto");
  const id = parseInt(select.value);

  if (!id) {
    alert("Selecciona un producto válido");
    return;
  }

  const optionSeleccionada = select.options[select.selectedIndex];
  const nombreCompleto = optionSeleccionada.text;
  // Limpiamos el texto para que en la tabla no salga el texto del stock decorativo
  const nombreLimpio = nombreCompleto.split(" (")[0];
  const precio = parseFloat(optionSeleccionada.dataset.precio);
  const stockDisponible = parseInt(optionSeleccionada.dataset.stock) || 0;
  const cantidad = parseInt(document.getElementById("v-cantidad").value) || 1;

  if (cantidad <= 0) {
    alert("La cantidad debe ser mayor a cero.");
    return;
  }

  const existente = itemsVenta.find((i) => i.producto_id === id);
  const cantidadTotalIntento = existente
    ? existente.cantidad + cantidad
    : cantidad;

  // Control estricto de UX: No permitir añadir más de lo existente en bodega
  if (cantidadTotalIntento > stockDisponible) {
    alert(
      `Operación denegada: El stock disponible para este producto es de ${stockDisponible} unidades.`,
    );
    return;
  }

  if (existente) {
    existente.cantidad = cantidadTotalIntento;
  } else {
    itemsVenta.push({
      producto_id: id,
      nombre: nombreLimpio,
      cantidad: cantidad,
      precio_unitario: precio,
    });
  }

  // Resetea indicador de cantidad del formulario
  document.getElementById("v-cantidad").value = "1";
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
      <td><strong>${item.nombre}</strong></td>
      <td><span class="badge bg-dark px-2 py-1">${item.cantidad}</span></td>
      <td>C$ ${item.precio_unitario.toFixed(2)}</td>
      <td class="fw-bold">C$ ${(item.cantidad * item.precio_unitario).toFixed(2)}</td>
      <td><button class="btn btn-sm btn-outline-danger py-0 px-1" onclick="quitarItem(${i})">✕</button></td>
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
    alert("Agrega al menos un producto antes de facturar.");
    return;
  }

  const cliente_id = document.getElementById("v-cliente").value || null;
  const metodo_pago = document.getElementById("v-metodo-pago").value;

  if (metodo_pago === "credito" && !cliente_id) {
    alert(
      "Para pagar con crédito debes seleccionar obligatoriamente un cliente.",
    );
    return;
  }

  // --- PROTECCIÓN UX: Deshabilitar el botón para evitar duplicados ---
  const btnRegistrar = document.querySelector("#modalNuevaVenta .btn-success");
  if (btnRegistrar) {
    btnRegistrar.disabled = true;
    btnRegistrar.textContent = "Procesando...";
  }

  try {
    await apiPost("/ventas/", {
      cliente_id: cliente_id ? parseInt(cliente_id) : null,
      metodo_pago: metodo_pago,
      items: itemsVenta.map((i) => ({
        producto_id: i.producto_id,
        cantidad: i.cantidad,
        precio_unitario: i.precio_unitario,
      })),
    });

    const modalElement = document.getElementById("modalNuevaVenta");
    const modalInstance = bootstrap.Modal.getInstance(modalElement);
    if (modalInstance) modalInstance.hide();

    itemsVenta = [];
    await cargarPagina();
    alert("Venta registrada con éxito.");
  } catch (e) {
    alert(
      "Error al registrar la venta. Verifique la disponibilidad en el backend.",
    );
  } finally {
    // --- RESTAURAR BOTÓN ---
    if (btnRegistrar) {
      btnRegistrar.disabled = false;
      btnRegistrar.textContent = "Registrar venta";
    }
  }
}

function establecerFechaDeHoy() {
  const input = document.getElementById("filtro-fecha");
  if (input && !input.value) {
    // Inserta la fecha actual en formato YYYY-MM-DD
    input.value = new Date().toISOString().slice(0, 10);
  }
}

async function cargarPagina() {
  establecerFechaDeHoy(); // <-- Añadido aquí
  await Promise.allSettled([cargarResumen(), cargarVentas()]);
}

// Inicialización global al cargar script
cargarPagina();
