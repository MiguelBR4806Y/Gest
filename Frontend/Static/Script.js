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

// ── Mostrar nombre de usuario en navbar ──
function mostrarUsuario() {
  const span = document.getElementById("nombreUsuario");
  const btnLogin = document.getElementById("btnLogin");
  const btnCerrar = document.getElementById("btnCerrarSesion");
  const btnLoginMain = document.getElementById("btnLoginMain");
  if (sessionStorage.getItem("logueado")) {
    if (btnLoginMain) btnLoginMain.style.display = "none";
    if (span) span.textContent = sessionStorage.getItem("usuario") ?? "";
    if (btnLogin) btnLogin.style.display = "none";
    if (btnCerrar) btnCerrar.style.display = "block";
  } else {
    if (btnCerrar) btnCerrar.style.display = "none";
  }
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
        headers: { "Authorization": "Bearer " + getToken() }
    });
    if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
    return respuesta.json();
}

async function apiPost(ruta, datos) {
    const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + getToken()
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
            "Authorization": "Bearer " + getToken()
        },
        body: JSON.stringify(datos),
    });
    if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
    return respuesta.json();
}

async function apiDelete(ruta) {
    const respuesta = await fetch("http://127.0.0.1:8000" + ruta, {
        method: "DELETE",
        headers: { "Authorization": "Bearer " + getToken() }
    });
    if (!respuesta.ok) throw new Error("Error HTTP: " + respuesta.status);
    return respuesta.json();
}

// ── Ejecutar al cargar ──
verificarSesion();
mostrarUsuario();
