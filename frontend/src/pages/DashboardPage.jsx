import { useState, useEffect, useRef } from "react";
import { api, formatHora, fmtMoney } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Package, TrendingUp, Users, TriangleAlert as AlertTriangle, Send, Trash2, Bot, CircleAlert as AlertCircle, RefreshCw } from "lucide-react";

function MetricCard({ icon: Icon, label, value, sub, color = "brand" }) {
  const colors = {
    brand:  { bg: "bg-brand-900/30",   icon: "text-brand-400",  border: "border-brand-800/40" },
    red:    { bg: "bg-red-900/30",     icon: "text-red-400",    border: "border-red-800/40" },
    blue:   { bg: "bg-blue-900/30",    icon: "text-blue-400",   border: "border-blue-800/40" },
    yellow: { bg: "bg-yellow-900/30",  icon: "text-yellow-400", border: "border-yellow-800/40" },
  };
  const c = colors[color];
  return (
    <div className={`card p-5 flex items-start gap-4 border ${c.border}`}>
      <div className={`w-10 h-10 rounded-xl ${c.bg} flex items-center justify-center shrink-0`}>
        <Icon size={20} className={c.icon} />
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-0.5">{label}</p>
        <p className="text-2xl font-bold text-gray-100">{value ?? "—"}</p>
        {sub && <p className="text-xs text-gray-500 mt-0.5">{sub}</p>}
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
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Hola, <span className="text-gray-300">{user?.usuario}</span>. Aquí está el resumen del día.</p>
        </div>
        <button onClick={cargar} className="btn-ghost flex items-center gap-2 text-sm">
          <RefreshCw size={15} /> Actualizar
        </button>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard icon={Package}        label="Total productos"  value={metrics?.total_productos}   sub="Registrados"         color="brand"  />
        <MetricCard icon={TrendingUp}     label="Ventas hoy"       value={fmtMoney(metrics?.ventas_hoy)} sub="C$ acumulado hoy" color="blue"  />
        <MetricCard icon={Users}          label="Total clientes"   value={metrics?.total_clientes}    sub="Registrados"         color="brand"  />
        <MetricCard icon={AlertTriangle}  label="Stock bajo"       value={metrics?.alertas_stock}     sub="Productos críticos"  color="red"    />
      </div>

      {/* IA Análisis */}
      {iaAnalisis && (
        <div className="card p-5 border border-brand-800/40 bg-brand-900/10">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-brand-600/20 flex items-center justify-center shrink-0 mt-0.5">
              <Bot size={16} className="text-brand-400" />
            </div>
            <div>
              <p className="text-xs font-semibold text-brand-400 mb-1">Análisis IA del día</p>
              <p className="text-sm text-gray-300 leading-relaxed">{iaAnalisis}</p>
            </div>
          </div>
        </div>
      )}

      {/* Predictivos */}
      {predictivos && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="card p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Reabastecer pronto</p>
            <p className="text-xs text-gray-600 mb-3">Productos que se agotan en menos de 14 días</p>
            {predictivos.reabastecer?.length > 0
              ? predictivos.reabastecer.map((p, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0">
                    <span className="text-sm text-gray-300 truncate">{p.nombre}</span>
                    <span className="badge-red ml-2 shrink-0">{p.dias_restantes}d</span>
                  </div>
                ))
              : <p className="text-sm text-gray-600">Sin alertas por ahora.</p>
            }
          </div>
          <div className="card p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Días de mayor venta</p>
            <p className="text-xs text-gray-600 mb-3">Ranking histórico por día de la semana</p>
            {predictivos.mejores_dias?.length > 0
              ? predictivos.mejores_dias.map((d, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0">
                    <span className="text-sm text-gray-300">{d.dia}</span>
                    <span className="text-sm font-medium text-brand-400">{fmtMoney(d.total)}</span>
                  </div>
                ))
              : <p className="text-sm text-gray-600">Sin datos suficientes.</p>
            }
          </div>
          <div className="card p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">Proyección 7 días</p>
            <p className="text-xs text-gray-600 mb-3">Estimación basada en los últimos 30 días</p>
            {predictivos.proyeccion
              ? <p className="text-2xl font-bold text-gray-100">{fmtMoney(predictivos.proyeccion)}</p>
              : <p className="text-sm text-gray-600">Sin datos suficientes.</p>
            }
          </div>
        </div>
      )}

      {/* Chat IA */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Bot size={18} className="text-brand-400" />
            <h3 className="text-sm font-semibold text-gray-200">Pregúntale a la IA sobre tu negocio</h3>
          </div>
          {chat.length > 0 && (
            <button onClick={() => setChat([])} className="btn-ghost text-xs flex items-center gap-1 text-gray-500 hover:text-red-400">
              <Trash2 size={13} /> Limpiar
            </button>
          )}
        </div>
        {chat.length > 0 && (
          <div ref={chatRef} className="bg-gray-950 rounded-xl p-3 mb-4 space-y-3 max-h-72 overflow-y-auto">
            {chat.map((m, i) => (
              <div key={i} className={`flex gap-2 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ` +
                  (m.role === "user" ? "bg-brand-600 text-white" : "bg-gray-700 text-gray-300")}>
                  {m.role === "user" ? "Tú" : "IA"}
                </div>
                <div className={`max-w-[80%] text-sm px-3 py-2 rounded-xl leading-relaxed ` +
                  (m.role === "user" ? "bg-brand-600/20 text-gray-100 rounded-tr-sm" : "bg-gray-800 text-gray-300 rounded-tl-sm")}>
                  {m.text}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="flex gap-2">
                <div className="w-7 h-7 rounded-full bg-gray-700 flex items-center justify-center text-xs text-gray-300">IA</div>
                <div className="bg-gray-800 px-3 py-2 rounded-xl rounded-tl-sm">
                  <div className="flex gap-1">
                    {[0,1,2].map(i => <div key={i} className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: `${i*150}ms` }} />)}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
        <div className="flex gap-2">
          <input className="input flex-1" placeholder="Ej: ¿Cuál es mi producto más vendido?"
            value={pregunta} onChange={e => setPregunta(e.target.value)}
            onKeyDown={e => e.key === "Enter" && enviarPregunta()} />
          <button onClick={enviarPregunta} disabled={chatLoading || !pregunta.trim()}
            className="btn-primary px-4 flex items-center gap-2">
            <Send size={16} />
          </button>
        </div>
      </div>

      {/* Bottom tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <div className="px-5 py-4 border-b border-gray-800">
            <h3 className="text-sm font-semibold text-gray-200">Últimas ventas</h3>
          </div>
          {ultimasVentas.length === 0
            ? <p className="text-sm text-gray-600 px-5 py-6">Sin ventas recientes.</p>
            : <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Cliente</th>
                    <th className="th">Hora</th>
                    <th className="th text-right">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {ultimasVentas.map((v, i) => (
                    <tr key={i} className="table-row">
                      <td className="td">{v.cliente_nombre ?? v.cliente ?? "—"}</td>
                      <td className="td text-gray-500">{formatHora(v.fecha_hora ?? v.hora ?? v.fecha)}</td>
                      <td className="td text-right font-medium text-brand-400">{fmtMoney(v.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
          }
        </div>
        <div className="card">
          <div className="px-5 py-4 border-b border-gray-800">
            <h3 className="text-sm font-semibold text-gray-200">Productos con stock bajo</h3>
          </div>
          {stockBajo.length === 0
            ? <p className="text-sm text-gray-600 px-5 py-6">Sin productos críticos.</p>
            : <div className="divide-y divide-gray-800">
                {stockBajo.map((p, i) => (
                  <div key={i} className="flex items-center justify-between px-5 py-3 hover:bg-gray-800/40 transition-colors">
                    <span className="text-sm text-gray-300 truncate">{p.nombre}</span>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      <span className="badge-red">{p.stock} u.</span>
                      <AlertCircle size={14} className="text-red-400" />
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
