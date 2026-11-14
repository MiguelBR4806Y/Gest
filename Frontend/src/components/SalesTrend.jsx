import { useMemo, useState } from "react";

import { fmtMoney } from "../lib/api";

const ANCHO = 280;
const ALTO = 116;
const BASE = 96;
const TECHO = 14;
const ETIQUETAS = {};

function etiquetaDia(fecha) {
  if (ETIQUETAS[fecha]) return ETIQUETAS[fecha];
  const d = new Date(`${fecha}T12:00:00`);
  const texto = d.toLocaleDateString("es-NI", { weekday: "short" }).replace(".", "");
  ETIQUETAS[fecha] = texto;
  return texto;
}

/**
 * Tendencia diaria de ventas y ganancia.
 *
 * SVG puro: no agrega dependencias de gráficas y hereda el color de acento
 * del negocio a través de las variables CSS.
 */
export default function SalesTrend({ dias = [], cargando = false }) {
  const [activo, setActivo] = useState(null);

  const { maximo, barras, anchoBarra, paso } = useMemo(() => {
    const total = dias.length || 1;
    const tope = Math.max(...dias.map((d) => Number(d.total) || 0), 1);
    const pasoCalc = ANCHO / total;
    return {
      maximo: tope,
      paso: pasoCalc,
      anchoBarra: Math.max(6, pasoCalc * 0.28),
      barras: dias.map((d, i) => {
        const x = i * pasoCalc + pasoCalc / 2;
        const altoVenta = ((Number(d.total) || 0) / tope) * (BASE - TECHO);
        const altoGanancia = ((Number(d.ganancia) || 0) / tope) * (BASE - TECHO);
        return {
          ...d,
          x,
          altoVenta: Math.max(altoVenta, Number(d.total) > 0 ? 2 : 0),
          altoGanancia: Math.max(altoGanancia, Number(d.ganancia) > 0 ? 2 : 0),
        };
      }),
    };
  }, [dias]);

  if (cargando) {
    return <div className="h-44 skeleton" aria-hidden="true" />;
  }

  if (dias.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-content-subtle">
        Aún no hay ventas para dibujar la tendencia.
      </p>
    );
  }

  const detalle = activo !== null ? barras[activo] : null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div className="min-h-[2.5rem]">
          {detalle ? (
            <>
              <p className="text-xs uppercase tracking-wide text-content-subtle">
                {etiquetaDia(detalle.fecha)} · {detalle.fecha}
              </p>
              <p className="text-lg font-bold tabular text-content">
                {fmtMoney(detalle.total)}
                <span className="ml-2 text-xs font-medium text-secondary-600 dark:text-secondary-400">
                  +{fmtMoney(detalle.ganancia)} ganancia
                </span>
              </p>
            </>
          ) : (
            <>
              <p className="text-xs uppercase tracking-wide text-content-subtle">
                Últimos {dias.length} días
              </p>
              <p className="text-sm text-content-muted">
                {dias.reduce((s, d) => s + (Number(d.operaciones) || 0), 0)} ventas
              </p>
            </>
          )}
        </div>

        <div className="flex items-center gap-4 text-xs text-content-muted">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-brand-500" aria-hidden="true" />
            Ventas
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-secondary-500" aria-hidden="true" />
            Ganancia
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${ANCHO} ${ALTO}`}
        preserveAspectRatio="none"
        className="h-44 w-full"
        role="img"
        aria-label={`Tendencia de los últimos ${dias.length} días: ${dias
          .map((d) => `${d.fecha}, ${fmtMoney(d.total)}`)
          .join("; ")}`}
      >
        <defs>
          <linearGradient id="trend-ventas" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" style={{ stopColor: "rgb(var(--brand-500))", stopOpacity: 0.95 }} />
            <stop offset="100%" style={{ stopColor: "rgb(var(--brand-500))", stopOpacity: 0.55 }} />
          </linearGradient>
          <linearGradient id="trend-ganancia" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" style={{ stopColor: "rgb(var(--secondary-500))", stopOpacity: 0.95 }} />
            <stop offset="100%" style={{ stopColor: "rgb(var(--secondary-500))", stopOpacity: 0.5 }} />
          </linearGradient>
        </defs>

        {[0.25, 0.5, 0.75, 1].map((f) => (
          <line
            key={f}
            x1="0"
            x2={ANCHO}
            y1={BASE - f * (BASE - TECHO)}
            y2={BASE - f * (BASE - TECHO)}
            style={{ stroke: "rgb(var(--border-default))" }}
            strokeWidth="0.5"
            strokeDasharray="2 3"
          />
        ))}

        <line
          x1="0"
          x2={ANCHO}
          y1={BASE}
          y2={BASE}
          style={{ stroke: "rgb(var(--border-strong))" }}
          strokeWidth="0.75"
        />

        {barras.map((b, i) => {
          const activoAqui = activo === i;
          const opacidad = activo === null || activoAqui ? 1 : 0.45;
          return (
            <g
              key={b.fecha}
              onMouseEnter={() => setActivo(i)}
              onMouseLeave={() => setActivo(null)}
            >
              <title>{`${b.fecha} · ${fmtMoney(b.total)} · ganancia ${fmtMoney(b.ganancia)}`}</title>
              <rect
                x={b.x - anchoBarra - 1}
                y={BASE - b.altoVenta}
                width={anchoBarra}
                height={b.altoVenta}
                rx="2"
                style={{ fill: "url(#trend-ventas)", opacity: opacidad }}
                className="chart-bar"
              />
              <rect
                x={b.x + 1}
                y={BASE - b.altoGanancia}
                width={anchoBarra}
                height={b.altoGanancia}
                rx="2"
                style={{ fill: "url(#trend-ganancia)", opacity: opacidad }}
                className="chart-bar"
              />
              {activoAqui && (
                <rect
                  x={b.x - paso / 2 + 1}
                  y={TECHO - 8}
                  width={paso - 2}
                  height={BASE - TECHO + 8}
                  rx="3"
                  style={{ fill: "rgb(var(--brand-500))", opacity: 0.06 }}
                />
              )}
            </g>
          );
        })}
      </svg>

      <div
        className="mt-2 grid text-center text-[10px] font-medium uppercase tracking-wide text-content-subtle"
        style={{ gridTemplateColumns: `repeat(${dias.length}, minmax(0, 1fr))` }}
        aria-hidden="true"
      >
        {dias.map((d, i) => (
          <span key={d.fecha} className={i === dias.length - 1 ? "text-content" : ""}>
            {etiquetaDia(d.fecha)}
          </span>
        ))}
      </div>
      <p className="sr-only">
        Máximo del periodo: {fmtMoney(maximo)}
      </p>
    </div>
  );
}
