import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeft, ChevronRight, Download, Eye, FileText, FolderOpen,
} from "lucide-react";

import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState } from "../components/ui/Card";
import { Spinner } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { api, formatHora, fmtMoney } from "../lib/api";

const MESES = [
  "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

const NIVELES = ["anios", "semestres", "trimestres", "meses", "semanas", "dias"];

const ESTADO_INICIAL = {
  nivel: "anios",
  anio: null,
  semestre: null,
  trimestre: null,
  mes: null,
  semana: null,
  dia: null,
};

function Cargando() {
  return (
    <div className="flex justify-center py-20">
      <Spinner size={30} />
    </div>
  );
}

export default function OrganizacionPage() {
  const { toast } = useToast();

  const [estado, setEstado] = useState(ESTADO_INICIAL);
  const [items, setItems] = useState([]);
  const [facturas, setFacturas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [verFacturas, setVerFacturas] = useState(false);
  const [tituloFacturas, setTituloFacturas] = useState("");
  const [descargando, setDescargando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    setItems([]);
    try {
      let data;
      switch (estado.nivel) {
        case "anios":
          data = await api.get("/organizacion/anios");
          setItems(
            (data.anios ?? []).map((a) => ({
              key: a.anio,
              label: String(a.anio),
              ventas: a.total_ventas,
              ingresos: a.total_ingresos,
            }))
          );
          break;
        case "semestres":
          data = await api.get(`/organizacion/${estado.anio}/semestres`);
          setItems(
            (data.semestres ?? []).map((s) => ({
              key: s.semestre,
              label: s.label,
              ventas: s.total_ventas,
              ingresos: s.total_ingresos,
            }))
          );
          break;
        case "trimestres":
          data = await api.get(`/organizacion/${estado.anio}/${estado.semestre}/trimestres`);
          setItems(
            (data.trimestres ?? []).map((t) => ({
              key: t.trimestre,
              label: t.label,
              ventas: t.total_ventas,
              ingresos: t.total_ingresos,
            }))
          );
          break;
        case "meses":
          data = await api.get(`/organizacion/${estado.anio}/${estado.trimestre}/meses`);
          setItems(
            (data.meses ?? []).map((m) => ({
              key: m.mes,
              label: m.label,
              ventas: m.total_ventas,
              ingresos: m.total_ingresos,
            }))
          );
          break;
        case "semanas":
          data = await api.get(`/organizacion/${estado.anio}/${estado.mes}/semanas`);
          setItems(
            (data.semanas ?? []).map((s) => ({
              key: s.inicio_semana,
              label: s.label,
              ventas: s.total_ventas,
              ingresos: s.total_ingresos,
            }))
          );
          break;
        case "dias":
          data = await api.get(`/organizacion/${estado.anio}/${estado.mes}/${estado.semana}/dias`);
          setItems(
            (data.dias ?? []).map((d) => ({
              key: d.fecha,
              label: d.label,
              ventas: d.total_ventas,
              ingresos: d.total_ingresos,
            }))
          );
          break;
        default:
          break;
      }
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [estado, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function bajarNivel(item) {
    if (estado.nivel === "dias") {
      abrirFacturasDelDia(item.key, item.label);
      return;
    }
    const siguiente = NIVELES[NIVELES.indexOf(estado.nivel) + 1];
    const campo = {
      anios: "anio",
      semestres: "semestre",
      trimestres: "trimestre",
      meses: "mes",
      semanas: "semana",
    }[estado.nivel];
    setEstado((s) => ({ ...s, nivel: siguiente, [campo]: item.key }));
  }

  async function abrirFacturasDelDia(fecha, label) {
    setVerFacturas(true);
    setTituloFacturas(`Facturas del ${label}`);
    setFacturas([]);
    try {
      const data = await api.get(`/organizacion/dia/${fecha}`);
      setFacturas(data.facturas ?? []);
    } catch (e) {
      toast(e.message, "error");
    }
    setEstado((s) => ({ ...s, dia: fecha }));
  }

  function volverA(nivel) {
    const indice = NIVELES.indexOf(nivel);
    setVerFacturas(false);
    setEstado((s) => ({
      ...s,
      nivel,
      anio: indice < 1 ? null : s.anio,
      semestre: indice < 2 ? null : s.semestre,
      trimestre: indice < 3 ? null : s.trimestre,
      mes: indice < 4 ? null : s.mes,
      semana: indice < 5 ? null : s.semana,
      dia: null,
    }));
  }

  /**
   * URL de descarga del periodo actual.
   *
   * Antes esto se usaba en un `<a href>`: el token va en la cabecera
   * Authorization y un enlace no la envía, así que siempre daba 401.
   */
  function urlDescarga(nivel, extra = {}) {
    const p = new URLSearchParams({ nivel });
    const campos = { anio: estado.anio, semestre: estado.semestre, trimestre: estado.trimestre, mes: estado.mes, semana: estado.semana };
    Object.entries({ ...campos, ...extra }).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== "") p.set(k, v);
    });
    return `/organizacion/descargar?${p.toString()}`;
  }

  async function descargar(url, nombre) {
    setDescargando(true);
    try {
      await api.descargar(url, nombre);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setDescargando(false);
    }
  }

  async function verPdf(id) {
    try {
      await api.abrir(`/facturas/${id}`);
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const migas = [{ label: "Inicio", nivel: "anios" }];
  if (estado.anio) migas.push({ label: String(estado.anio), nivel: "semestres" });
  if (estado.semestre) migas.push({ label: `H${estado.semestre}`, nivel: "trimestres" });
  if (estado.trimestre) migas.push({ label: `Q${estado.trimestre}`, nivel: "meses" });
  if (estado.mes) migas.push({ label: MESES[estado.mes] ?? "Mes", nivel: "semanas" });
  if (estado.semana) {
    const [, m, d] = String(estado.semana).split("-");
    migas.push({ label: `Semana ${d}/${m}`, nivel: "dias" });
  }
  if (estado.dia) {
    const [, m, d] = String(estado.dia).split("-");
    migas.push({ label: `${d}/${m}`, nivel: "facturas" });
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Organización de facturas</h1>
          <p>Navega por año, semestre, mes y día para descargar tus facturas.</p>
        </div>
        {!verFacturas && estado.nivel !== "anios" && (
          <Button
            variant="secondary"
            icon={Download}
            loading={descargando}
            onClick={() => descargar(urlDescarga("anio"), `facturas_${estado.anio}.zip`)}
          >
            Descargar {estado.anio}
          </Button>
        )}
      </div>

      <nav aria-label="Ruta de navegación" className="flex items-center gap-1 flex-wrap text-sm">
        {migas.map((m, i) => (
          <span key={`${m.nivel}-${i}`} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={14} className="text-content-subtle" aria-hidden="true" />}
            {i === migas.length - 1 ? (
              <span className="px-2.5 py-1 rounded-md bg-surface-card border border-border text-content font-medium">
                {m.label}
              </span>
            ) : (
              <button
                type="button"
                onClick={() => volverA(m.nivel)}
                className="px-2 py-1 rounded-md text-brand-600 dark:text-brand-300 hover:bg-brand-500/10 transition-colors"
              >
                {m.label}
              </button>
            )}
          </span>
        ))}
      </nav>

      {verFacturas ? (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h2 className="text-base font-semibold text-content">{tituloFacturas}</h2>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                icon={Download}
                loading={descargando}
                onClick={() => descargar(urlDescarga("dia", { fecha: estado.dia }), `facturas_${estado.dia}.zip`)}
              >
                Descargar todo
              </Button>
              <Button
                variant="ghost"
                size="sm"
                icon={ArrowLeft}
                onClick={() => {
                  setVerFacturas(false);
                  setEstado((s) => ({ ...s, dia: null }));
                }}
              >
                Volver
              </Button>
            </div>
          </div>

          <Card className="overflow-hidden">
            {facturas.length === 0 ? (
              <EmptyState
                icon={FileText}
                title="Sin facturas este día"
                text="No se registraron ventas en esta fecha."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      <th className="th">Factura</th>
                      <th className="th">Cliente</th>
                      <th className="th text-right">Total</th>
                      <th className="th hidden sm:table-cell">Hora</th>
                      <th className="th hidden sm:table-cell">Método</th>
                      <th className="th text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {facturas.map((f) => (
                      <tr key={f.id} className="table-row">
                        <td className="td font-mono text-xs text-content-muted">#{f.id}</td>
                        <td className="td font-medium max-w-[12rem] truncate">
                          {f.cliente_nombre || "Consumidor final"}
                        </td>
                        <td className="td text-right font-semibold tabular">{fmtMoney(f.total)}</td>
                        <td className="td hidden sm:table-cell text-content-muted">
                          {formatHora(f.fecha_hora)}
                        </td>
                        <td className="td hidden sm:table-cell text-content-muted">{f.metodo_pago}</td>
                        <td className="td">
                          <div className="flex items-center justify-end gap-0.5">
                            <IconButton label="Ver PDF" icon={Eye} onClick={() => verPdf(f.id)} />
                            <IconButton
                              label="Descargar PDF"
                              icon={Download}
                              onClick={() =>
                                descargar(
                                  `/organizacion/descargar?nivel=factura&factura_id=${f.id}`,
                                  `factura_${f.id}.pdf`
                                )
                              }
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      ) : cargando ? (
        <Cargando />
      ) : items.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Sin facturas en este período"
          text="Registra ventas para que se generen las facturas."
        />
      ) : (
        <ul className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {items.map((item) => {
            const vacio = item.ventas === 0;
            return (
              <li key={item.key}>
                <button
                  type="button"
                  disabled={vacio}
                  onClick={() => bajarNivel(item)}
                  className={`w-full card-hover p-4 text-left flex flex-col gap-2 ${
                    vacio ? "opacity-45 cursor-not-allowed" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <FolderOpen
                      size={20}
                      className={vacio ? "text-content-subtle" : "text-brand-500 dark:text-brand-300"}
                      aria-hidden="true"
                    />
                    {!vacio && (
                      <span className="badge-blue">{item.ventas}</span>
                    )}
                  </div>
                  <p className="text-sm font-semibold text-content truncate">{item.label}</p>
                  {vacio ? (
                    <p className="text-xs text-content-subtle">Sin facturas</p>
                  ) : (
                    <p className="text-xs text-content-muted tabular">{fmtMoney(item.ingresos)}</p>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
