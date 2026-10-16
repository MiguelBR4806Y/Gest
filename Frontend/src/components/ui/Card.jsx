const TONOS = {
  brand: { bg: "bg-brand-500/10", icon: "text-brand-500 dark:text-brand-300" },
  green: { bg: "bg-secondary-500/10", icon: "text-secondary-600 dark:text-secondary-400" },
  red: { bg: "bg-red-500/10", icon: "text-red-500 dark:text-red-400" },
  yellow: { bg: "bg-accent-500/10", icon: "text-accent-600 dark:text-accent-400" },
};

export function Card({ className = "", children, ...props }) {
  return (
    <div className={`card ${className}`} {...props}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, icon: Icon }) {
  return (
    <div className="px-5 py-4 border-b border-border/60 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2.5 min-w-0">
        {Icon && <Icon size={16} className="text-content-muted shrink-0" aria-hidden="true" />}
        <div className="min-w-0">
          <h3 className="section-title truncate">{title}</h3>
          {subtitle && <p className="text-xs text-content-subtle mt-0.5 truncate">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

/** Tarjeta de métrica: icono, etiqueta y valor. */
export function StatCard({ icon: Icon, label, value, sub, tono = "brand" }) {
  const t = TONOS[tono] ?? TONOS.brand;
  return (
    <div className="metric-card">
      <div className={`metric-icon ${t.bg}`}>
        <Icon size={19} className={t.icon} aria-hidden="true" />
      </div>
      <div className="min-w-0">
        <p className="metric-label">{label}</p>
        <p className="metric-value tabular mt-0.5">{value}</p>
        {sub && <p className="text-xs text-content-subtle mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, text, action }) {
  return (
    <div className="empty-state">
      {Icon && (
        <div className="w-12 h-12 rounded-xl bg-surface-elevated flex items-center justify-center">
          <Icon size={22} className="text-content-subtle" aria-hidden="true" />
        </div>
      )}
      <p className="empty-state-title">{title}</p>
      {text && <p className="empty-state-text">{text}</p>}
      {action}
    </div>
  );
}
