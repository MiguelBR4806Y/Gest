import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, RefreshCw, Send, Sparkles, Trash2 } from "lucide-react";

import { Button, IconButton } from "../components/ui/Button";
import { Card, CardHeader, EmptyState } from "../components/ui/Card";
import { Input } from "../components/ui/Field";
import { useToast } from "../context/ToastContext";
import { api, fmtMoney } from "../lib/api";

const SUGERENCIAS = [
  "¿Cuál es mi producto más vendido?",
  "¿Qué días tengo más ventas?",
  "¿Cuánto vendí este mes?",
  "¿Qué cliente compra más seguido?",
];

function Burbuja({ role, texto }) {
  const esUsuario = role === "user";
  return (
    <li className={`flex gap-2.5 ${esUsuario ? "flex-row-reverse" : ""}`}>
      <span
        className={`w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold ${
          esUsuario
            ? "bg-brand-600"
            : "bg-surface-elevated text-content-muted border border-border"
        }`}
        style={esUsuario ? { color: "rgb(var(--brand-contrast, 255 255 255))" } : undefined}
        aria-hidden="true"
      >
        {esUsuario ? "Tú" : "G"}
      </span>
      <p
        className={`max-w-[85%] text-sm px-3.5 py-2.5 rounded-2xl leading-relaxed whitespace-pre-wrap break-words ${
          esUsuario
            ? "bg-brand-500/15 text-content rounded-tr-sm"
            : "bg-surface-elevated text-content rounded-tl-sm"
        }`}
      >
        {texto}
      </p>
    </li>
  );
}

