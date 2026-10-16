import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowDownRight, ArrowUpRight, BadgePercent, Banknote,
  Bot, Calendar, CreditCard, DollarSign, Package, Plus, RefreshCw,
  ShoppingCart, Tag, TrendingUp, Users, Wallet, X,
} from "lucide-react";

import { CardSkeleton, TableSkeleton } from "../components/ui/Feedback";
import { Button, IconButton } from "../components/ui/Button";
import { Card, CardHeader, EmptyState, StatCard } from "../components/ui/Card";
import { useAuth } from "../context/AuthContext";
import { api, formatHora, fmtMoney } from "../lib/api";

const METODOS = {
  efectivo: { label: "Efectivo", icon: Banknote, color: "text-secondary-600 dark:text-secondary-400" },
  tarjeta: { label: "Tarjeta", icon: CreditCard, color: "text-brand-600 dark:text-brand-300" },
  transferencia: { label: "Transferencia", icon: Wallet, color: "text-accent-600 dark:text-accent-400" },
  credito: { label: "Crédito", icon: ShoppingCart, color: "text-red-600 dark:text-red-400" },
};

const ACCESOS = [
  { to: "/ventas", label: "Nueva venta", icon: Plus, primario: true },
  { to: "/inventario", label: "Agregar producto", icon: Package },
  { to: "/clientes", label: "Nuevo cliente", icon: Users },
  { to: "/gesti", label: "Preguntar a Gesti", icon: Bot },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [metricas, setMetricas] = useState(null);
  const [ultimasVentas, setUltimasVentas] = useState([]);
  const [stockBajo, setStockBajo] = useState([]);
  const [promociones, setPromociones] = useState([]);
  const [anios, setAnios] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [avisoTasaVisible, setAvisoTasaVisible] = useState(
    () => sessionStorage.getItem("ocultarAvisoTasa") !== "true"
  );

  const cargar = useCallback(async () => {
    setCargando(true);
    setError("");
    try {
      const [dash, resumen, bajo, promos, years] = await Promise.all([
        api.get("/reportes/dashboard"),
        api.get("/ventas/resumen-dia").catch(() => null),
        api.get("/productos/stock-bajo").catch(() => []),
        api.get("/promociones/").catch(() => []),
        // El endpoint devuelve { anios: [...] }, no un array — antes se
        // comprobaba Array.isArray sobre el objeto y nunca se pintaba nada.
        api.get("/organizacion/anios").catch(() => null),
      ]);

      setMetricas({
        total_productos: dash.total_productos,
        ventas_hoy: dash.resumen_dia?.total_ventas ?? 0,
        total_clientes: dash.total_clientes,
        alertas_stock: dash.stock_bajo,
      });
      setUltimasVentas(resumen?.ultimas_ventas ?? []);
      setStockBajo(Array.isArray(bajo) ? bajo : []);
      setPromociones(Array.isArray(promos) ? promos.filter((p) => p.activa) : []);
      setAnios(Array.isArray(years?.anios) ? years.anios : []);
    } catch (e) {
      setError(e.message || "No se pudo cargar el dashboard");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const porMetodo = ultimasVentas.reduce((acc, v) => {
    const m = v.metodo_pago || "otro";
    acc[m] = (acc[m] || 0) + Number(v.total || 0);
    return acc;
  }, {});

  const anioActual = new Date().getFullYear();
  const delAnio = anios.find((a) => a.anio === anioActual);
  const anioPrevio = anios.find((a) => a.anio === anioActual - 1);

  const variacion =
    delAnio && anioPrevio && Number(anioPrevio.total_ingresos) > 0
      ? Math.round(
          ((delAnio.total_ingresos - anioPrevio.total_ingresos) / anioPrevio.total_ingresos) * 100
        )
      : null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>
            Hola, <span className="text-content font-medium">{user?.usuario}</span>. Este es el
            resumen de hoy.
          </p>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} onClick={cargar} loading={cargando}>
          Actualizar
        </Button>
      </div>

      {!user?.tasa_cambio_configurada && avisoTasaVisible && (
        <div className="card p-4 border-accent-500/30 flex items-start gap-3" role="status">
          <div className="w-9 h-9 rounded-lg bg-accent-500/15 flex items-center justify-center shrink-0">
            <DollarSign size={17} className="text-accent-600 dark:text-accent-400" aria-hidden="true" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-content">Configura tu tasa de cambio</p>
            <p className="text-xs text-content-muted mt-0.5">
              Con la tasa C$ / US$ los precios se convierten a dólares automáticamente.
            </p>
          </div>
          <IconButton
            label="Descartar aviso"
            icon={X}
            onClick={() => {
              setAvisoTasaVisible(false);
              sessionStorage.setItem("ocultarAvisoTasa", "true");
            }}
          />
        </div>
      )}

      <div className="flex items-center gap-2.5 overflow-x-auto pb-1 -mx-1 px-1">
        {ACCESOS.map(({ to, label, icon, primario }) => (
          <Button
            key={to}
            variant={primario ? "primary" : "secondary"}
            icon={icon}
            onClick={() => navigate(to)}
            className="shrink-0"
          >
            {label}
          </Button>
        ))}
      </div>

      {error && (
        <div className="card p-4 border-red-500/30 bg-red-500/5 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {cargando ? (
        <>
          <CardSkeleton />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <TableSkeleton filas={4} columnas={3} />
            <TableSkeleton filas={4} columnas={2} />
          </div>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard
              icon={Package}
              label="Productos"
              value={metricas?.total_productos ?? 0}
              sub="Registrados"
            />
            <StatCard
              icon={TrendingUp}
              label="Ventas de hoy"
              value={fmtMoney(metricas?.ventas_hoy)}
              sub="Acumulado del día"
              tono="green"
            />
            <StatCard
              icon={Users}
              label="Clientes"
              value={metricas?.total_clientes ?? 0}
              sub="Registrados"
            />
            <StatCard
              icon={AlertTriangle}
              label="Stock bajo"
              value={metricas?.alertas_stock ?? 0}
              sub={metricas?.alertas_stock > 0 ? "Requieren reposición" : "Todo en orden"}
              tono={metricas?.alertas_stock > 0 ? "red" : "brand"}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader title="Últimas ventas" subtitle="Movimientos del día" />
              {ultimasVentas.length === 0 ? (
                <EmptyState
                  icon={ShoppingCart}
                  title="Sin ventas hoy"
                  text="Cuando registres una venta aparecerá aquí."
                  action={
                    <Button size="sm" icon={Plus} onClick={() => navigate("/ventas")}>
                      Registrar venta
                    </Button>
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr>
                        <th className="th">Cliente</th>
                        <th className="th">Hora</th>
                        <th className="th text-right">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ultimasVentas.slice(0, 7).map((v, i) => (
                        <tr key={v.id ?? i} className="table-row">
                          <td className="td max-w-[12rem] truncate">
                            {v.cliente_nombre || "Consumidor final"}
                          </td>
                          <td className="td text-content-muted">{formatHora(v.fecha_hora)}</td>
                          <td className="td text-right font-medium tabular">
                            {fmtMoney(v.total)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>

            <Card>
              <CardHeader
                title="Stock bajo"
                subtitle={
                  stockBajo.length ? `${stockBajo.length} producto(s) en el mínimo` : "Sin alertas"
                }
              />
              {stockBajo.length === 0 ? (
                <EmptyState
                  icon={Package}
                  title="Inventario saludable"
                  text="Ningún producto está en su nivel mínimo."
                />
              ) : (
                <ul className="divide-y divide-border/60 max-h-80 overflow-y-auto">
                  {stockBajo.map((p, i) => (
                    <li
                      key={p.id ?? i}
                      className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-surface-hover"
                    >
                      <span className="text-sm text-content truncate">{p.nombre}</span>
                      <span className="badge-red shrink-0">{p.stock} u.</span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card>
              <CardHeader title="Métodos de pago" subtitle="Ventas de hoy" />
              <div className="p-5">
                {Object.keys(porMetodo).length === 0 ? (
                  <p className="text-sm text-content-subtle">Sin ventas registradas hoy.</p>
                ) : (
                  <ul className="space-y-2.5">
                    {Object.entries(porMetodo).map(([metodo, total]) => {
                      const info =
                        METODOS[metodo] ?? { label: metodo, icon: Banknote, color: "text-content-muted" };
                      const Icono = info.icon;
                      return (
                        <li key={metodo} className="flex items-center justify-between gap-3">
                          <span className="flex items-center gap-2.5 min-w-0">
                            <Icono size={15} className={info.color} aria-hidden="true" />
                            <span className="text-sm text-content truncate">{info.label}</span>
                          </span>
                          <span className={`text-sm font-semibold tabular shrink-0 ${info.color}`}>
                            {fmtMoney(total)}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </Card>

            <Card>
              <CardHeader
                title="Promociones activas"
                icon={BadgePercent}
                action={
                  <Button variant="ghost" size="sm" onClick={() => navigate("/promociones")}>
                    Gestionar
                  </Button>
                }
              />
              <div className="p-5">
                {promociones.length === 0 ? (
                  <p className="text-sm text-content-subtle">No hay promociones activas.</p>
                ) : (
                  <ul className="space-y-2">
                    {promociones.map((p) => (
                      <li
                        key={p.id}
                        className="flex items-center justify-between gap-3 p-2.5 rounded-lg bg-accent-500/5 border border-accent-500/20"
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          <Tag size={13} className="text-accent-600 dark:text-accent-400 shrink-0" aria-hidden="true" />
                          <span className="text-sm text-content truncate">{p.nombre}</span>
                        </span>
                        <span className="text-xs font-semibold text-accent-600 dark:text-accent-400 shrink-0">
                          {p.tipo === "porcentaje"
                            ? `${p.valor}%`
                            : p.tipo === "monto_fijo"
                              ? `C$${p.valor}`
                              : "2x1"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </Card>

            <Card>
              <CardHeader title={String(anioActual)} subtitle="Resumen anual" icon={Calendar} />
              <div className="p-5">
                {delAnio ? (
                  <dl className="space-y-3">
                    <div className="flex items-center justify-between">
                      <dt className="text-sm text-content-muted">Ingresos totales</dt>
                      <dd className="text-sm font-bold tabular">{fmtMoney(delAnio.total_ingresos)}</dd>
                    </div>
                    <div className="flex items-center justify-between">
                      <dt className="text-sm text-content-muted">Ventas realizadas</dt>
                      <dd className="text-sm font-semibold tabular">{delAnio.total_ventas}</dd>
                    </div>
                    {variacion !== null && (
                      <div
                        className={`flex items-center gap-1.5 text-xs font-medium ${
                          variacion >= 0
                            ? "text-secondary-600 dark:text-secondary-400"
                            : "text-red-600 dark:text-red-400"
                        }`}
                      >
                        {variacion >= 0 ? (
                          <ArrowUpRight size={14} aria-hidden="true" />
                        ) : (
                          <ArrowDownRight size={14} aria-hidden="true" />
                        )}
                        <span>{Math.abs(variacion)}% respecto a {anioActual - 1}</span>
                      </div>
                    )}
                  </dl>
                ) : (
                  <p className="text-sm text-content-subtle">Sin datos de {anioActual} todavía.</p>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full mt-4"
                  onClick={() => navigate("/organizacion")}
                >
                  Ver detalle
                </Button>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
