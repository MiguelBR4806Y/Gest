import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatHora, fmtMoney } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import {
  Package, TrendingUp, Users, TriangleAlert as AlertTriangle,
  RefreshCw, DollarSign, X, Plus, FileText,
  CreditCard, Wallet, Banknote, Bot, Calendar,
  BadgePercent, ArrowUpRight, ArrowDownRight, Tag
} from "lucide-react";

function MetricCard({ icon: Icon, label, value, sub, color = "brand" }) {
  const colors = {
    brand:  { bg: "bg-brand-500/10", icon: "text-brand-400", border: "border-brand-500/20", gradient: "from-brand-500/5" },
    blue:   { bg: "bg-brand-500/10", icon: "text-brand-400", border: "border-brand-500/20", gradient: "from-brand-500/5" },
    red:    { bg: "bg-red-500/10",   icon: "text-red-400",   border: "border-red-500/20",  gradient: "from-red-500/5" },
    yellow: { bg: "bg-accent-500/10", icon: "text-accent-400", border: "border-accent-500/20", gradient: "from-accent-500/5" },
  };
  const c = colors[color];
  return (
    <div className={`card-gradient p-6 flex items-start gap-4 border ${c.border} bg-gradient-to-br ${c.gradient} to-transparent`}>
      <div className={`w-11 h-11 rounded-2xl ${c.bg} flex items-center justify-center shrink-0`}>
        <Icon size={20} className={c.icon} />
      </div>
      <div>
        <p className="text-xs text-content-muted mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-content">{value ?? "—"}</p>
        {sub && <p className="text-xs text-content-subtle mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState(null);
  const [ultimasVentas, setUltimasVentas] = useState([]);
  const [stockBajo, setStockBajo] = useState([]);
  const [promociones, setPromociones] = useState([]);
  const [anios, setAnios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dismissTasa, setDismissTasa] = useState(() => sessionStorage.getItem("dismissTasa") === "true");

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setLoading(true);
    try {
      const [dash, ventasHoy, stockBajoList, promos, years] = await Promise.all([
        api.get("/reportes/dashboard"),
        api.get("/ventas/resumen-dia").catch(() => null),
        api.get("/productos/stock-bajo").catch(() => []),
        api.get("/promociones/").catch(() => []),
        api.get("/organizacion/anios").catch(() => []),
      ]);
      setMetrics({
        total_productos: dash.total_productos,
        ventas_hoy: dash.resumen_dia?.total_ventas ?? 0,
        total_clientes: dash.total_clientes,
        alertas_stock: dash.stock_bajo,
      });
      setUltimasVentas(ventasHoy?.ultimas_ventas ?? []);
      setStockBajo(Array.isArray(stockBajoList) ? stockBajoList : []);
      setPromociones(Array.isArray(promos) ? promos.filter(p => p.activa) : []);
      setAnios(Array.isArray(years) ? years : []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const metodosPago = ultimasVentas.reduce((acc, v) => {
    const m = v.metodo_pago || "otro";
    acc[m] = (acc[m] || 0) + Number(v.total);
    return acc;
  }, {});

  const metodoInfo = {
    efectivo:      { label: "Efectivo",      icon: Banknote,    color: "text-secondary-400", bg: "bg-secondary-500/10", border: "border-secondary-500/20" },
    tarjeta:       { label: "Tarjeta",       icon: CreditCard,  color: "text-brand-400",     bg: "bg-brand-500/10",    border: "border-brand-500/20" },
    transferencia: { label: "Transferencia", icon: Wallet,      color: "text-accent-400",    bg: "bg-accent-500/10",   border: "border-accent-500/20" },
    credito:       { label: "Crédito",       icon: FileText,    color: "text-red-400",       bg: "bg-red-500/10",      border: "border-red-500/20" },
  };

  const anioActual = new Date().getFullYear();
  const currentYear = anios.find(a => a.anio === anioActual);
  const prevYear = anios.find(a => a.anio === anioActual - 1);
  const ingresosDiff = currentYear && prevYear
    ? ((currentYear.total_ingresos - prevYear.total_ingresos) / prevYear.total_ingresos * 100).toFixed(0)
    : null;

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-9 h-9 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-7 animate-fade-in">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Hola, <span className="text-content">{user?.usuario}</span>. Aquí está el resumen del día.</p>
        </div>
        <button onClick={cargar} className="btn-ghost flex items-center gap-2 text-sm">
          <RefreshCw size={15} /> Actualizar
        </button>
      </div>

      {/* Tasa de cambio notification */}
      {!user?.tasa_cambio_configurada && !dismissTasa && (
        <div className="card p-4 border border-accent-500/30 bg-gradient-to-r from-accent-500/5 to-transparent flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-accent-500/15 flex items-center justify-center shrink-0 mt-0.5">
            <DollarSign size={17} className="text-accent-400" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-content">Configura tu tasa de cambio</p>
            <p className="text-xs text-content-muted mt-0.5">
              Establece la tasa de cambio C$ / USD para que los precios se conviertan automáticamente a dólares.
              Puedes cambiarla en cualquier momento en Configuración.
            </p>
          </div>
          <button onClick={() => { setDismissTasa(true); sessionStorage.setItem("dismissTasa", "true"); }}
            className="shrink-0 text-content-muted hover:text-content transition-colors p-1">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Quick actions */}
      <div className="flex items-center gap-3 overflow-x-auto pb-1">
        <button onClick={() => navigate("/ventas")}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-500 transition-all duration-200 shadow-glow-sm hover:shadow-glow shrink-0">
          <Plus size={16} /> Nueva venta
        </button>
        <button onClick={() => navigate("/inventario")}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-surface-card border border-border text-content text-sm font-medium hover:bg-surface-hover transition-all duration-200 shrink-0">
          <Package size={16} /> Agregar producto
        </button>
        <button onClick={() => navigate("/clientes")}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-surface-card border border-border text-content text-sm font-medium hover:bg-surface-hover transition-all duration-200 shrink-0">
          <Users size={16} /> Nuevo cliente
        </button>
        <button onClick={() => navigate("/gesti")}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-surface-card border border-border text-content text-sm font-medium hover:bg-surface-hover transition-all duration-200 shrink-0">
          <Bot size={16} /> Preguntar a Gesti
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard icon={Package}       label="Total productos" value={metrics?.total_productos} sub="Registrados" />
        <MetricCard icon={TrendingUp}    label="Ventas hoy"     value={fmtMoney(metrics?.ventas_hoy)} sub="C$ acumulado hoy" />
        <MetricCard icon={Users}         label="Total clientes" value={metrics?.total_clientes} sub="Registrados" />
        <MetricCard icon={AlertTriangle} label="Stock bajo"     value={metrics?.alertas_stock} sub="Productos críticos" color="red" />
      </div>

      {/* Bottom row 1: tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-border/50">
            <h3 className="section-title">Últimas ventas</h3>
          </div>
          {ultimasVentas.length === 0
            ? <p className="text-sm text-content-subtle px-5 py-6">Sin ventas recientes.</p>
            : <table className="w-full">
                <thead>
                  <tr><th className="th">Cliente</th><th className="th">Hora</th><th className="th text-right">Total</th></tr>
                </thead>
                <tbody>
                  {ultimasVentas.map((v, i) => (
                    <tr key={i} className="table-row">
                      <td className="td">{v.cliente_nombre ?? v.cliente ?? "—"}</td>
                      <td className="td text-content-muted">{formatHora(v.fecha_hora ?? v.hora ?? v.fecha)}</td>
                      <td className="td text-right font-medium text-brand-400">{fmtMoney(v.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
          }
        </div>
        <div className="card">
          <div className="px-5 py-4 border-b border-border/50">
            <h3 className="section-title">Productos con stock bajo</h3>
          </div>
          {stockBajo.length === 0
            ? <p className="text-sm text-content-subtle px-5 py-6">Sin productos críticos.</p>
            : <div className="divide-y divide-border/40">
                {stockBajo.map((p, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-3.5 hover:bg-surface-hover transition-colors">
                    <span className="text-sm text-content truncate">{p.nombre}</span>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      <span className="badge-red">{p.stock} u.</span>
                    </div>
                  </div>
                ))}
              </div>
          }
        </div>
      </div>

      {/* Bottom row 2: metodos pago + promociones + resumen año */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Métodos de pago hoy */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <CreditCard size={15} className="text-content-muted" />
            <h3 className="text-sm font-semibold text-content">Métodos de pago hoy</h3>
          </div>
          {Object.keys(metodosPago).length === 0
            ? <p className="text-sm text-content-subtle">Sin ventas hoy.</p>
            : <div className="space-y-3">
                {Object.entries(metodosPago).map(([metodo, total]) => {
                  const info = metodoInfo[metodo] || { label: metodo, icon: Banknote, color: "text-content-muted", bg: "bg-surface-hover", border: "border-border" };
                  const Icon = info.icon;
                  return (
                    <div key={metodo} className={`flex items-center justify-between p-3 rounded-xl ${info.bg} border ${info.border}`}>
                      <div className="flex items-center gap-2.5">
                        <Icon size={16} className={info.color} />
                        <span className="text-sm text-content">{info.label}</span>
                      </div>
                      <span className={`text-sm font-semibold ${info.color}`}>{fmtMoney(total)}</span>
                    </div>
                  );
                })}
              </div>
          }
        </div>

        {/* Promociones activas */}
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <BadgePercent size={15} className="text-content-muted" />
            <h3 className="text-sm font-semibold text-content">Promociones activas</h3>
          </div>
          {promociones.length === 0
            ? <p className="text-sm text-content-subtle">No hay promociones activas.</p>
            : <div className="space-y-2">
                {promociones.map(p => (
                  <div key={p.id} className="flex items-center justify-between p-3 rounded-xl bg-accent-500/5 border border-accent-500/20">
                    <div className="flex items-center gap-2.5">
                      <Tag size={14} className="text-accent-400" />
                      <span className="text-sm text-content">{p.nombre}</span>
                    </div>
                    <span className="text-xs font-semibold text-accent-400">
                      {p.tipo === "porcentaje" ? `${p.valor}%` : p.tipo === "monto_fijo" ? `C$${p.valor}` : p.tipo === "2x1" ? "2x1" : p.tipo}
                    </span>
                  </div>
                ))}
              </div>
          }
          <button onClick={() => navigate("/promociones")}
            className="mt-3 w-full text-xs text-content-muted hover:text-content text-center py-2 rounded-lg hover:bg-surface-hover transition-all duration-200">
            Gestionar promociones
          </button>
        </div>

        {/* Resumen del año */}
        <div className="card p-5 bg-gradient-to-br from-brand-500/[0.03] to-transparent">
          <div className="flex items-center gap-2 mb-4">
            <Calendar size={15} className="text-content-muted" />
            <h3 className="text-sm font-semibold text-content">{anioActual}</h3>
          </div>
          {currentYear
            ? <div className="space-y-3">
                <div className="flex items-center justify-between py-2 border-b border-border/40">
                  <span className="text-sm text-content-muted">Ingresos totales</span>
                  <span className="text-sm font-bold text-content">{fmtMoney(currentYear.total_ingresos)}</span>
                </div>
                <div className="flex items-center justify-between py-2">
                  <span className="text-sm text-content-muted">Ventas realizadas</span>
                  <span className="text-sm font-semibold text-content">{currentYear.total_ventas}</span>
                </div>
                {ingresosDiff && (
                  <div className={`flex items-center gap-1.5 text-xs ${Number(ingresosDiff) >= 0 ? "text-secondary-400" : "text-red-400"}`}>
                    {Number(ingresosDiff) >= 0 ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                    <span>{Math.abs(ingresosDiff)}% vs año anterior</span>
                  </div>
                )}
              </div>
            : <p className="text-sm text-content-subtle">Sin datos de {anioActual}.</p>
          }
          <button onClick={() => navigate("/organizacion")}
            className="mt-3 w-full text-xs text-content-muted hover:text-content text-center py-2 rounded-lg hover:bg-surface-hover transition-all duration-200">
            Ver detalle completo
          </button>
        </div>
      </div>
    </div>
  );
}
