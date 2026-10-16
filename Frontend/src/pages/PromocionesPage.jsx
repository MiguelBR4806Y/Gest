import { useCallback, useEffect, useState } from "react";
import { DollarSign, Pencil, Percent, Plus, Tag, Trash2 } from "lucide-react";

import Modal, { ConfirmDialog } from "../components/Modal";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState } from "../components/ui/Card";
import { Checkbox, Field, Input, Select } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";

const TIPOS = [
  { value: "porcentaje", label: "Descuento por porcentaje", icon: Percent },
  { value: "monto_fijo", label: "Descuento de monto fijo (C$)", icon: DollarSign },
  { value: "2x1", label: "2x1 (lleva dos, paga uno)", icon: Tag },
];

const VACIO = { nombre: "", tipo: "porcentaje", valor: 0, activa: true };

function descripcionValor(p) {
  if (p.tipo === "porcentaje") return `${p.valor}%`;
  if (p.tipo === "monto_fijo") return `C$ ${p.valor}`;
  return "2x1";
}

export default function PromocionesPage() {
  const { toast } = useToast();

  const [promos, setPromos] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get("/promociones/");
      setPromos(Array.isArray(data) ? data : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function abrirNueva() {
    setEditando(null);
    setForm(VACIO);
    setAbierta(true);
  }

  function abrirEditar(p) {
    setEditando(p.id);
    setForm({ nombre: p.nombre, tipo: p.tipo, valor: p.valor, activa: p.activa });
    setAbierta(true);
  }

  async function guardar() {
    if (!form.nombre.trim()) return;
    setGuardando(true);
    try {
      const cuerpo = { ...form, nombre: form.nombre.trim(), valor: Number(form.valor) || 0 };
      if (editando) await api.put(`/promociones/${editando}`, cuerpo);
      else await api.post("/promociones/", cuerpo);
      setAbierta(false);
      toast(editando ? "Promoción actualizada" : "Promoción creada");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar() {
    if (!aEliminar) return;
    setGuardando(true);
    try {
      await api.delete(`/promociones/${aEliminar.id}`);
      toast("Promoción eliminada");
      setAEliminar(null);
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  const activas = promos.filter((p) => p.activa).length;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Promociones</h1>
          <p>
            {activas} activa{activas === 1 ? "" : "s"} · {promos.length} en total
          </p>
        </div>
        <Button icon={Plus} onClick={abrirNueva}>
          Nueva promoción
        </Button>
      </div>

      {cargando ? (
        <TableSkeleton filas={5} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {promos.length === 0 ? (
            <EmptyState
              icon={Tag}
              title="Sin promociones"
              text="Crea una promoción y asígnala a tus productos desde Inventario."
              action={
                <Button size="sm" icon={Plus} onClick={abrirNueva}>
                  Crear promoción
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Nombre</th>
                    <th className="th hidden sm:table-cell">Tipo</th>
                    <th className="th text-right">Valor</th>
                    <th className="th text-center">Estado</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {promos.map((p) => (
                    <tr key={p.id} className="table-row">
                      <td className="td font-medium max-w-[14rem] truncate">{p.nombre}</td>
                      <td className="td hidden sm:table-cell text-content-muted">
                        {TIPOS.find((t) => t.value === p.tipo)?.label ?? p.tipo}
                      </td>
                      <td className="td text-right font-medium tabular">
                        {descripcionValor(p)}
                      </td>
                      <td className="td text-center">
                        <span className={p.activa ? "badge-green" : "badge-neutral"}>
                          {p.activa ? "Activa" : "Inactiva"}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton label="Editar" icon={Pencil} onClick={() => abrirEditar(p)} />
                          <IconButton
                            label="Eliminar"
                            icon={Trash2}
                            onClick={() => setAEliminar(p)}
                            className="text-red-600 dark:text-red-400 hover:bg-red-500/10"
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
      )}

      <Modal
        open={abierta}
        onClose={() => setAbierta(false)}
        title={editando ? "Editar promoción" : "Nueva promoción"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAbierta(false)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={guardar} loading={guardando} disabled={!form.nombre.trim()}>
              {editando ? "Guardar cambios" : "Crear promoción"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Nombre" required>
            <Input
              value={form.nombre}
              onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              placeholder="Ej: Descuento de temporada"
              maxLength={120}
            />
          </Field>

          <Field label="Tipo de promoción">
            <Select
              value={form.tipo}
              onChange={(e) =>
                setForm((f) => ({
                  ...f,
                  tipo: e.target.value,
                  valor: e.target.value === "2x1" ? 0 : f.valor,
                }))
              }
            >
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </Field>

          {form.tipo !== "2x1" && (
            <Field
              label={form.tipo === "porcentaje" ? "Porcentaje de descuento" : "Monto a descontar (C$)"}
              hint={
                form.tipo === "porcentaje"
                  ? "Se aplica sobre el subtotal de la venta."
                  : "No puede superar el total de la venta."
              }
            >
              <Input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                max={form.tipo === "porcentaje" ? 100 : undefined}
                value={form.valor}
                onChange={(e) => setForm((f) => ({ ...f, valor: e.target.value }))}
              />
            </Field>
          )}

          <Checkbox
            label="Activa"
            checked={form.activa}
            onChange={(e) => setForm((f) => ({ ...f, activa: e.target.checked }))}
          />
        </div>
      </Modal>

      <ConfirmDialog
        open={Boolean(aEliminar)}
        onClose={() => setAEliminar(null)}
        onConfirm={eliminar}
        loading={guardando}
        title="Eliminar promoción"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.nombre ?? ""}". Los productos que la tengan asignada quedarán sin promoción.`}
      />
    </div>
  );
}
