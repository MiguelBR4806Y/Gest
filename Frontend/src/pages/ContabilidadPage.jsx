import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Download, Info, Receipt, ShoppingCart, TrendingDown, TrendingUp, Truck, Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";

import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { Button } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input } from "../components/ui/Field";
import { CardSkeleton } from "../components/ui/Feedback";

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

function inicioDeMes() {
  const hoy = new Date();
  return new Date(hoy.getFullYear(), hoy.getMonth(), 1).toISOString().slice(0, 10);
}

const ACCESOS = [
  { to: "/gastos", label: "Gastos", icon: Wallet, texto: "Servicios, alquiler, salarios" },
  { to: "/compras", label: "Compras", icon: Receipt, texto: "Mercancía y costo promedio" },
  { to: "/proveedores", label: "Proveedores", icon: Truck, texto: "A quién le compras" },
  { to: "/ventas", label: "Ventas", icon: ShoppingCart, texto: "Facturas emitidas" },
];

/** Mini gráfico de barras apiladas con SVG puro, sin dependencias. */
function SerieContable({ puntos }) {
  if (!puntos?.length) return null;

  const maximo = Math.max(...puntos.map((p) => Math.max(p.ingresos, p.gastos, 1)));
  const alto = 120;

  return (
    <div className="flex items-end gap-1.5 h-32" role="img" aria-label="Ingresos y gastos por periodo">
      {puntos.map((p) => {
        const altoIngreso = Math.max(2, (p.ingresos / maximo) * alto);
        const altoGasto = Math.max(1, (p.gastos / maximo) * alto);
        return (
          <div key={p.periodo} className="flex-1 min-w-0 flex flex-col justify-end gap-0.5">
            <div
              className="w-full rounded-t bg-brand-500/80"
              style={{ height: `${altoIngreso}px` }}
              title={`Ingresos ${fmtMoney(p.ingresos)}`}
            />
            <div
              className="w-full rounded-t bg-red-500/60"
              style={{ height: `${altoGasto}px` }}
              title={`Gastos ${fmtMoney(p.gastos)}`}
            />
          </div>
        );
      })}
    </div>
  );
}

