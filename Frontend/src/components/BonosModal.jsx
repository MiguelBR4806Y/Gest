import { useCallback, useEffect, useState } from "react";
import { Gift, Plus, Trash2 } from "lucide-react";

import Modal from "./Modal";
import { Button, IconButton } from "./ui/Button";
import { Field, Input } from "./ui/Field";
import { Checkbox } from "./ui/Field";
import { TableSkeleton } from "./ui/Feedback";
import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";

const VACIO = {
  concepto: "",
  monto: "",
  fecha: new Date().toISOString().slice(0, 10),
  recurrente: false,
};

/** Bonos de una persona: alta, edición del monto y recurrencia mensual. */
export default function BonosModal({ persona, open, onClose, onCambio }) {
  const { toast } = useToast();
  const [bonos, setBonos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [form, setForm] = useState(VACIO);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!open || !persona) return;
    setCargando(true);
    try {
      const data = await api.get(
        `/empleados/bonos?persona_tipo=${persona.tipo}&persona_id=${persona.id}`
      );
      setBonos(data?.items ?? []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [open, persona, toast]);

  useEffect(() => {
    if (!open) return;
    setForm(VACIO);
    cargar();
  }, [open, cargar]);

  async function agregar(e) {
    e?.preventDefault();
    const monto = Number(form.monto);
    if (!form.concepto.trim() || !Number.isFinite(monto) || monto <= 0) return;
    setGuardando(true);
    try {
      await api.post("/empleados/bonos", {
        persona_tipo: persona.tipo,
        persona_id: persona.id,
        concepto: form.concepto.trim(),
        monto,
        fecha: form.fecha,
        recurrente: form.recurrente,
      });
      setForm({ ...VACIO, fecha: form.fecha });
      toast("Bono agregado");
      cargar();
      onCambio?.();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar(bono) {
    try {
      await api.delete(`/empleados/bonos/${bono.id}`);
      toast("Bono eliminado");
      cargar();
      onCambio?.();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  const total = bonos.reduce((s, b) => s + Number(b.monto), 0);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`Bonos — ${persona?.nombre ?? ""}`}
      size="md"
      footer={
        <button type="button" className="btn-secondary" onClick={onClose}>
          Cerrar
        </button>
      }
    >
      <div className="space-y-4">
        <form onSubmit={agregar} className="rounded-xl border border-border p-3.5 space-y-3">
          <div className="flex items-center gap-2 text-sm font-medium text-content">
            <Gift size={16} className="text-content-muted" aria-hidden="true" />
            Nuevo bono
          </div>

          <Field label="Concepto" required>
            <Input
              value={form.concepto}
              onChange={(e) => setForm((f) => ({ ...f, concepto: e.target.value }))}
              placeholder="Bono de productividad"
              maxLength={120}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Monto (C$)" required>
              <Input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={form.monto}
                onChange={(e) => setForm((f) => ({ ...f, monto: e.target.value }))}
                placeholder="1000"
              />
            </Field>
            <Field label="Fecha de pago" required>
              <Input
                type="date"
                value={form.fecha}
                onChange={(e) => setForm((f) => ({ ...f, fecha: e.target.value }))}
              />
            </Field>
          </div>

          <Checkbox
            label="Repetir cada mes desde esa fecha"
            checked={form.recurrente}
            onChange={(e) => setForm((f) => ({ ...f, recurrente: e.target.checked }))}
          />

          <Button
            type="submit"
            icon={Plus}
            loading={guardando}
            disabled={!form.concepto.trim() || !(Number(form.monto) > 0)}
            className="w-full"
          >
            Agregar bono
          </Button>
        </form>

        {cargando ? (
          <TableSkeleton filas={3} columnas={3} />
        ) : bonos.length === 0 ? (
          <p className="text-sm text-content-muted text-center py-4">
            Sin bonos registrados para esta persona.
          </p>
        ) : (
          <>
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Concepto</th>
                  <th className="th text-right">Monto</th>
                  <th className="th text-right">Acción</th>
                </tr>
              </thead>
              <tbody>
                {bonos.map((b) => (
                  <tr key={b.id} className="table-row">
                    <td className="td">
                      <p className="text-sm text-content">{b.concepto}</p>
                      <p className="text-xs text-content-subtle">
                        {b.fecha}
                        {b.recurrente && " · mensual"}
                      </p>
                    </td>
                    <td className="td text-right tabular">{fmtMoney(b.monto)}</td>
                    <td className="td text-right">
                      <IconButton
                        label="Eliminar bono"
                        icon={Trash2}
                        onClick={() => eliminar(b)}
                        className="text-red-500 hover:bg-red-500/10"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div className="flex justify-between border-t border-border pt-3 text-sm">
              <span className="text-content-muted">Total en bonos</span>
              <span className="font-semibold tabular">{fmtMoney(total)}</span>
            </div>
          </>
        )}

        <p className="text-xs text-content-subtle">
          Los bonos se suman al salario del periodo y pagan INSS e IR como salario.
        </p>
      </div>
    </Modal>
  );
}
