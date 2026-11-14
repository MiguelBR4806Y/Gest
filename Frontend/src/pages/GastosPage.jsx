import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Trash2, Wallet } from "lucide-react";

import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import Modal, { ConfirmDialog } from "../components/Modal";

const CATEGORIAS = ["operativo", "compra", "servicios", "alquiler", "salarios", "impuestos", "otro"];

const VACIO = { concepto: "", categoria: "operativo", monto: "", proveedor_id: "" };

function hoyISO() {
  return new Date().toISOString().slice(0, 10);
}

export default function GastosPage() {
  const { toast } = useToast();
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [categoria, setCategoria] = useState("");
  const [datos, setDatos] = useState({ items: [], total: 0, por_categoria: [] });
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const params = new URLSearchParams();
      if (desde) params.set("desde", desde);
      if (hasta) params.set("hasta", hasta);
      if (categoria) params.set("categoria", categoria);
      const consulta = params.toString();

      const [gastos, provs] = await Promise.all([
        api.get(`/gastos/${consulta ? `?${consulta}` : ""}`),
        api.get("/proveedores/").catch(() => []),
      ]);
      setDatos({
        items: gastos?.items ?? [],
        total: gastos?.total ?? 0,
        por_categoria: gastos?.por_categoria ?? [],
      });
      setProveedores(Array.isArray(provs) ? provs : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [desde, hasta, categoria, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const gastosDeCompra = useMemo(
    () => datos.items.filter((g) => g.compra_id).length,
    [datos.items]
  );

  function abrirNuevo() {
    setForm({ ...VACIO });
    setEditando(null);
    setAbierta(true);
  }

  function abrirEdicion(g) {
    setForm({
      concepto: g.concepto,
      categoria: g.categoria,
      monto: String(g.monto),
      proveedor_id: g.proveedor_id ? String(g.proveedor_id) : "",
    });
    setEditando(g.id);
    setAbierta(true);
  }

  async function guardar(e) {
    e?.preventDefault();
    if (!form.concepto.trim() || form.monto === "") return;
    setGuardando(true);
    try {
      const cuerpo = {
        concepto: form.concepto.trim(),
        categoria: form.categoria,
        monto: Number(form.monto) || 0,
        proveedor_id: form.proveedor_id ? Number(form.proveedor_id) : null,
      };
      if (editando) await api.put(`/gastos/${editando}`, cuerpo);
      else await api.post("/gastos/", cuerpo);
      setAbierta(false);
      toast(editando ? "Gasto actualizado" : "Gasto registrado");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar() {
    setGuardando(true);
    try {
      await api.delete(`/gastos/${aEliminar.id}`);
      toast("Gasto eliminado");
      setAEliminar(null);
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Gastos</h1>
          <p>{datos.items.length} registrados en el periodo</p>
        </div>
        <Button icon={Plus} onClick={abrirNuevo}>
          Registrar gasto
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Wallet} label="Total del periodo" value={fmtMoney(datos.total)} tono="red" />
        <StatCard icon={Wallet} label="Registros" value={datos.items.length} />
        <StatCard
          icon={Wallet}
          label="Origen compras"
          value={gastosDeCompra}
          tono="yellow"
          sub="Generados por compras"
        />
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Desde">
            <Input type="date" value={desde} max={hasta || hoyISO()} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} />
          </Field>
          <Field label="Categoría">
            <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
              <option value="">Todas</option>
              {CATEGORIAS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Card>

      {datos.por_categoria.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {datos.por_categoria.map((c) => (
            <span key={c.categoria} className="badge-neutral">
              {c.categoria}: {fmtMoney(c.total)} ({c.cantidad})
            </span>
          ))}
        </div>
      )}

      {cargando ? (
        <TableSkeleton filas={5} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {datos.items.length === 0 ? (
            <EmptyState
              icon={Wallet}
              title="Sin gastos en el periodo"
              text="Registra servicios, alquiler o compras para saber cuánto cuesta operar."
              action={<Button icon={Plus} onClick={abrirNuevo}>Registrar gasto</Button>}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Concepto</th>
                    <th className="th hidden sm:table-cell">Categoría</th>
                    <th className="th hidden md:table-cell">Proveedor</th>
                    <th className="th text-right">Monto</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((g) => (
                    <tr key={g.id} className="table-row">
                      <td className="td">
                        <p className="font-medium text-content">{g.concepto}</p>
                        <p className="text-xs text-content-subtle">
                          {new Date(g.fecha).toLocaleDateString("es-NI")}
                          {g.compra_id && " · desde compra"}
                        </p>
                      </td>
                      <td className="td hidden sm:table-cell">
                        <span className="badge-neutral">{g.categoria}</span>
                      </td>
                      <td className="td hidden md:table-cell text-content-muted">
                        {g.proveedor_nombre || "—"}
                      </td>
                      <td className="td text-right tabular font-medium">{fmtMoney(g.monto)}</td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton
                            label="Editar"
                            icon={Pencil}
                            onClick={() => abrirEdicion(g)}
                            disabled={Boolean(g.compra_id)}
                          />
                          <IconButton
                            label="Eliminar"
                            icon={Trash2}
                            onClick={() => setAEliminar(g)}
                            disabled={Boolean(g.compra_id)}
                            className="text-red-500 hover:bg-red-500/10"
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
        title={editando ? "Editar gasto" : "Nuevo gasto"}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAbierta(false)}>
              Cancelar
            </button>
            <Button
              onClick={guardar}
              loading={guardando}
              disabled={!form.concepto.trim() || form.monto === ""}
            >
              {editando ? "Guardar cambios" : "Registrar gasto"}
            </Button>
          </>
        }
      >
        <form onSubmit={guardar} className="space-y-4">
          <Field label="Concepto" required>
            <Input
              value={form.concepto}
              onChange={(e) => setForm((f) => ({ ...f, concepto: e.target.value }))}
              placeholder="Alquiler del local"
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Monto (C$)" required>
              <Input
                type="number"
                min="0"
                step="0.01"
                value={form.monto}
                onChange={(e) => setForm((f) => ({ ...f, monto: e.target.value }))}
                placeholder="0.00"
              />
            </Field>
            <Field label="Categoría">
              <Select
                value={form.categoria}
                onChange={(e) => setForm((f) => ({ ...f, categoria: e.target.value }))}
              >
                {CATEGORIAS.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field label="Proveedor" hint="Opcional">
            <Select
              value={form.proveedor_id}
              onChange={(e) => setForm((f) => ({ ...f, proveedor_id: e.target.value }))}
            >
              <option value="">Sin proveedor</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
          </Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(aEliminar)}
        onClose={() => setAEliminar(null)}
        onConfirm={eliminar}
        loading={guardando}
        title="Eliminar gasto"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.concepto ?? ""}".`}
      />
    </div>
  );
}