export default function GestiPage() {
  const { toast } = useToast();

  const [predictivos, setPredictivos] = useState(null);
  const [chat, setChat] = useState([]);
  const [pregunta, setPregunta] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const refChat = useRef(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const pred = await api.get("/reportes/predictivos").catch(() => null);
      if (pred) {
        setPredictivos({
          reabastecer: pred.reabastecer ?? [],
          mejoresDias: (pred.dias_semana ?? []).map((d) => ({ dia: d.dia, total: d.total_ventas })),
          proyeccion: pred.proyeccion?.proyeccion_7_dias ?? null,
          promedioDiario: pred.proyeccion?.promedio_diario ?? null,
        });
      }
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [toast]);

  useEffect(() => {
    api
      .get("/reportes/chat/historial")
      .then((d) => setChat(Array.isArray(d) ? d : []))
      .catch(() => {});
    cargar();
  }, [cargar]);

  useEffect(() => {
    const el = refChat.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [chat, enviando]);

  async function enviar(texto) {
    const q = (texto ?? pregunta).trim();
    if (!q || enviando) return;

    setPregunta("");
    setChat((c) => [...c, { role: "user", text: q }]);
    setEnviando(true);

    try {
      const data = await api.post("/reportes/chat", { pregunta: q });
      setChat((c) => [...c, { role: "ai", text: data.respuesta ?? "Sin respuesta." }]);
    } catch (e) {
      setChat((c) => [...c, { role: "ai", text: `No pude responder: ${e.message}` }]);
    } finally {
      setEnviando(false);
    }
  }

  // Sin guarda, un fallo al cargar los predictivos dejaba `predictivos` en null
  // y el render de abajo reventaba al leer sus propiedades.
  const sinDatos =
    !predictivos || (!predictivos.proyeccion && predictivos.reabastecer.length === 0);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-500/10 flex items-center justify-center shrink-0">
            <Bot size={20} className="text-brand-600 dark:text-brand-300" aria-hidden="true" />
          </div>
          <div>
            <h1>Gesti</h1>
            <p>Tu asistente: preguntas, predicciones y análisis de tu negocio</p>
          </div>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} onClick={cargar} loading={cargando}>
          Actualizar
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <Card className="flex flex-col overflow-hidden">
            <CardHeader
              title="Pregúntale a Gesti"
              subtitle="Conoce tu inventario, clientes y ventas"
              icon={Bot}
              action={
                chat.length > 0 && (
                  <IconButton
                    label="Limpiar conversación"
                    icon={Trash2}
                    onClick={() => setChat([])}
                  />
                )
              }
            />

            <div
              ref={refChat}
              className="flex-1 max-h-[28rem] overflow-y-auto p-5 space-y-3 scroll-smooth"
            >
              {chat.length === 0 && !enviando ? (
                <EmptyState
                  icon={Sparkles}
                  title="Empieza la conversación"
                  text="Pregúntale lo que quieras sobre tus ventas, tu inventario o tus clientes."
                />
              ) : (
                <ul className="space-y-3">
                  {chat.map((m, i) => (
                    <Burbuja key={m.id ?? i} role={m.role} texto={m.text} />
                  ))}
                  {enviando && (
                    <li className="flex gap-2.5">
                      <span className="w-7 h-7 rounded-full bg-surface-elevated border border-border flex items-center justify-center text-[10px] text-content-muted" aria-hidden="true">
                        G
                      </span>
                      <span
                        className="bg-surface-elevated px-4 py-3 rounded-2xl rounded-tl-sm"
                        role="status"
                        aria-label="Gesti está escribiendo"
                      >
                        <span className="flex gap-1">
                          {[0, 1, 2].map((i) => (
                            <span
                              key={i}
                              className="w-1.5 h-1.5 rounded-full bg-content-muted/50 animate-bounce"
                              style={{ animationDelay: `${i * 150}ms` }}
                            />
                          ))}
                        </span>
                      </span>
                    </li>
                  )}
                </ul>
              )}
            </div>

            <div className="p-4 border-t border-border/60 flex gap-2">
              <Input
                placeholder="Escribe tu pregunta…"
                value={pregunta}
                onChange={(e) => setPregunta(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    enviar();
                  }
                }}
                aria-label="Pregunta para Gesti"
                disabled={enviando}
              />
              <Button
                onClick={() => enviar()}
                disabled={!pregunta.trim()}
                loading={enviando}
                aria-label="Enviar pregunta"
                className="shrink-0"
              >
                <Send size={15} aria-hidden="true" />
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Predicciones" icon={Sparkles} />
            <div className="p-5">
              {cargando ? (
                <p className="text-sm text-content-subtle">Analizando…</p>
              ) : sinDatos ? (
                <p className="text-sm text-content-subtle">
                  Necesitas registrar ventas para ver predicciones.
                </p>
              ) : (
                <div className="space-y-5">
                  <div>
                    <p className="text-xs font-semibold text-content-subtle uppercase tracking-wide mb-1">
                      Proyección 7 días
                    </p>
                    {predictivos.proyeccion ? (
                      <p className="text-xl font-bold tabular">{fmtMoney(predictivos.proyeccion)}</p>
                    ) : (
                      <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
                    )}
                    {predictivos.promedioDiario > 0 && (
                      <p className="text-xs text-content-subtle mt-0.5">
                        Promedio diario {fmtMoney(predictivos.promedioDiario)}
                      </p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-content-subtle uppercase tracking-wide mb-2">
                      Reabastecer pronto
                    </p>
                    {predictivos.reabastecer.length > 0 ? (
                      <ul className="space-y-1.5">
                        {predictivos.reabastecer.map((p, i) => (
                          <li key={i} className="flex items-center justify-between gap-2 py-1">
                            <span className="text-sm text-content truncate">{p.nombre}</span>
                            <span className="badge-red shrink-0">
                              {p.dias_restantes <= 0 ? "Agotado" : `${p.dias_restantes} d`}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-content-subtle">Sin alertas por ahora.</p>
                    )}
                  </div>

                  <div>
                    <p className="text-xs font-semibold text-content-subtle uppercase tracking-wide mb-2">
                      Mejores días
                    </p>
                    {predictivos.mejoresDias.length > 0 ? (
                      <ul className="space-y-1.5">
                        {predictivos.mejoresDias.slice(0, 4).map((d, i) => (
                          <li key={i} className="flex items-center justify-between gap-2 py-1">
                            <span className="text-sm text-content">{d.dia}</span>
                            <span className="text-sm font-medium tabular text-brand-600 dark:text-brand-300">
                              {fmtMoney(d.total)}
                            </span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-content-subtle">Sin datos suficientes.</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card>
            <CardHeader title="Preguntas sugeridas" />
            <div className="p-3">
              <ul className="space-y-1">
                {SUGERENCIAS.map((s) => (
                  <li key={s}>
                    <button
                      type="button"
                      onClick={() => enviar(s)}
                      disabled={enviando}
                      className="w-full text-left text-sm text-content-muted hover:text-content px-3 py-2
                                 rounded-lg hover:bg-surface-hover transition-colors disabled:opacity-50"
                    >
                      {s}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
