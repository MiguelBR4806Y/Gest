import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Search, Trash2, Truck } from "lucide-react";

import { api } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Textarea } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import Modal, { ConfirmDialog } from "../components/Modal";

const VACIO = { nombre: "", contacto: "", email: "", telefono: "", notas: "", activo: true };

export default function ProveedoresPage() {
  const { toast } = useToast();
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get("/proveedores/");
      setProveedores(Array.isArray(data) ? data : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const filtrados = useMemo(() => {
    const q = busquedaDiferida.trim().toLowerCase();
    if (!q) return proveedores;
    return proveedores.filter(
      (p) =>
        p.nombre.toLowerCase().includes(q) ||
        (p.contacto ?? "").toLowerCase().includes(q) ||
        (p.email ?? "").toLowerCase().includes(q)
    );
  }, [proveedores, busquedaDiferida]);

  function abrirNuevo() {
    setForm(VACIO);
    setEditando(null);
    setAbierta(true);
  }

  function abrirEdicion(p) {
    setForm({
      nombre: p.nombre,
      contacto: p.contacto ?? "",
      email: p.email ?? "",
      telefono: p.telefono ?? "",
      notas: p.notas ?? "",
      activo: p.activo,
    });
    setEditando(p.id);
    setAbierta(true);
  }

  async function guardar(e) {
    e?.preventDefault();
    if (!form.nombre.trim()) return;
    setGuardando(true);
    try {
      const cuerpo = {
        nombre: form.nombre.trim(),
        contacto: form.contacto.trim() || null,
        email: form.email.trim() || null,
        telefono: form.telefono.trim() || null,
        notas: form.notas.trim() || null,
        activo: form.activo,
      };
      if (editando) await api.put(`/proveedores/${editando}`, cuerpo);
      else await api.post("/proveedores/", cuerpo);
      setAbierta(false);
      toast(editando ? "Proveedor actualizado" : "Proveedor creado");
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
      await api.delete(`/proveedores/${aEliminar.id}`);
      toast("Proveedor eliminado");
      setAEliminar(null);
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  const activos = proveedores.filter((p) => p.activo).length;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Proveedores</h1>
          <p>{proveedores.length} registrados</p>
        </div>
        <Button icon={Plus} onClick={abrirNuevo}>
          Agregar proveedor
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Truck} label="Proveedores" value={proveedores.length} sub="En catálogo" />
        <StatCard icon={Truck} label="Activos" value={activos} tono="green" sub="Disponibles" />
        <StatCard
          icon={Truck}
          label="Inactivos"
          value={proveedores.length - activos}
          tono="yellow"
          sub="Sin compras nuevas"
        />
      </div>

      <div className="relative">
        <Search
          size={16}
          className="absolute left-3.5 top-1/2 -translate-y-1/2 text-content-subtle pointer-events-none"
        />
        <Input
          className="pl-10"
          placeholder="Buscar por nombre, contacto o correo…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar proveedores"
        />
      </div>

      {cargando ? (
        <TableSkeleton filas={5} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {filtrados.length === 0 ? (
            <EmptyState
              icon={Truck}
              title="Sin proveedores"
              text="Registra a quién le compras para controlar gastos y costo de inventario."
              action={<Button icon={Plus} onClick={abrirNuevo}>Agregar proveedor</Button>}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Proveedor</th>
                    <th className="th">Contacto</th>
                    <th className="th hidden sm:table-cell">Teléfono</th>
                    <th className="th hidden md:table-cell">Estado</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((p) => (
                    <tr key={p.id} className="table-row">
                      <td className="td">
                        <p className="font-medium text-content">{p.nombre}</p>
                        {p.email && <p className="text-xs text-content-subtle truncate">{p.email}</p>}
                      </td>
                      <td className="td text-content-muted">{p.contacto || "—"}</td>
                      <td className="td hidden sm:table-cell text-content-muted tabular">
                        {p.telefono || "—"}
                      </td>
                      <td className="td hidden md:table-cell">
                        <span className={`badge ${p.activo ? "badge-green" : "badge-neutral"}`}>
                          {p.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton label="Editar" icon={Pencil} onClick={() => abrirEdicion(p)} />
                          <IconButton
                            label="Eliminar"
                            icon={Trash2}
                            onClick={() => setAEliminar(p)}
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
        title={editando ? "Editar proveedor" : "Nuevo proveedor"}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAbierta(false)}>
              Cancelar
            </button>
            <Button onClick={guardar} loading={guardando} disabled={!form.nombre.trim()}>
              {editando ? "Guardar cambios" : "Crear proveedor"}
            </Button>
          </>
        }
      >
        <form onSubmit={guardar} className="space-y-4">
          <Field label="Nombre" required>
            <Input
              value={form.nombre}
              onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              placeholder="Distribuidora La Unión"
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Contacto">
              <Input
                value={form.contacto}
                onChange={(e) => setForm((f) => ({ ...f, contacto: e.target.value }))}
                placeholder="Nombre del vendedor"
              />
            </Field>
            <Field label="Teléfono">
              <Input
                value={form.telefono}
                onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))}
                placeholder="8888-1234"
              />
            </Field>
          </div>
          <Field label="Correo">
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              placeholder="ventas@proveedor.com"
            />
          </Field>
          <Field label="Notas">
            <Textarea
              value={form.notas}
              onChange={(e) => setForm((f) => ({ ...f, notas: e.target.value }))}
              placeholder="Días de entrega, condiciones de pago…"
            />
          </Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={Boolean(aEliminar)}
        onClose={() => setAEliminar(null)}
        onConfirm={eliminar}
        loading={guardando}
        title="Eliminar proveedor"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.nombre ?? ""}". Si tiene compras o gastos, desactívalo en vez de borrarlo.`}
      />
    </div>
  );
}
