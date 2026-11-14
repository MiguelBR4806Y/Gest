import { useCallback, useEffect, useState } from "react";
import { Palmtree, Plus, Trash2 } from "lucide-react";

import Modal from "./Modal";
import { Button, IconButton } from "./ui/Button";
import { Field, Input } from "./ui/Field";
import { TableSkeleton } from "./ui/Feedback";
import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

function diasEntre(inicio, fin) {
  if (!inicio || !fin) return 0;
  const a = new Date(inicio);
  const b = new Date(fin);
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return 0;
  return Math.max(0, Math.round((b - a) / 86400000) + 1);
}

/**
 * Vacaciones: saldo según el art. 76 (15 días por cada 6 meses) y registro
 * de los periodos tomados.
 */
export default function VacacionesModal({ persona, open, onClose, onCambio }) {
  const { toast } = useToast();
  const [datos, setDatos] = useState({ items: [], total_dias: 0, saldo: null });
  const [cargando, setCargando] = useState(true);
  const [inicio, setInicio] = useState(hoyISO);
  const [fin, setFin] = useState(hoyISO);
  const [nota, setNota] = useState("");
  const [guardando, setGuardando] = useState(false);

  const dias = diasEntre(inicio, fin);
  const saldo = datos.saldo;

  const cargar = useCallback(async () => {
    if (!open || !persona) return;
    setCargando(true);
    try {
      const data = await api.get(
        `/empleados/vacaciones?persona_tipo=${persona.tipo}&persona_id=${persona.id}`
      );
      setDatos({
        items: data?.items ?? [],
        total_dias: data?.total_dias ?? 0,
        saldo: data?.saldo ?? null,
      });
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [open, persona, toast]);

  useEffect(() => {
    if (!open) return;
    setInicio(hoyISO());
    setFin(hoyISO());
    setNota("");
    cargar();
  }, [open, cargar]);

  async function registrar(e) {
    e?.preventDefault();
    if (dias <= 0) return;
    setGuardando(true);
    try {
      await api.post("/empleados/vacaciones", {
        persona_tipo: persona.tipo,
        persona_id: persona.id,
        fecha_inicio: inicio,
        fecha_fin: fin,
        dias,
        nota: nota.trim() || null,
      });
      toast(`${dias} día(s) registrados`);
      setNota("");
      cargar();
      onCambio?.();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar(registro) {
    try {
      await api.delete(`/empleados/vacaciones/${registro.id}`);
      toast("Registro eliminado");
      cargar();
      onCambio?.();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const excede = saldo && dias > Number(saldo.dias_disponibles);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Vacaciones — ${persona?.nombre ?? ""}`}
      size="md"
      footer={
        <button type="button" className="btn-secondary" onClick={onClose}>
          Cerrar
        </button>
      }
    >
      <div className="space-y-4">
        {cargando && !saldo ? (
          <TableSkeleton filas={2} columnas={3} />
        ) : saldo && !saldo.configurado ? (
          <div className="rounded-xl border border-accent-500/30 bg-accent-500/5 p-4 text-sm text-content-muted">
            Falta la <span className="font-medium text-content">fecha de ingreso</span> de esta
            persona. Configúrala en su ficha para calcular las vacaciones.
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Devengados", valor: `${Number(saldo?.dias_devengados ?? 0).toFixed(1)} d` },
              { label: "Tomados", valor: `${saldo?.dias_tomados ?? 0} d` },
              { label: "Disponibles", valor: `${Number(saldo?.dias_disponibles ?? 0).toFixed(1)} d`, fuerte: true },
              { label: "Valor", valor: fmtMoney(saldo?.valor_dias ?? 0) },
            ].map((m) => (
              <div key={m.label} className="rounded-lg border border-border p-2.5">
                <p className="text-[10px] uppercase tracking-wide text-content-subtle">{m.label}</p>
                <p className={`tabular mt-0.5 ${m.fuerte ? "text-lg font-bold text-content" : "text-sm text-content"}`}>
                  {m.valor}
                </p>
              </div>
            ))}
          </div>
        )}

        {saldo?.configurado && (
          <form onSubmit={registrar} className="rounded-xl border border-border p-3.5 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-content">
              <Palmtree size={16} className="text-content-muted" aria-hidden="true" />
              Registrar días tomados
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Desde">
                <Input type="date" value={inicio} onChange={(e) => setInicio(e.target.value)} />
              </Field>
              <Field label="Hasta">
                <Input
                  type="date"
                  value={fin}
                  min={inicio}
                  onChange={(e) => setFin(e.target.value)}
                />
              </Field>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-surface-sunken px-3 py-2">
              <span className="text-sm text-content-muted">Días a registrar</span>
              <span className={`tabular font-semibold ${excede ? "text-red-600 dark:text-red-400" : "text-content"}`}>
                {dias}
              </span>
            </div>
            {excede && (
              <p className="text-xs text-red-600 dark:text-red-400">
                Excede el saldo disponible ({Number(saldo.dias_disponibles).toFixed(1)} días).
              </p>
            )}

            <Field label="Nota" hint="Opcional">
              <Input
                value={nota}
                onChange={(e) => setNota(e.target.value)}
                placeholder="Vacaciones de fin de año"
                maxLength={300}
              />
            </Field>

            <Button
              type="submit"
              icon={Plus}
              loading={guardando}
              disabled={dias <= 0 || Boolean(excede)}
              className="w-full"
            >
              Registrar {dias > 0 ? `${dias} día(s)` : ""}
            </Button>
          </form>
        )}

        {datos.items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Periodo</th>
                  <th className="th text-right">Días</th>
                  <th className="th text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {datos.items.map((v) => (
                  <tr key={v.id} className="table-row">
                    <td className="td text-sm">
                      {v.fecha_inicio} → {v.fecha_fin}
                      {v.nota && <p className="text-xs text-content-subtle">{v.nota}</p>}
                    </td>
                    <td className="td text-right tabular">{v.dias}</td>
                    <td className="td text-right">
                      <IconButton
                        label="Eliminar registro"
                        icon={Trash2}
                        onClick={() => eliminar(v)}
                        className="text-red-500 hover:bg-red-500/10"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <p className="text-xs text-content-subtle">
          Cálculo según el art. 76 del Código del Trabajo: 15 días por cada 6 meses
          (2.5 por mes, hasta 30 al año). El valor usa el salario diario (mensual / 30).
        </p>
      </div>
    </Modal>
  );
}
