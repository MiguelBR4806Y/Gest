import { useCallback, useEffect, useState } from "react";
import {
  Eye, Package, Plus, Search, ShoppingCart, Tag, Trash2, TrendingUp,
} from "lucide-react";

import Modal, { ConfirmDialog } from "../components/Modal";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Field";
import { BadgeMetodoPago, TableSkeleton } from "../components/ui/Feedback";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { api, formatHora, fmtMoney } from "../lib/api";

const METODOS = [
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta", label: "Tarjeta" },
  { value: "transferencia", label: "Transferencia" },
  { value: "credito", label: "Crédito" },
];

const hoyISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function VentasPage() {
  const { toast } = useToast();

  const [fecha, setFecha] = useState(hoyISO);
  const [ventas, setVentas] = useState([]);
  const [resumen, setResumen] = useState({ total: 0, transacciones: 0, promedio: 0 });
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);

  const [nuevaAbierta, setNuevaAbierta] = useState(false);
  const [detalle, setDetalle] = useState(null);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [aAnular, setAAnular] = useState(null);

  const [clientes, setClientes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [form, setForm] = useState({ cliente_id: "", metodo_pago: "efectivo" });
  const [items, setItems] = useState([]);
  const [productoSel, setProductoSel] = useState("");
  const [cantidad, setCantidad] = useState(1);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get(`/ventas/resumen-dia?fecha=${fecha}`);
      const lista = data.ultimas_ventas ?? [];
      setVentas(lista);
      const total = lista.reduce((s, v) => s + Number(v.total || 0), 0);
      setResumen({
        total,
        transacciones: data.numero_ventas ?? lista.length,
        promedio: lista.length ? total / lista.length : 0,
      });
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [fecha, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  async function abrirNueva() {
    try {
      const [c, p] = await Promise.all([
        api.get("/clientes/").catch(() => []),
        api.get("/productos/").catch(() => []),
      ]);
      setClientes(Array.isArray(c) ? c : []);
      setProductos(Array.isArray(p) ? p : []);
    } catch {
      setClientes([]);
      setProductos([]);
    }
    setForm({ cliente_id: "", metodo_pago: "efectivo" });
    setItems([]);
    setProductoSel("");
    setCantidad(1);
    setNuevaAbierta(true);
  }

  function agregarItem() {
    const prod = productos.find((p) => String(p.id) === String(productoSel));
    if (!prod) return;

    const cant = Math.max(1, Number(cantidad) || 1);

    if (cant > prod.stock) {
      toast(`Solo quedan ${prod.stock} unidades de ${prod.nombre}`, "error");
      return;
    }

    setItems((it) => {
      const idx = it.findIndex((i) => i.producto_id === prod.id);
      if (idx >= 0) {
        const nuevaCant = it[idx].cantidad + cant;
        if (nuevaCant > prod.stock) {
          toast(`Solo quedan ${prod.stock} unidades de ${prod.nombre}`, "error");
          return it;
        }
        return it.map((i, k) => (k === idx ? { ...i, cantidad: nuevaCant } : i));
      }
      return [
        ...it,
        {
          producto_id: prod.id,
          nombre: prod.nombre,
          precio: prod.precio,
          precio_dolar: prod.precio_dolar,
          cantidad: cant,
          promocion: prod.promocion || null,
        },
      ];
    });

    setProductoSel("");
    setCantidad(1);
  }

  const totalVenta = items.reduce((s, i) => s + i.precio * i.cantidad, 0);

  async function registrar() {
    if (items.length === 0) return;
    setGuardando(true);
    try {
      const r = await api.post("/ventas/", {
        cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
        metodo_pago: form.metodo_pago,
        items: items.map((i) => ({ producto_id: i.producto_id, cantidad: i.cantidad })),
      });
      setNuevaAbierta(false);
      toast(
        r.promos_aplicadas?.length
          ? `Venta registrada. Promociones: ${r.promos_aplicadas.join(", ")}`
          : "Venta registrada"
      );
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function verDetalle(v) {
    setDetalleAbierto(true);
    setDetalle(null);
    try {
      setDetalle(await api.get(`/ventas/${v.id}`));
    } catch {
      setDetalle(v);
    }
  }

  async function anular() {
    if (!aAnular) return;
    setGuardando(true);
    try {
      await api.delete(`/ventas/${aAnular.id}`);
      toast("Venta anulada y stock devuelto");
      setAAnular(null);
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  const filtradas = ventas.filter((v) => {
    if (!busquedaDiferida) return true;
    const q = busquedaDiferida.toLowerCase();
    return (
      String(v.cliente_nombre || "").toLowerCase().includes(q) ||
      String(v.productos || "").toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Ventas</h1>
          <p>Registro y control de transacciones</p>
        </div>
        <Button icon={Plus} onClick={abrirNueva}>
          Nueva venta
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={TrendingUp} label="Total del día" value={fmtMoney(resumen.total)} tono="green" />
        <StatCard icon={ShoppingCart} label="Transacciones" value={resumen.transacciones} />
        <StatCard icon={Package} label="Ticket promedio" value={fmtMoney(resumen.promedio)} tono="yellow" />
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
            placeholder="Buscar por cliente o producto…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar ventas"
          />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <label htmlFor="fecha-ventas" className="text-sm text-content-muted whitespace-nowrap">
            Fecha
          </label>
          <Input
            id="fecha-ventas"
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="w-auto"
          />
        </div>
      </div>

      {cargando ? (
        <TableSkeleton filas={6} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {filtradas.length === 0 ? (
            <EmptyState
              icon={ShoppingCart}
              title={ventas.length === 0 ? "Sin ventas en esta fecha" : "Sin resultados"}
              text={
                ventas.length === 0
                  ? "Cambia la fecha o registra una nueva venta."
                  : "Prueba con otro término de búsqueda."
              }
              action={
                ventas.length === 0 && (
                  <Button size="sm" icon={Plus} onClick={abrirNueva}>
                    Registrar venta
                  </Button>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th w-12">#</th>
                    <th className="th">Cliente</th>
                    <th className="th hidden md:table-cell">Productos</th>
                    <th className="th hidden sm:table-cell">Hora</th>
                    <th className="th text-right">Total</th>
                    <th className="th hidden sm:table-cell">Método</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtradas.map((v, i) => (
                    <tr key={v.id ?? i} className="table-row">
                      <td className="td text-content-subtle tabular">{v.id}</td>
                      <td className="td font-medium max-w-[10rem] truncate">
                        {v.cliente_nombre || "Consumidor final"}
                      </td>
                      <td className="td hidden md:table-cell text-content-muted text-xs max-w-[16rem] truncate">
                        {v.productos || "—"}
                      </td>
                      <td className="td hidden sm:table-cell text-content-muted whitespace-nowrap">
                        {formatHora(v.fecha_hora)}
                      </td>
                      <td className="td text-right font-semibold tabular">{fmtMoney(v.total)}</td>
                      <td className="td hidden sm:table-cell">
                        <BadgeMetodoPago metodo={v.metodo_pago} />
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton
                            label="Ver detalle"
                            icon={Eye}
                            onClick={() => verDetalle(v)}
                          />
                          <IconButton
                            label="Anular venta"
                            icon={Trash2}
                            onClick={() => setAAnular(v)}
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

      {/* Nueva venta */}
      <Modal
        open={nuevaAbierta}
        onClose={() => setNuevaAbierta(false)}
        title="Nueva venta"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setNuevaAbierta(false)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={registrar} loading={guardando} disabled={items.length === 0}>
              Registrar venta
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field label="Cliente">
              <Select
                value={form.cliente_id}
                onChange={(e) => setForm((f) => ({ ...f, cliente_id: e.target.value }))}
              >
                <option value="">Consumidor final</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </Select>
            </Field>

            <Field label="Método de pago" hint={form.metodo_pago === "credito" ? "Requiere cliente seleccionado." : undefined}>
              <Select
                value={form.metodo_pago}
                onChange={(e) => setForm((f) => ({ ...f, metodo_pago: e.target.value }))}
              >
                {METODOS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <div className="p-3.5 rounded-lg bg-surface-sunken border border-border">
            <div className="flex flex-col sm:flex-row gap-2 sm:items-end">
              <div className="flex-1 min-w-0">
                <Field label="Producto">
                  <Select value={productoSel} onChange={(e) => setProductoSel(e.target.value)}>
                    <option value="">Seleccionar…</option>
                    {productos.map((p) => (
                      <option key={p.id} value={p.id} disabled={p.stock <= 0}>
                        {p.nombre} — {fmtMoney(p.precio)} ({p.stock} disp.)
                        {p.promocion ? ` · ${p.promocion.nombre}` : ""}
                      </option>
                    ))}
                  </Select>
                </Field>
              </div>
              <Field label="Cantidad">
                <Input
                  type="number"
                  min="1"
                  value={cantidad}
                  onChange={(e) => setCantidad(e.target.value)}
                  className="w-24"
                />
              </Field>
              <Button
                variant="secondary"
                icon={Plus}
                onClick={agregarItem}
                disabled={!productoSel}
                className="shrink-0"
              >
                Agregar
              </Button>
            </div>
          </div>

          {items.length > 0 && (
            <div className="rounded-lg border border-border overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Producto</th>
                    <th className="th text-center">Cant.</th>
                    <th className="th text-right">Precio</th>
                    <th className="th text-right">Subtotal</th>
                    <th className="th w-10" />
                  </tr>
                </thead>
                <tbody>
                  {items.map((it, i) => (
                    <tr key={it.producto_id} className="table-row">
                      <td className="td">
                        <span className="flex items-center gap-1.5 min-w-0">
                          <span className="truncate">{it.nombre}</span>
                          {it.promocion && (
                            <span className="badge-yellow shrink-0">
                              <Tag size={9} aria-hidden="true" />
                              {it.promocion.tipo === "porcentaje"
                                ? `${it.promocion.valor}%`
                                : it.promocion.tipo === "2x1"
                                  ? "2x1"
                                  : `C$${it.promocion.valor}`}
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="td text-center tabular">{it.cantidad}</td>
                      <td className="td text-right tabular text-content-muted">{fmtMoney(it.precio)}</td>
                      <td className="td text-right font-medium tabular">
                        {fmtMoney(it.precio * it.cantidad)}
                      </td>
                      <td className="td">
                        <IconButton
                          label={`Quitar ${it.nombre}`}
                          icon={Trash2}
                          onClick={() => setItems((x) => x.filter((_, k) => k !== i))}
                          className="text-red-600 dark:text-red-400 hover:bg-red-500/10"
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-border bg-surface-elevated/60">
                    <td colSpan={3} className="td text-right font-semibold">
                      Total
                    </td>
                    <td className="td text-right font-bold text-base tabular">{fmtMoney(totalVenta)}</td>
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}
        </div>
      </Modal>

      {/* Detalle */}
      <Modal
        open={detalleAbierto}
        onClose={() => setDetalleAbierto(false)}
        title={detalle ? `Venta #${detalle.id}` : "Detalle de venta"}
        footer={
          <Button variant="secondary" onClick={() => setDetalleAbierto(false)}>
            Cerrar
          </Button>
        }
      >
        {!detalle ? (
          <TableSkeleton filas={3} columnas={3} />
        ) : (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-content-muted text-xs">Cliente</dt>
                <dd className="text-content mt-0.5">{detalle.cliente_nombre || "Consumidor final"}</dd>
              </div>
              <div>
                <dt className="text-content-muted text-xs">Método de pago</dt>
                <dd className="mt-0.5">
                  <BadgeMetodoPago metodo={detalle.metodo_pago} />
                </dd>
              </div>
              <div>
                <dt className="text-content-muted text-xs">Hora</dt>
                <dd className="text-content mt-0.5">{formatHora(detalle.fecha_hora)}</dd>
              </div>
              <div>
                <dt className="text-content-muted text-xs">Total</dt>
                <dd className="text-content font-bold tabular mt-0.5">{fmtMoney(detalle.total)}</dd>
              </div>
            </dl>

            {detalle.items?.length > 0 && (
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Producto</th>
                    <th className="th text-center">Cant.</th>
                    <th className="th text-right">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.items.map((it, i) => (
                    <tr key={i} className="table-row">
                      <td className="td">{it.nombre}</td>
                      <td className="td text-center tabular">{it.cantidad}</td>
                      <td className="td text-right tabular">
                        {fmtMoney(it.subtotal ?? it.precio_unitario * it.cantidad)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(aAnular)}
        onClose={() => setAAnular(null)}
        onConfirm={anular}
        loading={guardando}
        title="Anular venta"
        confirmLabel="Anular venta"
        mensaje={`Se devolverá el stock de los productos y se revertirá el crédito si aplica. La venta #${aAnular?.id ?? ""} se eliminará del historial.`}
      />
    </div>
  );
}
