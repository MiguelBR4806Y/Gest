// ── Aplicar tema guardado al cargar ──
const temaGuardado = localStorage.getItem("tema") || "dark";
document.documentElement.setAttribute("data-bs-theme", temaGuardado);
document.body.classList.add("bg-" + temaGuardado);

// ── Obtener token ──
function getToken() {
  return sessionStorage.getItem("token") ?? "";
}

// ── Login ──
function iniciarSesion() {
  const usuario = document.getElementById("inputUsuario")?.value.trim();
  const password = document.getElementById("inputPassword")?.value.trim();

  if (!usuario || !password) {
    alert("Por favor llena todos los campos");
    return;
  }

  verificarConBackend(usuario, password);
}

async function verificarConBackend(usuario, password) {
  try {
    const respuesta = await fetch("http://127.0.0.1:8000/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, password }),
    });

    if (!respuesta.ok) {
      alert("Usuario o contraseña incorrectos");
      return;
    }

    const data = await respuesta.json();
    sessionStorage.setItem("token", data.token);
    sessionStorage.setItem("usuario", data.usuario);
    sessionStorage.setItem("nombre_negocio", data.nombre_negocio);
    sessionStorage.setItem("logueado", "true");

    const modal = bootstrap.Modal.getInstance(
      document.getElementById("modalLogin"),
    );
    if (modal) modal.hide();
    window.location.href = "dashboard.html";
  } catch (e) {
    alert("No se pudo conectar con el servidor");
  }
}

// ── Proteger módulos ──
function verificarSesion() {
  const pagina = window.location.pathname;
  const esIndex = pagina.includes("index.html") || pagina.endsWith("/");
  if (!esIndex && !sessionStorage.getItem("logueado")) {
    window.location.href = "index.html";
  }
}

// ── Formateo de hora (12h, Nicaragua GMT-6) ──
function formatearHora12(fechaHoraStr) {
  if (!fechaHoraStr) return "—";

  let horas, minutos;

  if (fechaHoraStr.length === 5 && fechaHoraStr.includes(":")) {
    [horas, minutos] = fechaHoraStr.split(":");
    horas = parseInt(horas, 10);
  } else {
    const limpio = fechaHoraStr.replace("T", " ");
    const parteHora = limpio.split(" ")[1].slice(0, 5);
    [horas, minutos] = parteHora.split(":");
    horas = parseInt(horas, 10);

    horas = horas - 6;
    if (horas < 0) {
      horas = horas + 24;
    }
  }

  const ampm = horas >= 12 ? "PM" : "AM";
  horas = horas % 12;
  horas = horas ? horas : 12;

  const minutosStr = String(minutos).padStart(2, "0");

  return `${horas}:${minutosStr} ${ampm}`;
}

// ── Mostrar nombre de usuario en navbar ──
function mostrarUsuario() {
  const span = document.getElementById("nombreUsuario");
  const btnLogin = document.getElementById("btnLogin");
  const btnCerrar = document.getElementById("btnCerrarSesion");
  const btnLoginMain = document.getElementById("btnLoginMain");

  if (sessionStorage.getItem("logueado")) {
    if (btnLoginMain) btnLoginMain.style.display = "none";

    if (span) {
      span.textContent = "⚙️ " + (sessionStorage.getItem("usuario") ?? "");
      span.style.cursor = "pointer";
      span.title = "Configuración del negocio";
      span.addEventListener("click", abrirModalPerfil);
    }

    if (btnLogin) btnLogin.style.display = "none";
    if (btnCerrar) btnCerrar.style.display = "block";

    crearModalPerfil();
  } else {
    if (btnCerrar) btnCerrar.style.display = "none";
  }
}

