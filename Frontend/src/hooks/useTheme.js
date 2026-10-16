import { useEffect, useState } from "react";

const CLAVE = "theme";
const VALIDOS = ["system", "dark", "light"];

function leerPreferencia() {
  try {
    const guardado = localStorage.getItem(CLAVE);
    return VALIDOS.includes(guardado) ? guardado : "system";
  } catch {
    return "system";
  }
}

function prefiereOscuro() {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches === true
  );
}

/**
 * Tema claro / oscuro / sistema.
 *
 * Devuelve `[esOscuro, tema, ciclarTema]`. La clase en <html> también la fija
 * `public/theme-boot.js` antes del primer pintado, para evitar el destello de
 * tema claro al cargar.
 */
export function useTheme() {
  const [tema, setTema] = useState(leerPreferencia);
  const [sistemaOscuro, setSistemaOscuro] = useState(prefiereOscuro);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const alCambiar = (e) => setSistemaOscuro(e.matches);
    mq.addEventListener("change", alCambiar);
    return () => mq.removeEventListener("change", alCambiar);
  }, []);

  const esOscuro = tema === "dark" || (tema === "system" && sistemaOscuro);

  useEffect(() => {
    const raiz = document.documentElement;
    raiz.classList.toggle("dark", esOscuro);
    raiz.dataset.theme = tema;
    try {
      localStorage.setItem(CLAVE, tema);
    } catch {
      /* localStorage bloqueado: el tema queda solo en memoria */
    }
  }, [esOscuro, tema]);

  const ciclar = () =>
    setTema((t) => (t === "system" ? "dark" : t === "dark" ? "light" : "system"));

  return [esOscuro, tema, ciclar];
}
