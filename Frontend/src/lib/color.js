/**
 * Aplica el color de acento del negocio a la interfaz.
 *
 * El color se guarda en el perfil (`color_acento`) y hasta ahora solo se usaba
 * en los PDF. Aquí se genera una escala completa y se inyecta en las variables
 * CSS, de modo que botones, enlaces, badges y el sidebar lo reflejan al instante.
 */

const PARADAS = {
  50: ["#ffffff", 0.95],
  100: ["#ffffff", 0.88],
  200: ["#ffffff", 0.75],
  300: ["#ffffff", 0.55],
  400: ["#ffffff", 0.28],
  500: null,
  600: ["#000000", 0.14],
  700: ["#000000", 0.28],
  800: ["#000000", 0.42],
  900: ["#000000", 0.56],
};

const HEX_RE = /^#([0-9a-f]{6})$/i;

function aRgb(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

function mezclar(rgb, destinoHex, cantidad) {
  const destino = aRgb(destinoHex);
  return rgb.map((c, i) => Math.round(c + (destino[i] - c) * cantidad));
}

export function esHexValido(valor) {
  return typeof valor === "string" && HEX_RE.test(valor.trim());
}

/** Luminancia relativa (WCAG) para decidir si encima va texto claro u oscuro. */
function luminancia([r, g, b]) {
  const canal = (c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b);
}

export function aplicarColorAcento(hex) {
  if (!esHexValido(hex)) return false;

  const base = aRgb(hex.trim().toLowerCase());
  const raiz = document.documentElement;

  for (const [parada, config] of Object.entries(PARADAS)) {
    const rgb = config ? mezclar(base, config[0], config[1]) : base;
    raiz.style.setProperty(`--brand-${parada}`, rgb.join(" "));
  }

  // El anillo de foco sigue el color del negocio para que el contraste se
  // mantenga coherente en ambos temas.
  raiz.style.setProperty("--ring", base.join(" "));

  // Con un acento claro, el texto blanco del botón sería ilegible.
  const claro = luminancia(base) > 0.5;
  raiz.style.setProperty("--brand-contrast", claro ? "24 24 27" : "255 255 255");

  const themeColor = document.querySelector('meta[name="theme-color"]');
  if (themeColor) themeColor.setAttribute("content", hex.trim());

  return true;
}

export function limpiarColorAcento() {
  const raiz = document.documentElement;
  Object.keys(PARADAS).forEach((p) => raiz.style.removeProperty(`--brand-${p}`));
  raiz.style.removeProperty("--ring");
  raiz.style.removeProperty("--brand-contrast");
}
