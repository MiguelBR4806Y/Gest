import { useState } from "react";
import { Check, Copy, Eye, EyeOff } from "lucide-react";

/** Recuadro copiable con usuario y contraseña de un vendedor. */
export default function CredencialesBox({ usuario, password, titulo = "Credenciales de acceso" }) {
  const [visible, setVisible] = useState(false);
  const [copiado, setCopiado] = useState("");

  async function copiar(campo, valor) {
    try {
      await navigator.clipboard.writeText(valor);
      setCopiado(campo);
      setTimeout(() => setCopiado(""), 1600);
    } catch {
      setCopiado("");
    }
  }

  const filas = [
    { campo: "usuario", etiqueta: "Usuario", valor: usuario },
    { campo: "password", etiqueta: "Contraseña", valor: visible ? password : "•".repeat(12) },
  ];

  return (
    <div className="rounded-xl border border-brand-500/30 bg-brand-500/5 p-4 space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-brand-700 dark:text-brand-300">
        {titulo}
      </p>
      {filas.map(({ campo, etiqueta, valor }) => (
        <div key={campo} className="flex items-center gap-2">
          <span className="w-20 shrink-0 text-xs text-content-subtle">{etiqueta}</span>
          <code className="flex-1 min-w-0 truncate rounded-lg bg-surface-card px-2.5 py-1.5 font-mono text-sm text-content">
            {valor}
          </code>
          {campo === "password" && (
            <button
              type="button"
              className="btn-icon shrink-0"
              onClick={() => setVisible((v) => !v)}
              aria-label={visible ? "Ocultar contraseña" : "Mostrar contraseña"}
            >
              {visible ? <EyeOff size={15} aria-hidden="true" /> : <Eye size={15} aria-hidden="true" />}
            </button>
          )}
          <button
            type="button"
            className="btn-icon shrink-0"
            onClick={() => copiar(campo, password && campo === "password" ? password : usuario)}
            aria-label={`Copiar ${etiqueta.toLowerCase()}`}
          >
            {copiado === campo ? (
              <Check size={15} className="text-secondary-600" aria-hidden="true" />
            ) : (
              <Copy size={15} aria-hidden="true" />
            )}
          </button>
        </div>
      ))}
      <p className="text-xs text-content-subtle pt-1">
        Compártelas con el vendedor: son las que usará para iniciar sesión.
      </p>
    </div>
  );
}
