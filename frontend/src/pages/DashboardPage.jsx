import { useState, useEffect, useRef } from "react";
import { api, formatHora, fmtMoney } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Package, TrendingUp, Users, TriangleAlert as AlertTriangle, Send, Trash2, Bot, RefreshCw, Sparkles, DollarSign, X } from "lucide-react";

function MetricCard({ icon: Icon, label, value, sub, color = "brand" }) {
  const colors = {
    brand:  { bg: "bg-brand-500/10", icon: "text-brand-400", border: "border-brand-500/20", gradient: "from-brand-500/5" },
    blue:   { bg: "bg-brand-500/10", icon: "text-brand-400", border: "border-brand-500/20", gradient: "from-brand-500/5" },
    red:    { bg: "bg-red-500/10",   icon: "text-red-400",   border: "border-red-500/20",  gradient: "from-red-500/5" },
    yellow: { bg: "bg-accent-500/10", icon: "text-accent-400", border: "border-accent-500/20", gradient: "from-accent-500/5" },
  };
  const c = colors[color];
  return (
    <div className={`card-gradient p-5 flex items-start gap-4 border ${c.border} bg-gradient-to-br ${c.gradient} to-transparent`}>
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
  const [metrics, setMetrics] = useState(null);
  const [predictivos, setPredictivos] = useState(null);
  const [ultimasVentas, setUltimasVentas] = useState([]);
  const [stockBajo, setStockBajo] = useState([]);
  const [iaAnalisis, setIaAnalisis] = useState("");
  const [chat, setChat] = useState([]);
  const [pregunta, setPregunta] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dismissTasa, setDismissTasa] = useState(() => sessionStorage.getItem("dismissTasa") === "true");
  const chatRef = useRef(null);

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setLoading(true);
    try {
      const [dash, pred, ventasHoy, stockBajoList] = await Promise.all([
        api.get("/reportes/dashboard"),
        api.get("/reportes/predictivos").catch(() => null),
        api.get("/ventas/resumen-dia").catch(() => null),
        api.get("/productos/stock-bajo").catch(() => []),
      ]);
      setMetrics({
        total_productos: dash.total_productos,
        ventas_hoy: dash.resumen_dia?.total_ventas ?? 0,
        total_clientes: dash.total_clientes,
        alertas_stock: dash.stock_bajo,
      });
      setUltimasVentas(ventasHoy?.ultimas_ventas ?? []);
      setStockBajo(Array.isArray(stockBajoList) ? stockBajoList : []);
      setIaAnalisis("");
      if (pred) {
        setPredictivos({
          reabastecer: pred.reabastecer ?? [],
          mejores_dias: (pred.dias_semana ?? []).map(d => ({ dia: d.dia, total: d.total_ventas })),
          proyeccion: pred.proyeccion?.proyeccion_7_dias ?? null,
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function enviarPregunta() {
    if (!pregunta.trim() || chatLoading) return;
    const q = pregunta.trim();
    setPregunta("");
    setChat(c => [...c, { role: "user", text: q }]);
    setChatLoading(true);
    try {
      const data = await api.post("/reportes/chat", { pregunta: q });
      setChat(c => [...c, { role: "ai", text: data.respuesta ?? "Sin respuesta" }]);
    } catch (e) {
      setChat(c => [...c, { role: "ai", text: "Error al consultar la IA: " + e.message }]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatRef.current?.scrollTo({ top: 99999, behavior: "smooth" }), 50);
    }
  }

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

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard icon={Package}       label="Total productos" value={metrics?.total_productos} sub="Registrados" />
        <MetricCard icon={TrendingUp}    label="Ventas hoy"     value={fmtMoney(metrics?.ventas_hoy)} sub="C$ acumulado hoy" />
        <MetricCard icon={Users}         label="Total clientes" value={metrics?.total_clientes} sub="Registrados" />
        <MetricCard icon={AlertTriangle} label="Stock bajo"     value={metrics?.alertas_stock} sub="Productos críticos" color="red" />
      </div>

      {/* IA Análisis */}
      {iaAnalisis && (
        <div className="card p-5 border border-brand-500/20 bg-gradient-to-r from-brand-500/5 to-transparent">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-500/15 flex items-center justify-center shrink-0 mt-0.5">
              <Bot size={17} className="text-brand-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-brand-400 mb-1">Análisis IA del día</p>
              <p className="text-sm text-content leading-relaxed">{iaAnalisis}</p>
            </div>
          </div>
        </div>
      )}

      {/* Predictivos */}
      {predictivos && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="card p-5">
            <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-3">Reabastecer pronto</p>
            <p className="text-xs text-content-subtle mb-3">Productos que se agotan en menos de 14 días</p>
            {predictivos.reabastecer?.length > 0
              ? predictivos.reabastecer.map((p, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/40 last:border-0">
                    <span className="text-sm text-content truncate">{p.nombre}</span>
                    <span className="badge-red ml-2 shrink-0">{p.dias_restantes}d</span>
                  </div>
                ))
              : <p className="text-sm text-content-subtle">Sin alertas por ahora.</p>
            }
          </div>
          <div className="card p-5">
            <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-3">Días de mayor venta</p>
            <p className="text-xs text-content-subtle mb-3">Ranking histórico por día de la semana</p>
            {predictivos.mejores_dias?.length > 0
              ? predictivos.mejores_dias.map((d, i) => (
                  <div key={i} className="flex items-center justify-between py-2 border-b border-border/40 last:border-0">
                    <span className="text-sm text-content">{d.dia}</span>
                    <span className="text-sm font-medium text-brand-400">{fmtMoney(d.total)}</span>
                  </div>
                ))
              : <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
            }
          </div>
          <div className="card p-5 bg-gradient-to-br from-brand-500/[0.03] to-transparent">
            <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-3">Proyección 7 días</p>
            <p className="text-xs text-content-subtle mb-3">Estimación basada en los últimos 30 días</p>
            {predictivos.proyeccion
              ? <div>
                  <p className="text-3xl font-bold text-content">{fmtMoney(predictivos.proyeccion)}</p>
                  <div className="flex items-center gap-1.5 mt-1">
                    <Sparkles size={12} className="text-accent-400" />
                    <span className="text-xs text-accent-400">Predicción IA</span>
                  </div>
                </div>
              : <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
            }
          </div>
        </div>
      )}

      {/* Chat IA */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500/20 to-secondary-500/20 flex items-center justify-center">
              <Bot size={18} className="text-brand-400" />
            </div>
            <h3 className="text-sm font-semibold text-content">Pregúntale a la IA sobre tu negocio</h3>
          </div>
          {chat.length > 0 && (
            <button onClick={() => setChat([])} className="btn-ghost text-xs flex items-center gap-1.5 text-content-muted hover:text-red-400">
              <Trash2 size={13} /> Limpiar
            </button>
          )}
        </div>
        {chat.length > 0 && (
          <div ref={chatRef} className="bg-surface rounded-2xl p-4 mb-4 space-y-3 max-h-80 overflow-y-auto border border-border/40">
            {chat.map((m, i) => (
              <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
                  m.role === "user" ? "bg-gradient-to-br from-brand-500 to-secondary-500 text-white" : "bg-gray-700 text-content"
                }`}>
                  {m.role === "user" ? "Tú" : "IA"}
                </div>
                <div className={`max-w-[80%] text-sm px-4 py-2.5 rounded-2xl leading-relaxed ${
                  m.role === "user" ? "bg-brand-500/15 text-content" : "bg-surface-elevated/60 text-content"
                }`}>
                  {m.text}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex gap-2.5">
                <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center text-xs text-content">IA</div>
                <div className="bg-surface-elevated/60 px-4 py-3 rounded-2xl">
                  <div className="flex gap-1.5">
                    {[0,1,2].map(i => <div key={i} className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: `${i*150}ms` }} />)}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex gap-2.5">
          <input className="input flex-1" placeholder="Ej: ¿Cuál es mi producto más vendido?"
            value={pregunta} onChange={e => setPregunta(e.target.value)}
            onKeyDown={e => e.key === "Enter" && enviarPregunta()} />
          <button onClick={enviarPregunta} disabled={chatLoading || !pregunta.trim()}
            className="btn-primary px-5 flex items-center gap-2">
            <Send size={16} />
          </button>
        </div>
      </div>

      {/* Bottom tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-border/50">
            <h3 className="text-sm font-semibold text-content">Últimas ventas</h3>
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
            <h3 className="text-sm font-semibold text-content">Productos con stock bajo</h3>
          </div>
          {stockBajo.length === 0
            ? <p className="text-sm text-content-subtle px-5 py-6">Sin productos críticos.</p>
            : <div className="divide-y divide-border/40">
                {stockBajo.map((p, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-3.5 hover:bg-white/[0.02] transition-colors">
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
    </div>
  );
}
