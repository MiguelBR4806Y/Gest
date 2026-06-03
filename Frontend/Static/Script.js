// ── Aplicar tema guardado al cargar ──
const temaGuardado = localStorage.getItem("tema") || "dark";
document.documentElement.setAttribute("data-bs-theme", temaGuardado);
document.body.classList.add("bg-" + temaGuardado);

// ── Usuarios locales ──
const USUARIOS_LOCALES = [{ usuario: "root", password: "1234" }];

// ── Login ──
function iniciarSesion() {
  const usuario = document.getElementById("inputUsuario")?.value.trim();
  const password = document.getElementById("inputPassword")?.value.trim();

  if (!usuario || !password) {
    alert("Por favor llena todos los campos");
    return;
  }

  const esRoot = USUARIOS_LOCALES.find(
    (u) => u.usuario === usuario && u.password === password,
  );

  if (esRoot) {
    sessionStorage.setItem("usuario", usuario);
    sessionStorage.setItem("logueado", "true");
    const modal = bootstrap.Modal.getInstance(
      document.getElementById("modalLogin"),
    );
    if (modal) modal.hide();
    window.location.href = "dashboard.html";
    return;
  }

  verificarConBackend(usuario, password);
}

async function verificarConBackend(usuario, password) {
  try {
    const respuesta = await fetch("http://localhost:8000/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, password }),
    });

    if (!respuesta.ok) {
      alert("Usuario o contraseña incorrectos");
      return;
    }

    sessionStorage.setItem("usuario", usuario);
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

// ── Ejecutar al cargar ──
verificarSesion();
mostrarUsuario();
