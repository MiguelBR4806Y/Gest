import { useCallback, useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

const TAMANOS = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

const SELECTOR_ENFOCABLES = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

/**
 * Diálogo accesible.
 *
 * Antes el cierre con Escape estaba en un `onKeyDown` sobre un div sin
 * `tabIndex`, así que nunca se disparaba. Ahora se escucha en el documento,
 * se atrapa el foco dentro y se devuelve al elemento que abrió el modal.
 */
export default function Modal({ title, open, onClose, children, size = "md", footer }) {
  const idTitulo = useId();
  const refPanel = useRef(null);
  const refFocoPrevio = useRef(null);

  const cerrar = useCallback(() => onClose?.(), [onClose]);

  // Bloqueo del scroll del body mientras el modal está abierto.
  useEffect(() => {
    if (!open) return;
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflowPrevio;
    };
  }, [open]);

  // Escape para cerrar + Tab atrapado dentro del panel.
  useEffect(() => {
    if (!open) return;

    function alPresionar(e) {
      if (e.key === "Escape") {
        e.stopPropagation();
        cerrar();
        return;
      }
      if (e.key !== "Tab" || !refPanel.current) return;

      const enfocables = Array.from(
        refPanel.current.querySelectorAll(SELECTOR_ENFOCABLES)
      ).filter((el) => el.offsetParent !== null);

      if (enfocables.length === 0) {
        e.preventDefault();
        return;
      }

      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];

      if (e.shiftKey && document.activeElement === primero) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primero.focus();
      }
    }

    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [open, cerrar]);

  // Guarda y restaura el foco.
  useEffect(() => {
    if (!open) return;
    refFocoPrevio.current = document.activeElement;

    const t = setTimeout(() => {
      const panel = refPanel.current;
      if (!panel) return;
      const enfocables = panel.querySelectorAll(SELECTOR_ENFOCABLES);
      (enfocables[0] ?? panel).focus();
    }, 0);

    return () => {
      clearTimeout(t);
      if (refFocoPrevio.current instanceof HTMLElement) refFocoPrevio.current.focus();
    };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={cerrar}
        aria-hidden="true"
      />
      <div
        ref={refPanel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? idTitulo : undefined}
        tabIndex={-1}
        className={`relative w-full ${TAMANOS[size] ?? TAMANOS.md} bg-surface-card border border-border
                    rounded-t-2xl sm:rounded-2xl shadow-lg animate-slide-up outline-none
                    max-h-[92vh] flex flex-col`}
      >
        <div className="flex items-start justify-between gap-4 px-5 sm:px-6 py-4 border-b border-border/60 shrink-0">
          {title && (
            <h2 id={idTitulo} className="text-base font-semibold text-content pt-1">
              {title}
            </h2>
          )}
          <button
            type="button"
            onClick={cerrar}
            className="btn-icon shrink-0 ml-auto"
            aria-label="Cerrar"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        <div className="px-5 sm:px-6 py-5 overflow-y-auto">{children}</div>

        {footer && (
          <div className="px-5 sm:px-6 py-4 border-t border-border/60 flex justify-end gap-3 shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}

/** Diálogo de confirmación para acciones destructivas. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = "¿Estás seguro?",
  mensaje,
  confirmLabel = "Confirmar",
  variant = "danger",
  loading = false,
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={loading}>
            Cancelar
          </button>
          <button
            type="button"
            className={variant === "danger" ? "btn-danger" : "btn-primary"}
            onClick={onConfirm}
            disabled={loading}
          >
            {loading ? "Procesando..." : confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-sm text-content-muted">{mensaje}</p>
    </Modal>
  );
}
