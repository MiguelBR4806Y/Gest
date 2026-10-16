import { Loader2 } from "lucide-react";

const VARIANTES = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  danger: "btn-danger",
  ghost: "btn-ghost",
};

export function Button({
  variant = "primary",
  size,
  loading = false,
  disabled = false,
  icon: Icon,
  className = "",
  type = "button",
  children,
  ...props
}) {
  const clases = [
    VARIANTES[variant] ?? VARIANTES.primary,
    size === "sm" && "btn-sm",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      className={clases}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <Loader2 size={15} className="animate-spin" aria-hidden="true" />
      ) : (
        Icon && <Icon size={15} aria-hidden="true" />
      )}
      {children}
    </button>
  );
}

/** Botón de solo icono. El `label` es obligatorio: sin él no hay nombre accesible. */
export function IconButton({ label, icon: Icon, size = 15, className = "", ...props }) {
  return (
    <button
      type="button"
      className={`btn-icon ${className}`}
      aria-label={label}
      title={label}
      {...props}
    >
      <Icon size={size} aria-hidden="true" />
    </button>
  );
}
