import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

import { useToast } from "../context/ToastContext";

const ESTILOS = {
  success: {
    icon: CheckCircle2,
    clases: "bg-secondary-500/10 border-secondary-500/30 text-secondary-700 dark:text-secondary-400",
  },
  error: {
    icon: TriangleAlert,
    clases: "bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400",
  },
  info: {
    icon: Info,
    clases: "bg-brand-500/10 border-brand-500/30 text-brand-700 dark:text-brand-300",
  },
};

/**
 * Notificaciones flotantes.
 *
 * La lista vive en una región `aria-live` para que los lectores de pantalla
 * anuncien los mensajes, que antes pasaban completamente desapercibidos.
 */
export default function Toast() {
  const { toasts, dismissToast } = useToast();

  return (
    <div
      className="fixed bottom-4 right-4 left-4 sm:left-auto z-[9999] flex flex-col gap-2 sm:max-w-sm pointer-events-none"
      role="region"
      aria-label="Notificaciones"
    >
      <div aria-live="polite" aria-atomic="false" className="flex flex-col gap-2">
        {toasts.map((t) => {
          const { icon: Icon, clases } = ESTILOS[t.type] ?? ESTILOS.info;
          return (
            <div
              key={t.id}
              className={`pointer-events-auto flex items-start gap-3 px-3.5 py-3 rounded-xl
                          border shadow-md backdrop-blur-md bg-surface-card animate-slide-up ${clases}`}
            >
              <Icon size={17} className="shrink-0 mt-0.5" aria-hidden="true" />
              <p className="text-sm flex-1 text-content break-words">{t.message}</p>
              <button
                type="button"
                onClick={() => dismissToast(t.id)}
                aria-label="Cerrar notificación"
                className="shrink-0 btn-icon w-6 h-6 opacity-70 hover:opacity-100"
              >
                <X size={13} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
