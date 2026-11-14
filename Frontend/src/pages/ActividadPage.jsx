import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, RefreshCw, Search } from "lucide-react";

import { Button } from "../components/ui/Button";
import { Card, EmptyState } from "../components/ui/Card";
import { Input, Select } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { api, formatFechaHora } from "../lib/api";

const ETIQUETAS = {
  venta_creada: { label: "Venta creada", tono: "badge-green" },
  venta_anulada: { label: "Venta anulada", tono: "badge-red" },
  producto_creado: { label: "Producto creado", tono: "badge-blue" },
  producto_editado: { label: "Producto editado", tono: "badge-yellow" },
  producto_eliminado: { label: "Producto eliminado", tono: "badge-red" },
  inventario_recargado: { label: "Inventario recargado", tono: "badge-blue" },
  cliente_creado: { label: "Cliente creado", tono: "badge-blue" },
  cliente_editado: { label: "Cliente editado", tono: "badge-yellow" },
  cliente_eliminado: { label: "Cliente eliminado", tono: "badge-red" },
  abono_credito: { label: "Abono de crédito", tono: "badge-green" },
};

export default function ActividadPage() {
  const { toast } = useToast();
  const [eventos, setEventos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [tipo, setTipo] = useState("");
  const [busqueda, setBusqueda] = useState("");

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const params = new URLSearchParams({ limite: "150" });
      if (tipo) params.set("tipo", tipo);
      const data = await api.get(`/reportes/eventos?${params.toString()}`);
      setEventos(Array.isArray(data) ? data : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [tipo, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const filtrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase();
    if (!q) return eventos;
    return eventos.filter(
      (e) =>
        String(e.detalle || "").toLowerCase().includes(q) ||
        String(e.entidad || "").toLowerCase().includes(q) ||
        String(e.entidad_id ?? "").includes(q)
    );
  }, [eventos, busqueda]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Actividad</h1>
          <p>Bitácora de auditoría de tu cuenta</p>
        </div>
        <Button variant="secondary" size="sm" icon={RefreshCw} onClick={cargar} loading={cargando}>
          Actualizar
        </Button>
      </div>

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-content-subtle pointer-events-none"
            aria-hidden="true"
          />
          <Input
            className="pl-10"
            placeholder="Buscar en el detalle…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar en la actividad"
          />
        </div>
        <Select
          value={tipo}
          onChange={(e) => setTipo(e.target.value)}
          className="sm:w-64 shrink-0"
          aria-label="Filtrar por tipo de evento"
        >
          <option value="">Todos los eventos</option>
          {Object.entries(ETIQUETAS).map(([valor, meta]) => (
            <option key={valor} value={valor}>
              {meta.label}
            </option>
          ))}
        </Select>
      </div>

      {cargando ? (
        <TableSkeleton filas={8} columnas={4} />
      ) : (
        <Card className="overflow-hidden">
          {filtrados.length === 0 ? (
            <EmptyState
              icon={Activity}
              title="Sin actividad registrada"
              text="Las ventas, anulaciones y cambios de inventario aparecerán aquí."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Fecha</th>
                    <th className="th">Evento</th>
                    <th className="th hidden sm:table-cell">Entidad</th>
                    <th className="th hidden md:table-cell">Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((e) => {
                    const meta = ETIQUETAS[e.tipo] ?? { label: e.tipo, tono: "badge-neutral" };
                    return (
                      <tr key={e.id} className="table-row">
                        <td className="td text-content-muted text-xs whitespace-nowrap">
                          {formatFechaHora(e.fecha_hora)}
                        </td>
                        <td className="td">
                          <span className={meta.tono}>{meta.label}</span>
                        </td>
                        <td className="td hidden sm:table-cell text-content-muted text-xs">
                          {e.entidad}
                          {e.entidad_id != null ? ` #${e.entidad_id}` : ""}
                        </td>
                        <td className="td hidden md:table-cell text-content-muted text-xs max-w-[28rem] truncate">
                          {e.detalle || "—"}
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
