function formatearCordobas(numero) {
  return (
    "C$ " +
    Number(numero).toLocaleString("es-NI", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
  );
}

function formatearHora12(fechaHoraStr) {
  if (!fechaHoraStr) return "—";

  let horas, minutos;

  // CASO 1: Si solo viene la hora armada (ej: "22:39")
  if (fechaHoraStr.length === 5 && fechaHoraStr.includes(":")) {
    [horas, minutos] = fechaHoraStr.split(":");
    horas = parseInt(horas, 10);
  }
  // CASO 2: Si viene un formato de fecha completo (ej: "2026-06-11 22:39:00" o con "T")
  else {
    // Reemplazamos la 'T' por un espacio por consistencia
    const limpio = fechaHoraStr.replace("T", " ");
    const parteHora = limpio.split(" ")[1].slice(0, 5); // Tomamos "22:39"
    [horas, minutos] = parteHora.split(":");
    horas = parseInt(horas, 10);

    // --- CORRECCIÓN DE DESFASE (UTC a GMT-6 Nicaragua) ---
    // Si detectamos que la hora guardada está adelantada por UTC, le restamos las 6 horas
    horas = horas - 6;
    if (horas < 0) {
      horas = horas + 24; // Corregir si pasa al día anterior
    }
  }

  // --- FORMATEO FINAL A 12 HORAS ---
  const ampm = horas >= 12 ? "PM" : "AM";
  horas = horas % 12;
  horas = horas ? horas : 12; // El 0 se convierte en 12

  // Asegurar que los minutos siempre tengan 2 dígitos (por si acaso)
  const minutosStr = String(minutos).padStart(2, "0");

  return `${horas}:${minutosStr} ${ampm}`;
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
        <td>${formatearHora12(v.hora ?? v.fecha_hora)}</td>
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

// Inicialización
cargarDashboard();
