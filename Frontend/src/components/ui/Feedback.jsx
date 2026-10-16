import { Loader2 } from "lucide-react";

export function Spinner({ size = 20, className = "", label = "Cargando" }) {
  return (
    <Loader2
      size={size}
      className={`animate-spin text-brand-500 ${className}`}
      role="status"
      aria-label={label}
    />
  );
}

export function Skeleton({ className = "" }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}

/** Esqueleto con la forma de una tabla, para que la carga no sea un salto en blanco. */
export function TableSkeleton({ filas = 6, columnas = 4 }) {
  return (
    <div className="table-container" role="status" aria-label="Cargando datos">
      <div className="px-4 py-3 border-b border-border bg-surface-elevated/60">
        <Skeleton className="h-3 w-28" />
      </div>
      <div className="divide-y divide-border/60">
        {Array.from({ length: filas }).map((_, f) => (
          <div key={f} className="flex items-center gap-4 px-4 py-3.5">
            {Array.from({ length: columnas }).map((_, c) => (
              <Skeleton
                key={c}
                className={`h-4 ${c === 1 ? "flex-[2]" : "flex-1"} ${c === columnas - 1 ? "max-w-[80px]" : ""}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function CardSkeleton({ cantidad = 4 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4" role="status" aria-label="Cargando datos">
      {Array.from({ length: cantidad }).map((_, i) => (
        <div key={i} className="metric-card">
          <Skeleton className="w-10 h-10 !rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="h-5 w-28" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ErrorState({ mensaje, onReintentar }) {
  return (
    <div className="card p-6 text-center">
      <p className="text-sm text-red-500 dark:text-red-400">{mensaje || "No se pudieron cargar los datos."}</p>
      {onReintentar && (
        <button type="button" className="btn-secondary btn-sm mt-3 mx-auto" onClick={onReintentar}>
          Reintentar
        </button>
      )}
    </div>
  );
}

const TONOS_BADGE = {
  efectivo: "badge-green",
  tarjeta: "badge-blue",
  transferencia: "badge-blue",
  credito: "badge-yellow",
};

export function BadgeMetodoPago({ metodo }) {
  return <span className={TONOS_BADGE[metodo] ?? "badge-neutral"}>{metodo ?? "—"}</span>;
}