// ── Modal de configuración del negocio ──
function crearModalPerfil() {
  if (document.getElementById("modalPerfil")) return;

  const modalHTML = `
    <div class="modal fade" id="modalPerfil" tabindex="-1">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Configuración del negocio</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <div class="mb-3">
              <label class="form-label">Nombre del negocio</label>
              <input type="text" class="form-control" id="perfil-nombre-negocio">
            </div>
            <div class="mb-3">
              <label class="form-label">Color de acento</label>
              <input type="color" class="form-control form-control-color" id="perfil-color-acento" value="#1D9E75">
            </div>
            <div class="mb-3">
              <label class="form-label">Logo del negocio (PNG o JPG)</label>
              <input type="file" class="form-control" id="perfil-logo" accept="image/png, image/jpeg">
              <button type="button" class="btn btn-sm btn-outline-primary mt-2" onclick="subirLogo()">Subir logo</button>
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
            <button type="button" class="btn btn-outline-info" onclick="previsualizarFactura()">Vista previa</button>
            <button type="button" class="btn btn-success" onclick="guardarPerfil()">Guardar cambios</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML("beforeend", modalHTML);
}

async function abrirModalPerfil() {
  try {
    const datos = await apiGet("/auth/perfil");
    document.getElementById("perfil-nombre-negocio").value =
      datos.nombre_negocio ?? "";
    document.getElementById("perfil-color-acento").value =
      datos.color_acento ?? "#1D9E75";
  } catch (e) {
    alert("Error al cargar la configuración del negocio");
    return;
  }

  new bootstrap.Modal(document.getElementById("modalPerfil")).show();
}

async function guardarPerfil() {
  const nombre_negocio = document
    .getElementById("perfil-nombre-negocio")
    .value.trim();
  const color_acento = document.getElementById("perfil-color-acento").value;

  if (!nombre_negocio) {
    alert("El nombre del negocio es obligatorio");
    return;
  }

  try {
    await apiPut("/auth/perfil", { nombre_negocio, color_acento });
    sessionStorage.setItem("nombre_negocio", nombre_negocio);

    bootstrap.Modal.getInstance(document.getElementById("modalPerfil")).hide();
    alert("Configuración guardada con éxito");
  } catch (e) {
    alert("Error al guardar la configuración");
  }
}

async function subirLogo() {
  const input = document.getElementById("perfil-logo");
  if (!input.files || input.files.length === 0) {
    alert("Selecciona una imagen primero");
    return;
  }

  const formData = new FormData();
  formData.append("archivo", input.files[0]);

  try {
    const respuesta = await fetch("http://127.0.0.1:8000/auth/perfil/logo", {
      method: "POST",
      headers: { Authorization: "Bearer " + getToken() },
      body: formData,
    });

    if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);

    alert("Logo subido con éxito. Usa 'Vista previa' para verlo.");
  } catch (e) {
    alert("Error al subir el logo");
  }
}

function previsualizarFactura() {
  const nombre_negocio =
    document.getElementById("perfil-nombre-negocio").value.trim() ||
    "Mi Negocio";
  const color_acento =
    document.getElementById("perfil-color-acento").value || "#1D9E75";
  const usuario = sessionStorage.getItem("usuario") ?? "root";

  const params = new URLSearchParams({ nombre_negocio, color_acento, usuario });
  window.open(
    "http://127.0.0.1:8000/facturas/preview?" + params.toString(),
    "_blank",
  );
}

// ── Cerrar sesión ──
function cerrarSesion() {
  sessionStorage.clear();
  window.location.href = "index.html";
}

function abrirRegistro() {
  bootstrap.Modal.getInstance(document.getElementById("modalLogin")).hide();
  new bootstrap.Modal(document.getElementById("modalRegistro")).show();
}

function volverLogin() {
  bootstrap.Modal.getInstance(document.getElementById("modalRegistro")).hide();
  new bootstrap.Modal(document.getElementById("modalLogin")).show();
}

async function registrarse() {
  const usuario = document.getElementById("r-usuario").value.trim();
  const password = document.getElementById("r-password").value.trim();
  const nombre_negocio = document.getElementById("r-negocio").value.trim();

  if (!usuario || !password || !nombre_negocio) {
    alert("Todos los campos son obligatorios");
    return;
  }

  try {
    const respuesta = await fetch("http://127.0.0.1:8000/auth/registro", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, password, nombre_negocio }),
    });

    if (!respuesta.ok) {
      const error = await respuesta.json();
      alert(error.detail ?? "Error al registrarse");
      return;
    }

    alert("Cuenta creada exitosamente. Ahora puedes iniciar sesión.");
    volverLogin();
  } catch (e) {
    alert("No se pudo conectar con el servidor");
  }
}

// ── Helpers de API con token ──
async function apiGet(ruta) {
  const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
    headers: { Authorization: "Bearer " + getToken() },
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

async function apiPost(ruta, datos) {
  const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken(),
    },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

async function apiPut(ruta, datos) {
  const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + getToken(),
    },
    body: JSON.stringify(datos),
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

async function apiDelete(ruta) {
  const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
    method: "DELETE",
    headers: { Authorization: "Bearer " + getToken() },
  });
  if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
  return respuesta.json();
}

// ── Ejecutar al cargar ──
verificarSesion();
mostrarUsuario();
