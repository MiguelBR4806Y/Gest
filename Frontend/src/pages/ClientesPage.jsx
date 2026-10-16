import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CreditCard, History, Pencil, Plus, Search, Trash2, Users,
} from "lucide-react";

import Modal, { ConfirmDialog } from "../components/Modal";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input } from "../components/ui/Field";
import { BadgeMetodoPago, TableSkeleton } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { api, formatFechaHora, fmtMoney } from "../lib/api";

const VACIO = { nombre: "", telefono: "", credito_limite: 0 };

export default function ClientesPage() {
  const { toast } = useToast();

  const [clientes, setClientes] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);

  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [creditoUsado, setCreditoUsado] = useState(0);

  const [deCliente, setDeCliente] = useState(null);
  const [compras, setCompras] = useState([]);
  const [cargandoCompras, setCargandoCompras] = useState(false);

  const [aEliminar, setAEliminar] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get("/clientes/");
      setClientes(Array.isArray(data) ? data : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  function abrirNuevo() {
    setEditando(null);
    setForm(VACIO);
    setAbierta(true);
  }

  function abrirEditar(c) {
    setEditando(c.id);
    setCreditoUsado(c.credito_usado ?? 0);
    setForm({
      nombre: c.nombre,
      telefono: c.telefono ?? "",
      credito_limite: c.credito_limite ?? 0,
    });
    setAbierta(true);
  }

  async function guardar() {
    if (!form.nombre.trim()) return;
    setGuardando(true);
    try {
      const cuerpo = {
        nombre: form.nombre.trim(),
        telefono: form.telefono.trim() || null,
        credito_limite: Number(form.credito_limite) || 0,
      };
      if (editando) {
        await api.put(`/clientes/${editando}`, { ...cuerpo, credito_usado: Number(creditoUsado) || 0 });
      } else {
        await api.post("/clientes/", cuerpo);
      }
      setAbierta(false);
      toast(editando ? "Cliente actualizado" : "Cliente creado");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function abrirCompras(c) {
    setDeCliente(c);
    setCompras([]);
    setCargandoCompras(true);
    try {
      const data = await api.get(`/clientes/${c.id}/compras`);
      setCompras(Array.isArray(data) ? data : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargandoCompras(false);
    }
  }

  async function eliminar() {
    if (!aEliminar) return;
    setGuardando(true);
    try {
      await api.delete(`/clientes/${aEliminar.id}`);
      toast("Cliente eliminado");
      setAEliminar(null);
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  const filtrados = useMemo(() => {
    const q = busquedaDiferida.trim().toLowerCase();
    if (!q) return clientes;
    return clientes.filter(
      (c) =>
        c.nombre.toLowerCase().includes(q) ||
        (c.telefono ?? "").includes(q) ||
        (c.codigo ?? "").toLowerCase().includes(q)
    );
  }, [clientes, busquedaDiferida]);

  const conCredito = clientes.filter((c) => (c.credito_usado ?? 0) > 0);
  const deudaTotal = conCredito.reduce((s, c) => s + (c.credito_usado ?? 0), 0);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Clientes</h1>
          <p>{clientes.length} registrados</p>
        </div>
        <Button icon={Plus} onClick={abrirNuevo}>
          Agregar cliente
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Users} label="Clientes" value={clientes.length} sub="En cartera" />
        <StatCard
          icon={CreditCard}
          label="Con crédito activo"
          value={conCredito.length}
          sub="Con saldo pendiente"
          tono="yellow"
        />
        <StatCard
          icon={CreditCard}
          label="Deuda total"
          value={fmtMoney(deudaTotal)}
          sub="Por cobrar"
          tono={deudaTotal > 0 ? "red" : "green"}
        />
      </div>

      <div className="relative">
        <Search
          size={16}
          className="absolute left-3.5 top-1/2 -translate-y-1/2 text-content-subtle pointer-events-none"
          aria-hidden="true"
        />
        <Input
          className="pl-10"
          placeholder="Buscar por nombre, teléfono o código…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar clientes"
        />
      </div>

      {cargando ? (
        <TableSkeleton filas={6} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {filtrados.length === 0 ? (
            <EmptyState
              icon={Users}
              title={clientes.length === 0 ? "Sin clientes" : "Sin resultados"}
              text={
                clientes.length === 0
                  ? "Registra clientes para llevar su historial de compras y su crédito."
                  : "Prueba con otro término de búsqueda."
              }
              action={
                clientes.length === 0 && (
                  <Button size="sm" icon={Plus} onClick={abrirNuevo}>
                    Agregar cliente
                  </Button>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Código</th>
                    <th className="th">Nombre</th>
                    <th className="th hidden sm:table-cell">Teléfono</th>
                    <th className="th text-right">Crédito usado</th>
                    <th className="th text-right hidden md:table-cell">Límite</th>
                    <th className="th hidden lg:table-cell">Última compra</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((c) => {
                    const limite = c.credito_limite ?? 0;
                    const usado = c.credito_usado ?? 0;
                    const pct = limite > 0 ? (usado / limite) * 100 : 0;
                    const badge =
                      pct >= 90 ? "badge-red" : pct >= 60 ? "badge-yellow" : "badge-green";
                    return (
                      <tr key={c.id} className="table-row">
                        <td className="td font-mono text-xs font-semibold text-brand-600 dark:text-brand-300">
                          {c.codigo}
                        </td>
                        <td className="td font-medium max-w-[12rem] truncate">{c.nombre}</td>
                        <td className="td hidden sm:table-cell text-content-muted">
                          {c.telefono || "—"}
                        </td>
                        <td className="td text-right">
                          {usado > 0 ? (
                            <span className={badge}>{fmtMoney(usado)}</span>
                          ) : (
                            <span className="text-content-subtle text-xs">—</span>
                          )}
                        </td>
                        <td className="td text-right hidden md:table-cell text-content-muted tabular">
                          {fmtMoney(limite)}
                        </td>
                        <td className="td hidden lg:table-cell text-content-muted text-xs">
                          {c.ultima_compra && c.ultima_compra !== "Sin compras"
                            ? formatFechaHora(c.ultima_compra)
                            : "Sin compras"}
                        </td>
                        <td className="td">
                          <div className="flex items-center justify-end gap-0.5">
                            <IconButton
                              label="Editar"
                              icon={Pencil}
                              onClick={() => abrirEditar(c)}
                            />
                            <IconButton
                              label="Ver historial de compras"
                              icon={History}
                              onClick={() => abrirCompras(c)}
                            />
                            <IconButton
                              label="Eliminar"
                              icon={Trash2}
                              onClick={() => setAEliminar(c)}
                              className="text-red-600 dark:text-red-400 hover:bg-red-500/10"
                            />
                          </div>
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

      <Modal
        open={abierta}
        onClose={() => setAbierta(false)}
        title={editando ? "Editar cliente" : "Agregar cliente"}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAbierta(false)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={guardar} loading={guardando} disabled={!form.nombre.trim()}>
              {editando ? "Guardar cambios" : "Agregar cliente"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Nombre" required>
            <Input
              value={form.nombre}
              onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              placeholder="Nombre del cliente"
              maxLength={120}
            />
          </Field>

          <Field label="Teléfono">
            <Input
              value={form.telefono}
              onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))}
              placeholder="Ej: 8888-8888"
              maxLength={32}
              inputMode="tel"
            />
          </Field>

          <Field label="Límite de crédito (C$)" hint="0 significa que no puede comprar a crédito.">
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={form.credito_limite}
              onChange={(e) => setForm((f) => ({ ...f, credito_limite: e.target.value }))}
            />
          </Field>

          {editando && (
            <Field
              label="Crédito usado (C$)"
              hint="Ajusta manualmente si registraste un abono fuera del sistema."
            >
              <Input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={creditoUsado}
                onChange={(e) => setCreditoUsado(e.target.value)}
              />
            </Field>
          )}

          {editando && (
            <p className="text-xs text-content-subtle">
              El código del cliente es fijo y no se puede modificar.
            </p>
          )}
        </div>
      </Modal>

      <Modal
        open={Boolean(deCliente)}
        onClose={() => setDeCliente(null)}
        title={`Compras — ${deCliente?.nombre ?? ""}`}
        footer={
          <Button variant="secondary" onClick={() => setDeCliente(null)}>
            Cerrar
          </Button>
        }
      >
        {cargandoCompras ? (
          <TableSkeleton filas={4} columnas={3} />
        ) : compras.length === 0 ? (
          <EmptyState
            icon={History}
            title="Sin compras registradas"
            text="Cuando este cliente compre aparecerá aquí su historial."
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th text-right">Total</th>
                <th className="th">Método</th>
                <th className="th text-right">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {compras.map((c, i) => (
                <tr key={c.id ?? i} className="table-row">
                  <td className="td text-right font-medium tabular">{fmtMoney(c.total)}</td>
                  <td className="td">
                    <BadgeMetodoPago metodo={c.metodo_pago} />
                  </td>
                  <td className="td text-right text-content-muted text-xs">
                    {formatFechaHora(c.fecha_hora)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(aEliminar)}
        onClose={() => setAEliminar(null)}
        onConfirm={eliminar}
        loading={guardando}
        title="Eliminar cliente"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.nombre ?? ""}" y sus ventas asociadas dejarán de estar vinculadas a él.`}
      />
    </div>
  );
}
