import { useState, useEffect, useCallback } from "react";
import { api, fmtMoney, formatHora } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { ChevronRight, Download, ArrowLeft, FolderOpen, FileText, Eye } from "lucide-react";

const MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];

function PeriodCard({ label, ventas, ingresos, onClick, disabled }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`card p-5 text-center flex flex-col items-center gap-2.5 transition-all duration-200 w-full
        ${disabled ? "opacity-40 cursor-not-allowed" : "hover:bg-surface-hover40 hover:border-border/60 cursor-pointer active:scale-[0.97]"}`}
    >
      <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${disabled ? "bg-surface-hover" : "bg-brand-500/10"}`}>
        <FolderOpen size={28} className={disabled ? "text-content-subtle" : "text-brand-400"} />
      </div>
      <p className="text-sm font-semibold text-content">{label}</p>
      {!disabled ? (
        <>
          <p className="text-2xl font-bold text-brand-400">{ventas}</p>
          <p className="text-xs text-content-muted">{ventas === 1 ? "factura" : "facturas"}</p>
          {ingresos > 0 && <p className="text-xs text-secondary-400 font-medium">{fmtMoney(ingresos)}</p>}
        </>
      ) : (
        <p className="text-xs text-content-subtle">Sin facturas</p>
      )}
    </button>
  );
}

export default function OrganizacionPage() {
  const { user } = useAuth();

  const [state, setState] = useState({
    nivel: "anios", anio: null, semestre: null, trimestre: null, mes: null, semana: null, dia: null,
  });
  const [items, setItems] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [vistaFacturas, setVistaFacturas] = useState(false);
  const [tituloFacturas, setTituloFacturas] = useState("");

  const cargar = useCallback(async () => {
    setLoading(true);
    setItems([]);
    try {
      let data;
      switch (state.nivel) {
        case "anios":
          data = await api.get("/organizacion/anios");
          setItems(data.anios.map(a => ({ key: a.anio, label: String(a.anio), ventas: a.total_ventas, ingresos: a.total_ingresos })));
          break;
        case "semestres":
          data = await api.get(`/organizacion/${state.anio}/semestres`);
          setItems(data.semestres.map(s => ({ key: s.semestre, label: s.label, ventas: s.total_ventas, ingresos: s.total_ingresos })));
          break;
        case "trimestres":
          data = await api.get(`/organizacion/${state.anio}/${state.semestre}/trimestres`);
          setItems(data.trimestres.map(t => ({ key: t.trimestre, label: t.label, ventas: t.total_ventas, ingresos: t.total_ingresos })));
          break;
        case "meses":
          data = await api.get(`/organizacion/${state.anio}/${state.trimestre}/meses`);
          setItems(data.meses.map(m => ({ key: m.mes, label: m.label, ventas: m.total_ventas, ingresos: m.total_ingresos })));
          break;
        case "semanas":
          data = await api.get(`/organizacion/${state.anio}/${state.mes}/semanas`);
          setItems(data.semanas.map(s => ({ key: s.inicio_semana, label: s.label, ventas: s.total_ventas, ingresos: s.total_ingresos })));
          break;
        case "dias":
          data = await api.get(`/organizacion/${state.anio}/${state.mes}/${state.semana}/dias`);
          setItems(data.dias.map(d => ({ key: d.fecha, label: d.label, ventas: d.total_ventas, ingresos: d.total_ingresos })));
          break;
      }
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [state.nivel, state.anio, state.semestre, state.trimestre, state.mes, state.semana]);

  useEffect(() => { cargar(); }, [cargar]);

  function drillDown(item) {
    const siguiente = {
      anios: "semestres", semestres: "trimestres", trimestres: "meses",
      meses: "semanas", semanas: "dias", dias: "facturas",
    };
    const campo = {
      anios: "anio", semestres: "semestre", trimestres: "trimestre",
      meses: "mes", semanas: "semana",
    };
    if (state.nivel === "dias") {
      verFacturas(item.key, item.label);
      return;
    }
    setState(s => ({ ...s, nivel: siguiente[s.nivel], [campo[s.nivel]]: item.key }));
  }

  async function verFacturas(fecha, label) {
    setVistaFacturas(true);
    setTituloFacturas("Facturas del " + label);
    setFacturas([]);
    try {
      const data = await api.get(`/organizacion/dia/${fecha}`);
      setFacturas(data.facturas ?? []);
    } catch(e) { console.error(e); }
    setState(s => ({ ...s, dia: fecha }));
  }

  function navegarA(nivel) {
    const NIVELES = ["anios", "semestres", "trimestres", "meses", "semanas", "dias"];
    const idx = NIVELES.indexOf(nivel);
    setVistaFacturas(false);
    setState(s => ({
      ...s, nivel,
      anio:      idx < 1 ? null : s.anio,
      semestre:  idx < 2 ? null : s.semestre,
      trimestre: idx < 3 ? null : s.trimestre,
      mes:       idx < 4 ? null : s.mes,
      semana:    idx < 5 ? null : s.semana,
      dia:       null,
    }));
  }

  function urlDescargar(nivel, extra = {}) {
    const p = new URLSearchParams({ nivel, usuario: user?.usuario ?? "root", ...extra });
    if (state.anio)     p.set("anio",      state.anio);
    if (state.semestre) p.set("semestre",  state.semestre);
    if (state.trimestre)p.set("trimestre", state.trimestre);
    if (state.mes)      p.set("mes",       state.mes);
    if (state.semana)   p.set("semana",    state.semana);
    return `${api.baseUrl}/organizacion/descargar?${p.toString()}`;
  }

  const crumbs = [{ label: "Inicio", nivel: "anios" }];
  if (state.anio)      crumbs.push({ label: String(state.anio),                          nivel: "semestres" });
  if (state.semestre)  crumbs.push({ label: "H" + state.semestre,                        nivel: "trimestres" });
  if (state.trimestre) crumbs.push({ label: "Q" + state.trimestre,                       nivel: "meses" });
  if (state.mes)       crumbs.push({ label: MESES[state.mes] ?? "Mes",                   nivel: "semanas" });
  if (state.semana) {
    const partes = String(state.semana).split("-");
    crumbs.push({ label: `Semana ${partes[2]}/${partes[1]}`,                             nivel: "dias" });
  }
  if (state.dia) {
    const d = new Date(state.dia + "T12:00:00");
    const dias = ["Dom","Lun","Mar","Mié","Jue","Vie","Sáb"];
    const p = String(state.dia).split("-");
    crumbs.push({ label: `${dias[d.getDay()]} ${p[2]}/${p[1]}`,                          nivel: "facturas" });
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Organización de Facturas</h1>
          <p>Navega y descarga facturas por período</p>
        </div>
        {!vistaFacturas && state.nivel !== "anios" && (
          <a href={urlDescargar("anio")} target="_blank" rel="noreferrer"
            className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={15} /> Descargar nivel
          </a>
        )}
      </div>

      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 flex-wrap text-sm">
        {crumbs.map((c, i) => (
          <span key={i} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight size={14} className="text-content-subtle/60" />}
            {i === crumbs.length - 1 ? (
              <span className="text-content font-medium bg-surface-card px-3 py-1.5 rounded-xl border border-border/40">{c.label}</span>
            ) : (
              <button onClick={() => navegarA(c.nivel)}
                className="text-brand-400 hover:text-brand-300 transition-colors px-2 py-1 hover:bg-brand-500/5 rounded-lg">
                {c.label}
              </button>
            )}
          </span>
        ))}
      </nav>

      {/* Vista de facturas */}
      {vistaFacturas ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-content">{tituloFacturas}</h2>
            <div className="flex gap-2">
              <a href={urlDescargar("dia", { fecha: state.dia })} target="_blank" rel="noreferrer"
                className="btn-secondary flex items-center gap-2 text-sm">
                <Download size={15} /> Descargar todo
              </a>
              <button onClick={() => { setVistaFacturas(false); setState(s => ({ ...s, dia: null })); }}
                className="btn-ghost flex items-center gap-2 text-sm">
                <ArrowLeft size={15} /> Volver
              </button>
            </div>
          </div>

          <div className="table-container">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">#</th>
                    <th className="th">Cliente</th>
                    <th className="th text-right">Total</th>
                    <th className="th hidden sm:table-cell">Hora</th>
                    <th className="th hidden sm:table-cell">Método</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {facturas.length === 0 ? (
                    <tr><td colSpan={6} className="td text-center text-content-subtle py-8">Sin facturas para este día</td></tr>
                  ) : facturas.map((f, i) => (
                    <tr key={f.id} className="table-row">
                      <td className="td text-content-subtle">{f.id}</td>
                      <td className="td font-medium text-content">{f.cliente_nombre ?? "—"}</td>
                      <td className="td text-right font-semibold text-brand-400">{fmtMoney(f.total)}</td>
                      <td className="td hidden sm:table-cell text-content-muted">{formatHora(f.fecha_hora)}</td>
                      <td className="td hidden sm:table-cell"><span className="badge-blue">{f.metodo_pago}</span></td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <a href={`${api.baseUrl}/facturas/${f.id}?usuario=${user?.usuario ?? "root"}`}
                            target="_blank" rel="noreferrer"
                            className="btn-ghost p-1.5 text-brand-400 hover:text-brand-300" title="Ver factura">
                            <Eye size={14} />
                          </a>
                          <a href={`${api.baseUrl}/organizacion/descargar?nivel=factura&factura_id=${f.id}&usuario=${user?.usuario ?? "root"}`}
                            target="_blank" rel="noreferrer"
                            className="btn-ghost p-1.5 text-secondary-400 hover:text-secondary-300" title="Descargar">
                            <Download size={14} />
                          </a>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : loading ? (
        <div className="flex justify-center py-20">
          <div className="w-9 h-9 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state">
          <FileText size={44} />
          <p>No hay facturas en este período.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {items.map(item => (
            <PeriodCard
              key={item.key}
              label={item.label}
              ventas={item.ventas}
              ingresos={item.ingresos}
              disabled={item.ventas === 0}
              onClick={() => item.ventas > 0 && drillDown(item)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
