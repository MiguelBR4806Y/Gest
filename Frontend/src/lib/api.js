const BASE = "";

export const ZONAS = [
  "America/Managua", "America/Mexico_City", "America/El_Salvador",
  "America/Costa_Rica", "America/Guatemala", "America/Panama",
  "America/Bogota", "America/Lima", "America/Santiago",
  "America/Argentina/Buenos_Aires", "America/Sao_Paulo",
  "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
  "Europe/Madrid", "UTC",
];

export const EVENTO_SESION_EXPIRADA = "auth:sesion-expirada";

function getToken() {
  return sessionStorage.getItem("token") ?? "";
}

/** Normaliza el `detail` de FastAPI, que puede ser texto o lista de errores. */
function mensajeDeError(detalle, status) {
  if (typeof detalle === "string" && detalle.trim()) return detalle;
  if (Array.isArray(detalle)) {
    const partes = detalle
      .map((e) => (typeof e === "string" ? e : e?.msg))
      .filter(Boolean);
    if (partes.length) return partes.join(". ");
  }
  if (status === 429) return "Demasiadas solicitudes. Espera unos segundos.";
  if (status === 401) return "Tu sesión expiró. Inicia sesión de nuevo.";
  if (status === 403) return "No tienes permiso para hacer eso.";
  if (status === 413) return "El archivo es demasiado grande.";
  if (status >= 500) return "Error interno del servidor. Intenta de nuevo.";
  return `Error HTTP ${status}`;
}

async function leerCuerpo(res) {
  const tipo = res.headers.get("content-type") || "";
  if (!tipo.includes("application/json")) return null;
  try {
    return await res.json();
  } catch {
    return null;
  }
}

function manejarNoAutorizado(status) {
  if (status !== 401) return;
  // Avisa al AuthContext para que cierre la sesión de forma ordenada, en vez
  // de recargar la página a media petición.
  window.dispatchEvent(new CustomEvent(EVENTO_SESION_EXPIRADA));
}

async function request(method, path, body) {
  const opts = {
    method,
    headers: { Authorization: "Bearer " + getToken() },
  };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }

  const res = await fetch(BASE + path, opts);
  const data = await leerCuerpo(res);

  if (!res.ok) {
    manejarNoAutorizado(res.status);
    throw new Error(mensajeDeError(data?.detail, res.status));
  }
  return data;
}

/**
 * Descarga un recurso protegido.
 *
 * No se puede usar `<a href>` con estos endpoints: el token viaja en la
 * cabecera Authorization y un enlace no la envía, así que siempre daba 401.
 */
async function descargarArchivo(path) {
  const res = await fetch(BASE + path, {
    headers: { Authorization: "Bearer " + getToken() },
  });

  if (!res.ok) {
    manejarNoAutorizado(res.status);
    const data = await leerCuerpo(res);
    throw new Error(mensajeDeError(data?.detail, res.status));
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  // Se intenta respetar el nombre que manda el servidor.
  const disposicion = res.headers.get("content-disposition") || "";
  const coincidencia = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposicion);
  const nombre = coincidencia ? decodeURIComponent(coincidencia[1]) : "descarga";

  return { url, nombre, revocar: () => URL.revokeObjectURL(url) };
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  put: (path, body) => request("PUT", path, body),
  delete: (path, body) => request("DELETE", path, body),

  postForm: async (path, formData) => {
    const res = await fetch(BASE + path, {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: formData,
    });
    const data = await leerCuerpo(res);
    if (!res.ok) {
      manejarNoAutorizado(res.status);
      throw new Error(mensajeDeError(data?.detail, res.status));
    }
    return data;
  },

  /** Descarga y guarda un archivo (PDF o ZIP) con el nombre indicado. */
  descargar: async (path, nombreSugerido) => {
    const { url, nombre, revocar } = await descargarArchivo(path);
    const a = document.createElement("a");
    a.href = url;
    a.download = nombreSugerido || nombre || "descarga";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(revocar, 1000);
  },

  /** Abre un archivo protegido (PDF) en una pestaña nueva. */
  abrir: async (path) => {
    const { url } = await descargarArchivo(path);
    const ventana = window.open(url, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    return ventana;
  },

  baseUrl: BASE,
};

function getZona() {
  try {
    return sessionStorage.getItem("zona_horaria") || "America/Managua";
  } catch {
    return "America/Managua";
  }
}

/** Hora corta (HH:MM AM/PM) en la zona horaria del negocio. */
export function formatHora(str, zona) {
  if (!str) return "—";
  if (typeof str === "string" && str.length === 5 && str.includes(":")) {
    const [h, m] = str.split(":").map(Number);
    const ampm = h >= 12 ? "PM" : "AM";
    return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${ampm}`;
  }
  const d = new Date(str);
  if (isNaN(d.getTime())) return str;
  return d.toLocaleString("es-NI", {
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: zona || getZona(),
  });
}

/** Fecha + hora, para tablas donde el contexto importa. */
export function formatFechaHora(str, zona) {
  if (!str) return "—";
  const d = new Date(str);
  if (isNaN(d.getTime())) return str;
  return d.toLocaleString("es-NI", {
    day: "2-digit",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
    timeZone: zona || getZona(),
  });
}

const cifras = (n, decimales = 2) => {
  const valor = Number(n);
  return Number.isFinite(valor)
    ? valor.toLocaleString("es-NI", { minimumFractionDigits: decimales, maximumFractionDigits: decimales })
    : "—";
};

export function fmtMoney(n) {
  const valor = Number(n);
  if (!Number.isFinite(valor)) return "—";
  return "C$ " + cifras(valor);
}

export function fmtMoneyUSD(n) {
  const valor = Number(n);
  if (!Number.isFinite(valor)) return "—";
  return "$ " + valor.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
