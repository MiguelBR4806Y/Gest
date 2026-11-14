import { useCallback, useEffect, useState } from "react";
import { Banknote, Percent, RefreshCw, TrendingUp, Wallet } from "lucide-react";

import { Button } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Input } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { api, fmtMoney } from "../lib/api";

const iso = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function rangoInicial() {
  const hasta = new Date();
  const desde = new Date();
  desde.setDate(desde.getDate() - 29);
  return { desde: iso(desde), hasta: iso(hasta) };
}

export default function RentabilidadPage() {
  const { toast } = useToast();
  const inicial = rangoInicial();
  const [desde, setDesde] = useState(inicial.desde);
  const [hasta, setHasta] = useState(inicial.hasta);
  const [datos, setDatos] = useState(null);
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get(`/reportes/margenes?desde=${desde}&hasta=${hasta}`);
      setDatos(data);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [desde, hasta, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const totales = datos?.totales ?? {
    ingresos: 0, costo: 0, ganancia: 0, margen_pct: 0, unidades: 0,
  };
  const productos = datos?.productos ?? [];

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Rentabilidad</h1>
          <p>Ingresos, costo y margen por producto</p>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} onClick={cargar} loading={cargando}>
          Actualizar
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 sm:items-end">
        <div className="flex items-center gap-2">
          <label htmlFor="desde" className="text-sm text-content-muted whitespace-nowrap">
            Desde
          </label>
          <Input
            id="desde"
            type="date"
            value={desde}
            max={hasta}
            onChange={(e) => setDesde(e.target.value)}
            className="w-auto"
          />
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="hasta" className="text-sm text-content-muted whitespace-nowrap">
            Hasta
          </label>
          <Input
            id="hasta"
            type="date"
            value={hasta}
            min={desde}
            onChange={(e) => setHasta(e.target.value)}
            className="w-auto"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={TrendingUp} label="Ingresos" value={fmtMoney(totales.ingresos)} tono="green" />
        <StatCard icon={Wallet} label="Costo" value={fmtMoney(totales.costo)} tono="yellow" />
        <StatCard
          icon={Banknote}
          label="Ganancia"
          value={fmtMoney(totales.ganancia)}
          sub={`${totales.unidades} unidades`}
          tono={totales.ganancia >= 0 ? "green" : "red"}
        />
        <StatCard
          icon={Percent}
          label="Margen"
          value={`${Number(totales.margen_pct || 0).toFixed(1)}%`}
          sub="Sobre ingresos"
          tono={totales.margen_pct >= 30 ? "green" : "yellow"}
        />
      </div>

      {cargando ? (
        <TableSkeleton filas={6} columnas={6} />
      ) : (
        <Card className="overflow-hidden">
          {productos.length === 0 ? (
            <EmptyState
              icon={Percent}
              title="Sin datos en el periodo"
              text="Registra el costo de tus productos y sus ventas para ver el margen real."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Producto</th>
                    <th className="th text-right hidden sm:table-cell">Unidades</th>
                    <th className="th text-right">Ingresos</th>
                    <th className="th text-right hidden md:table-cell">Costo</th>
                    <th className="th text-right">Ganancia</th>
                    <th className="th text-right">Margen</th>
                  </tr>
                </thead>
                <tbody>
                  {productos.map((p) => {
                    const tono =
                      p.margen_pct >= 40
                        ? "badge-green"
                        : p.margen_pct >= 20
                          ? "badge-yellow"
                          : "badge-red";
                    return (
                      <tr key={p.producto_id ?? p.nombre} className="table-row">
                        <td className="td font-medium max-w-[16rem] truncate">{p.nombre}</td>
                        <td className="td text-right tabular hidden sm:table-cell">{p.unidades}</td>
                        <td className="td text-right tabular">{fmtMoney(p.ingresos)}</td>
                        <td className="td text-right tabular hidden md:table-cell text-content-muted">
                          {fmtMoney(p.costo)}
                        </td>
                        <td className="td text-right font-semibold tabular">{fmtMoney(p.ganancia)}</td>
                        <td className="td text-right">
                          <span className={tono}>{Number(p.margen_pct || 0).toFixed(1)}%</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
