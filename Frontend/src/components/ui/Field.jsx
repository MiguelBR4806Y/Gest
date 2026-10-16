import { cloneElement, isValidElement, useId } from "react";

/**
 * Envuelve un control de formulario y le asocia etiqueta, ayuda y error.
 *
 * El control recibe automáticamente `id`, `aria-describedby` y `aria-invalid`,
 * que es lo que faltaba antes: las etiquetas eran texto suelto sin asociar.
 */
export function Field({ label, hint, error, required = false, id: idForzado, children }) {
  const generado = useId();
  const id = idForzado || generado;
  const idError = error ? `${id}-error` : undefined;
  const idHint = hint ? `${id}-hint` : undefined;
  const descrito = [idHint, idError].filter(Boolean).join(" ") || undefined;

  let control = children;
  if (isValidElement(children)) {
    control = cloneElement(children, {
      id,
      "aria-describedby": descrito,
      "aria-invalid": error ? true : undefined,
      "aria-required": required || undefined,
    });
  }

  return (
    <div>
      {label && (
        <label className="label" htmlFor={id}>
          {label}
          {required && (
            <span className="text-red-500 ml-0.5" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      {control}
      {hint && !error && (
        <p className="field-hint" id={idHint}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={idError} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input({ error, className = "", ...props }) {
  return (
    <input
      className={`input ${error ? "input-error" : ""} ${className}`}
      {...props}
    />
  );
}

export function Select({ error, className = "", children, ...props }) {
  return (
    <select
      className={`input ${error ? "input-error" : ""} ${className}`}
      {...props}
    >
      {children}
    </select>
  );
}

export function Textarea({ error, className = "", ...props }) {
  return (
    <textarea
      className={`input resize-y min-h-[5rem] ${error ? "input-error" : ""} ${className}`}
      {...props}
    />
  );
}

/** Interruptor con etiqueta asociada, en vez del par checkbox + label suelto. */
export function Checkbox({ label, id: idForzado, className = "", ...props }) {
  const generado = useId();
  const id = idForzado || generado;

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      <input
        type="checkbox"
        id={id}
        className="w-4 h-4 rounded border-border bg-surface-card text-brand-600
                   focus:ring-2 focus:ring-brand-500/30 focus:ring-offset-0 cursor-pointer"
        {...props}
      />
      <label htmlFor={id} className="text-sm text-content cursor-pointer select-none">
        {label}
      </label>
    </div>
  );
}