export default function ContabilidadPage() {
  const { toast } = useToast();
  const [desde, setDesde] = useState(inicioDeMes);
  const [hasta, setHasta] = useState(hoyISO);
  const [resumen, setResumen] = useState(null);
  const [serie, setSerie] = useState([]);
  const [agrupacion, setAgrupacion] = useState("dia");
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const consulta = new URLSearchParams({ desde, hasta }).toString();
      const [r, s] = await Promise.all([
        api.get(`/contabilidad/resumen?${consulta}`),
        api.get(`/contabilidad/serie?${consulta}&agrupacion=${agrupacion}`),
      ]);
      setResumen(r);
      setSerie(s?.puntos ?? []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [desde, hasta, agrupacion, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const utilidadPositiva = (resumen?.utilidad ?? 0) >= 0;
  const totalGastosCategoria = useMemo(
    () => (resumen?.gastos_por_categoria ?? []).reduce((s, c) => s + c.total, 0),
    [resumen]
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Contabilidad</h1>
          <p>Ingresos, costos y utilidad del periodo</p>
        </div>
        <Button
          variant="secondary"
          icon={Download}
          onClick={() =>
            api.descargar(
              `/contabilidad/exportar?desde=${desde}&hasta=${hasta}`,
              `contabilidad_${desde}_${hasta}.csv`
            )
          }
        >
          Exportar CSV
        </Button>
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Desde">
            <Input type="date" value={desde} max={hasta} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={hasta} min={desde} onChange={(e) => setHasta(e.target.value)} />
          </Field>
        </div>
      </Card>

      {cargando || !resumen ? (
        <CardSkeleton cantidad={4} />
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard
              icon={TrendingUp}
              label="Ingresos"
              value={fmtMoney(resumen.ingresos)}
              sub={`${resumen.numero_ventas} ventas`}
              tono="green"
            />
            <StatCard
              icon={ShoppingCart}
              label="Costo de ventas"
              value={fmtMoney(resumen.costo_ventas)}
              sub="Costo congelado al vender"
            />
            <StatCard
              icon={TrendingDown}
              label="Gastos"
              value={fmtMoney(resumen.gastos)}
              sub={`${resumen.numero_gastos} registros`}
              tono="red"
            />
            <StatCard
              icon={Wallet}
              label="Utilidad"
              value={fmtMoney(resumen.utilidad)}
              sub={`Margen ${Number(resumen.margen_pct).toFixed(1)}%`}
              tono={utilidadPositiva ? "green" : "red"}
            />
          </div>

          <Card className="p-5">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div>
                <h3 className="section-title">Evolución del periodo</h3>
                <p className="text-xs text-content-subtle mt-0.5">
                  Ingresos (verde) y gastos (rojo)
                </p>
              </div>
              <div className="segmented" role="tablist" aria-label="Agrupación">
                {[{ id: "dia", label: "Día" }, { id: "mes", label: "Mes" }].map((op) => (
                  <button
                    key={op.id}
                    type="button"
                    role="tab"
                    aria-selected={agrupacion === op.id}
                    className={`segment ${agrupacion === op.id ? "segment-active" : ""}`}
                    onClick={() => setAgrupacion(op.id)}
                  >
                    {op.label}
                  </button>
                ))}
              </div>
            </div>

            {serie.length === 0 ? (
              <EmptyState
                icon={Receipt}
                title="Sin movimientos"
                text="Registra ventas o gastos para ver la evolución."
              />
            ) : (
              <>
                <SerieContable puntos={serie} />
                <div className="flex justify-between mt-2 text-[10px] text-content-subtle">
                  <span>{serie[0]?.periodo}</span>
                  <span>{serie[serie.length - 1]?.periodo}</span>
                </div>
              </>
            )}
          </Card>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card className="overflow-hidden">
              <div className="px-5 py-4 border-b border-border/60">
                <h3 className="section-title">Gastos por categoría</h3>
              </div>
              {resumen.gastos_por_categoria.length === 0 ? (
                <EmptyState icon={Wallet} title="Sin gastos" text="No hay gastos en el periodo." />
              ) : (
                <table className="w-full">
                  <tbody>
                    {resumen.gastos_por_categoria.map((c) => (
                      <tr key={c.categoria} className="table-row">
                        <td className="td">
                          <span className="badge-neutral">{c.categoria}</span>
                        </td>
                        <td className="td text-right text-content-subtle text-xs tabular">
                          {((c.total / totalGastosCategoria) * 100).toFixed(0)}%
                        </td>
                        <td className="td text-right tabular font-medium">{fmtMoney(c.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>

            <Card className="overflow-hidden">
              <div className="px-5 py-4 border-b border-border/60">
                <h3 className="section-title">Ir a</h3>
              </div>
              <div className="p-2">
                {ACCESOS.map(({ to, label, icon: Icon, texto }) => (
                  <Link
                    key={to}
                    to={to}
                    className="nav-item nav-item-idle w-full"
                  >
                    <Icon size={17} className="shrink-0" aria-hidden="true" />
                    <span className="flex-1 min-w-0">
                      <span className="block text-sm">{label}</span>
                      <span className="block text-[11px] text-content-subtle truncate">{texto}</span>
                    </span>
                  </Link>
                ))}
              </div>
            </Card>
          </div>
        </>
      )}

      <p className="flex items-start gap-1.5 text-xs text-content-subtle">
        <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
        <span>
          {resumen?.nota
            ?? "Resumen de gestión. No incluye IVA ni asientos contables: no sustituye una declaración fiscal."}
        </span>
      </p>
    </div>
  );
}
