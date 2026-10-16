/* Arranque del tema antes del primer pintado.
 *
 * Vive en /public para ser un script externo: así la CSP puede seguir siendo
 * estricta (sin 'unsafe-inline' para scripts) y no aparece el parpadeo de tema
 * claro al cargar en modo oscuro.
 *
 * Se carga de forma bloqueante desde <head>; tiene que ser minúsculo.
 */
(function () {
  try {
    var guardado = localStorage.getItem("theme") || "system";
    var oscuro =
      guardado === "dark" ||
      (guardado === "system" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", oscuro);
    document.documentElement.dataset.theme = guardado;
  } catch {
    /* localStorage bloqueado (modo privado): se queda con el tema del sistema */
  }
})();
