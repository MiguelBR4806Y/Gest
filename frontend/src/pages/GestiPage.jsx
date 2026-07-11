import { useState, useEffect, useRef } from "react";
import { api, fmtMoney } from "../lib/api";
import { Bot, Send, Trash2, Sparkles, RefreshCw } from "lucide-react";

export default function GestiPage() {
  const [predictivos, setPredictivos] = useState(null);
  const [iaAnalisis, setIaAnalisis] = useState("");
  const [chat, setChat] = useState([]);
  const [pregunta, setPregunta] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const chatRef = useRef(null);

  useEffect(() => { cargar(); cargarHistorial(); }, []);

  async function cargarHistorial() {
    try {
      const data = await api.get("/reportes/chat/historial");
      setChat(data ?? []);
    } catch {}
  }

  async function cargar() {
    setLoading(true);
    try {
      const [pred] = await Promise.all([
        api.get("/reportes/predictivos").catch(() => null),
      ]);
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
      const respuesta = data.respuesta ?? "Sin respuesta";
      setChat(c => [...c, { role: "ai", text: respuesta }]);
      setIaAnalisis(respuesta);
    } catch (e) {
      setChat(c => [...c, { role: "ai", text: "Error al consultar a Gesti: " + e.message }]);
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
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-brand-500/20 to-secondary-500/20 flex items-center justify-center">
            <Bot size={22} className="text-brand-400" />
          </div>
          <div>
            <h1>Gesti</h1>
            <p>Tu asistente IA — preguntas, predicciones y análisis de tu negocio</p>
          </div>
        </div>
        <button onClick={cargar} className="btn-ghost flex items-center gap-2 text-sm">
          <RefreshCw size={15} /> Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chat */}
        <div className="lg:col-span-2">
          <div className="card-accent p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500/20 to-secondary-500/20 flex items-center justify-center">
                  <Bot size={18} className="text-brand-400" />
                </div>
                <div>
                  <h3 className="section-title">Pregúntale a Gesti</h3>
                  <p className="text-xs text-content-muted mt-0.5">✨ Gesti · Tu asistente IA amigable</p>
                </div>
              </div>
              {chat.length > 0 && (
                <button onClick={() => setChat([])} className="btn-ghost text-xs flex items-center gap-1.5 text-content-muted hover:text-red-400">
                  <Trash2 size={13} /> Limpiar
                </button>
              )}
            </div>
            {chat.length > 0 && (
              <div ref={chatRef} className="bg-surface rounded-2xl p-4 mb-4 space-y-3 max-h-96 overflow-y-auto border border-border/40">
                {chat.map((m, i) => (
                  <div key={i} className={`flex gap-2.5 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                    <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center text-xs font-bold ${
                      m.role === "user" ? "bg-gradient-to-br from-brand-500 to-secondary-500 text-white" : "bg-surface-elevated text-content-muted"
                    }`}>
                      {m.role === "user" ? "Tú" : "Gesti"}
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
                    <div className="w-8 h-8 rounded-full bg-surface-elevated flex items-center justify-center text-xs text-content-muted">Gesti</div>
                    <div className="bg-surface-elevated/60 px-4 py-3 rounded-2xl">
                      <div className="flex gap-1.5">
                        {[0,1,2].map(i => <div key={i} className="w-2 h-2 bg-content-muted/40 rounded-full animate-bounce" style={{ animationDelay: `${i*150}ms` }} />)}
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

          {/* IA Análisis */}
          {iaAnalisis && (
            <div className="card p-5 border border-brand-500/20 bg-gradient-to-r from-brand-500/5 to-transparent mt-4">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-xl bg-brand-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot size={17} className="text-brand-400" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-brand-400 mb-1">Último análisis de Gesti</p>
                  <p className="text-sm text-content leading-relaxed">{iaAnalisis}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Predictivos sidebar */}
        <div className="space-y-4">
          <div className="card-accent p-5">
            <div className="flex items-center gap-2.5 mb-4">
              <Sparkles size={16} className="text-accent-400" />
              <h3 className="text-sm font-semibold text-content">Predicciones</h3>
            </div>
            {predictivos ? (
              <div className="space-y-4">
                <div>
                  <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-2">Proyección 7 días</p>
                  {predictivos.proyeccion
                    ? <p className="text-2xl font-bold text-content">{fmtMoney(predictivos.proyeccion)}</p>
                    : <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
                  }
                </div>
                <div>
                  <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-2">Reabastecer pronto</p>
                  {predictivos.reabastecer?.length > 0
                    ? predictivos.reabastecer.map((p, i) => (
                        <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                          <span className="text-sm text-content truncate">{p.nombre}</span>
                          <span className="badge-red ml-2 shrink-0">{p.dias_restantes}d</span>
                        </div>
                      ))
                    : <p className="text-sm text-content-subtle">Sin alertas por ahora.</p>
                  }
                </div>
                <div>
                  <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-2">Mejores días</p>
                  {predictivos.mejores_dias?.length > 0
                    ? predictivos.mejores_dias.map((d, i) => (
                        <div key={i} className="flex items-center justify-between py-1.5 border-b border-border/40 last:border-0">
                          <span className="text-sm text-content">{d.dia}</span>
                          <span className="text-sm font-medium text-brand-400">{fmtMoney(d.total)}</span>
                        </div>
                      ))
                    : <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
                  }
                </div>
              </div>
            ) : (
              <p className="text-sm text-content-subtle">No hay datos de predicción disponibles.</p>
            )}
          </div>

          {/* Sugerencias */}
          <div className="card p-5">
            <p className="text-xs font-semibold text-content-muted uppercase tracking-wider mb-3">Preguntas sugeridas</p>
            <div className="space-y-2">
              {[
                "¿Cuál es mi producto más vendido?",
                "¿Qué días tengo más ventas?",
                "¿Cuánto vendí este mes?",
              ].map((sug, i) => (
                <button key={i} onClick={() => { setPregunta(sug); }}
                  className="w-full text-left text-sm text-content-muted hover:text-content px-3 py-2 rounded-lg hover:bg-surface-hover transition-all duration-200">
                  {sug}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
