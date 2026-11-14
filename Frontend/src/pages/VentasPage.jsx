import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Ban, Calculator, Download, Eye, Minus, Package, Plus, ScanLine, Search,
  ShoppingCart, Send, Tag, Trash2, TrendingUp, XCircle,
} from "lucide-react";

import Modal from "../components/Modal";
import EnviarFacturaModal from "../components/EnviarFacturaModal";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Select, Textarea } from "../components/ui/Field";
import { BadgeEstado, BadgeMetodoPago, TableSkeleton } from "../components/ui/Feedback";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { api, formatFechaHora, formatHora, fmtMoney, fmtMoneyUSD } from "../lib/api";

const METODOS = [
  { value: "efectivo", label: "Efectivo" },
  { value: "tarjeta", label: "Tarjeta" },
  { value: "transferencia", label: "Transferencia" },
  { value: "credito", label: "Crédito" },
];

const ESTADOS = [
  { value: "todas", label: "Todas" },
  { value: "completada", label: "Completadas" },
  { value: "anulada", label: "Anuladas" },
];

const nuevaClaveCobro = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const hoyISO = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function VentasPage() {
  const { toast } = useToast();
  const { user, esAdmin } = useAuth();
  const tasa = Number(user?.tasa_cambio) || 36;

  const [fecha, setFecha] = useState(hoyISO);
  const [estadoFiltro, setEstadoFiltro] = useState("todas");
  const [ventas, setVentas] = useState([]);
  const [resumen, setResumen] = useState({
    total: 0, transacciones: 0, promedio: 0, anuladas: { numero: 0, total: 0 },
  });
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);

  const [nuevaAbierta, setNuevaAbierta] = useState(false);
  const [detalle, setDetalle] = useState(null);
  const [detalleAbierto, setDetalleAbierto] = useState(false);
  const [aAnular, setAAnular] = useState(null);
  const [motivo, setMotivo] = useState("");
  const [aEnviar, setAEnviar] = useState(null);

  const [cierreAbierto, setCierreAbierto] = useState(false);
  const [cierre, setCierre] = useState(null);

  const [clientes, setClientes] = useState([]);
  const [productos, setProductos] = useState([]);
  const [form, setForm] = useState({ cliente_id: "", metodo_pago: "efectivo" });
  const [efectivoRecibido, setEfectivoRecibido] = useState("");
  const [items, setItems] = useState([]);
  const [productoSel, setProductoSel] = useState("");
  const [cantidad, setCantidad] = useState(1);
  const [escaneo, setEscaneo] = useState("");
  const [claveCobro, setClaveCobro] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const refEscaneo = useRef(null);

  // Atajo F2: abrir el cobro sin soltar el teclado.
  const abrirNuevaRef = useRef(null);
  const nuevaAbiertaRef = useRef(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const params = new URLSearchParams({
        desde: fecha,
        hasta: fecha,
        estado: estadoFiltro,
        limite: "200",
      });
      if (busquedaDiferida.trim()) params.set("busqueda", busquedaDiferida.trim());

      const [lista, dia] = await Promise.all([
        api.get(`/ventas/?${params.toString()}`),
        api.get(`/ventas/resumen-dia?fecha=${fecha}`),
      ]);

      setVentas(Array.isArray(lista?.items) ? lista.items : []);
      setResumen({
        total: dia.total_ventas ?? 0,
        transacciones: dia.numero_ventas ?? 0,
        promedio: dia.ticket_promedio ?? 0,
        anuladas: dia.anuladas ?? { numero: 0, total: 0 },
      });
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [fecha, estadoFiltro, busquedaDiferida, toast]);

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
    setEfectivoRecibido("");
    setItems([]);
    setProductoSel("");
    setCantidad(1);
    setEscaneo("");
    setClaveCobro(nuevaClaveCobro());
    setNuevaAbierta(true);
    setTimeout(() => refEscaneo.current?.focus(), 50);
  }

  function agregarProducto(prod, cant = 1) {
    if (!prod) return;
    const cantidadFinal = Math.max(1, Number(cant) || 1);

    setItems((it) => {
      const idx = it.findIndex((i) => i.producto_id === prod.id);
      const yaEnCarrito = idx >= 0 ? it[idx].cantidad : 0;
      if (yaEnCarrito + cantidadFinal > prod.stock) {
        toast(`Solo quedan ${prod.stock} unidades de ${prod.nombre}`, "error");
        return it;
      }
      if (idx >= 0) {
        return it.map((i, k) =>
          k === idx ? { ...i, cantidad: i.cantidad + cantidadFinal } : i
        );
      }
      return [
        ...it,
        {
          producto_id: prod.id,
          nombre: prod.nombre,
          precio: prod.precio,
          codigo_barras: prod.codigo_barras,
          cantidad: cantidadFinal,
          promocion: prod.promocion || null,
        },
      ];
    });
  }

  function agregarItem() {
    const prod = productos.find((p) => String(p.id) === String(productoSel));
    if (!prod) return;
    agregarProducto(prod, cantidad);
    setProductoSel("");
    setCantidad(1);
  }

  /** Escáner: busca por código de barras, id o nombre exacto/parcial. */
  async function alEscanear(e) {
    e.preventDefault();
    const codigo = escaneo.trim();
    if (!codigo) return;

    let prod = productos.find(
      (p) => String(p.codigo_barras || "") === codigo || String(p.id) === codigo
    );

    if (!prod) {
      try {
        prod = await api.get(`/productos/codigo/${encodeURIComponent(codigo)}`);
      } catch {
        const coincidencias = productos.filter((p) =>
          p.nombre.toLowerCase().includes(codigo.toLowerCase())
        );
        if (coincidencias.length === 1) {
          prod = coincidencias[0];
        } else if (coincidencias.length > 1) {
          toast(`"${codigo}" coincide con varios productos`, "error");
          return;
        }
      }
    }

    if (!prod) {
      toast(`No hay ningún producto con el código ${codigo}`, "error");
      setEscaneo("");
      return;
    }

    agregarProducto(prod, 1);
    setEscaneo("");
    refEscaneo.current?.focus();
  }

  const totalVenta = items.reduce((s, i) => s + Number(i.precio) * i.cantidad, 0);
  const esEfectivo = form.metodo_pago === "efectivo";
  const recibidoNum = Number(efectivoRecibido);
  const vuelto =
    esEfectivo && efectivoRecibido !== "" && Number.isFinite(recibidoNum)
      ? recibidoNum - totalVenta
      : null;
  const efectivoInvalido = esEfectivo && (efectivoRecibido === "" || vuelto < 0);
  const faltaEfectivo = esEfectivo && efectivoRecibido === "";

  async function registrar() {
    if (items.length === 0) return;
    if (faltaEfectivo) {
      toast("Indica con cuánto pagó el cliente", "error");
      return;
    }
    if (esEfectivo && vuelto < 0) {
      toast("El efectivo recibido es menor que el total", "error");
      return;
    }
    setGuardando(true);
    try {
      // La clave evita que un reintento de red cree una segunda venta.
      const clave = claveCobro || nuevaClaveCobro();
      const r = await api.post(
        "/ventas/",
        {
          cliente_id: form.cliente_id ? Number(form.cliente_id) : null,
          metodo_pago: form.metodo_pago,
          efectivo_recibido: esEfectivo ? recibidoNum : null,
          items: items.map((i) => ({ producto_id: i.producto_id, cantidad: i.cantidad })),
        },
        { headers: { "Idempotency-Key": clave } }
      );
      setClaveCobro(null);
      setNuevaAbierta(false);
      const cambio =
        r.vuelto !== null && r.vuelto !== undefined ? ` · Vuelto ${fmtMoney(r.vuelto)}` : "";
      toast(
        r.promos_aplicadas?.length
          ? `Venta registrada${cambio}. Promociones: ${r.promos_aplicadas.join(", ")}`
          : `Venta registrada${cambio}`
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
      await api.delete(`/ventas/${aAnular.id}`, { motivo });
      toast("Venta anulada: stock y crédito restaurados");
      setAAnular(null);
      setMotivo("");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function abrirCierre() {
    setCierreAbierto(true);
    setCierre(null);
    try {
      setCierre(await api.get(`/ventas/cierre?fecha=${fecha}`));
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function exportar() {
    try {
      await api.descargar(
        `/reportes/exportar?desde=${fecha}&hasta=${fecha}`,
        `ventas_${fecha}.csv`
      );
    } catch (e) {
      toast(e.message, "error");
    }
  }

  abrirNuevaRef.current = abrirNueva;
  nuevaAbiertaRef.current = nuevaAbierta;

  useEffect(() => {
    function alPresionar(e) {
      if (e.key !== "F2") return;
      e.preventDefault();
      if (!nuevaAbiertaRef.current) abrirNuevaRef.current?.();
    }
    window.addEventListener("keydown", alPresionar);
    return () => window.removeEventListener("keydown", alPresionar);
  }, []);

  function cambiarCantidad(productoId, delta) {
    const stock = productos.find((p) => p.id === productoId)?.stock ?? Infinity;
    setItems((it) =>
      it.map((i) => {
        if (i.producto_id !== productoId) return i;
        const nueva = i.cantidad + delta;
        if (nueva < 1) return i;
        if (nueva > stock) {
          toast(`Solo quedan ${stock} unidades de ${i.nombre}`, "error");
          return i;
        }
        return { ...i, cantidad: nueva };
      })
    );
  }

  const ventasFiltradas = useMemo(() => {
    const q = busquedaDiferida.trim().toLowerCase();
    if (!q) return ventas;
    return ventas.filter(
      (v) =>
        String(v.cliente_nombre || "").toLowerCase().includes(q) ||
        String(v.productos || "").toLowerCase().includes(q)
    );
  }, [ventas, busquedaDiferida]);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Ventas</h1>
          <p>Registro y control de transacciones</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {esAdmin && (
            <>
              <Button variant="secondary" icon={Calculator} onClick={abrirCierre}>
                Cierre de caja
              </Button>
              <Button variant="secondary" icon={Download} onClick={exportar}>
                CSV
              </Button>
            </>
          )}
          <Button icon={Plus} onClick={abrirNueva} title="Nueva venta (F2)">
            Nueva venta
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          icon={TrendingUp}
          label="Total del día"
          value={fmtMoney(resumen.total)}
          sub={fmtMoneyUSD(resumen.total / tasa)}
          tono="green"
        />
        <StatCard icon={ShoppingCart} label="Transacciones" value={resumen.transacciones} />
        <StatCard icon={Package} label="Ticket promedio" value={fmtMoney(resumen.promedio)} tono="yellow" />
        <StatCard
          icon={Ban}
          label="Anuladas"
          value={resumen.anuladas?.numero ?? 0}
          sub={fmtMoney(resumen.anuladas?.total ?? 0)}
          tono={resumen.anuladas?.numero > 0 ? "red" : "brand"}
        />
      </div>

      <div className="flex flex-col lg:flex-row gap-3">
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

        <div className="segmented shrink-0">
          {ESTADOS.map((e) => (
            <button
              key={e.value}
              type="button"
              onClick={() => setEstadoFiltro(e.value)}
              className={`segment ${estadoFiltro === e.value ? "segment-active" : ""}`}
              aria-pressed={estadoFiltro === e.value}
            >
              {e.label}
            </button>
          ))}
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
        <TableSkeleton filas={6} columnas={6} />
      ) : (
        <Card className="overflow-hidden">
          {ventasFiltradas.length === 0 ? (
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
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th w-12">#</th>
                    <th className="th">Cliente</th>
                    <th className="th hidden lg:table-cell">Productos</th>
                    <th className="th hidden sm:table-cell">Hora</th>
                    <th className="th hidden md:table-cell">Estado</th>
                    <th className="th text-right">Total</th>
                    <th className="th hidden sm:table-cell">Método</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {ventasFiltradas.map((v, i) => {
                    const anulada = v.estado === "anulada";
                    return (
                      <tr key={v.id ?? i} className={`table-row ${anulada ? "opacity-60" : ""}`}>
                        <td className="td text-content-subtle tabular">{v.id}</td>
                        <td className={`td font-medium max-w-[10rem] truncate ${anulada ? "line-through" : ""}`}>
                          {v.cliente_nombre || "Consumidor final"}
                        </td>
                        <td className="td hidden lg:table-cell text-content-muted text-xs max-w-[16rem] truncate">
                          {v.productos || "—"}
                        </td>
                        <td className="td hidden sm:table-cell text-content-muted whitespace-nowrap">
                          {formatHora(v.fecha_hora)}
                        </td>
                        <td className="td hidden md:table-cell">
                          <BadgeEstado estado={v.estado} />
                        </td>
                        <td className={`td text-right font-semibold tabular ${anulada ? "line-through" : ""}`}>
                          {fmtMoney(v.total)}
                        </td>
                        <td className="td hidden sm:table-cell">
                          <BadgeMetodoPago metodo={v.metodo_pago} />
                        </td>
                        <td className="td">
                          <div className="flex items-center justify-end gap-0.5">
                            <IconButton label="Ver detalle" icon={Eye} onClick={() => verDetalle(v)} />
                            <IconButton
                              label="Enviar factura"
                              icon={Send}
                              onClick={() => setAEnviar(v)}
                            />
                            {!anulada && esAdmin && (
                              <IconButton
                                label="Anular venta"
                                icon={XCircle}
                                onClick={() => {
                                  setAAnular(v);
                                  setMotivo("");
                                }}
                                className="text-red-600 dark:text-red-400 hover:bg-red-500/10"
                              />
                            )}
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

      <EnviarFacturaModal
        venta={aEnviar}
        open={Boolean(aEnviar)}
        onClose={() => setAEnviar(null)}
      />

      {/* Nueva venta */}
      <Modal
        open={nuevaAbierta}
        onClose={() => setNuevaAbierta(false)}
        title="Nueva venta"
        size="lg"
        footer={
          <>
            <span className="mr-auto hidden sm:flex items-center gap-1.5 text-[11px] text-content-subtle">
              <kbd className="kbd">⌘/Ctrl</kbd> + <kbd className="kbd">Enter</kbd> para cobrar
            </span>
            <Button variant="secondary" onClick={() => setNuevaAbierta(false)} disabled={guardando}>
              Cancelar
            </Button>
            <Button
              onClick={registrar}
              loading={guardando}
              disabled={items.length === 0 || efectivoInvalido}
            >
              Cobrar {items.length > 0 && fmtMoney(totalVenta)}
            </Button>
          </>
        }
      >
        <div
          className="space-y-4"
          onKeyDown={(e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && items.length > 0) {
              e.preventDefault();
              registrar();
            }
          }}
        >
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

            <Field
              label="Método de pago"
              hint={form.metodo_pago === "credito" ? "Requiere cliente seleccionado." : undefined}
            >
              <Select
                value={form.metodo_pago}
                onChange={(e) => {
                  const metodo = e.target.value;
                  setForm((f) => ({ ...f, metodo_pago: metodo }));
                  // El efectivo solo tiene sentido si se paga en efectivo.
                  if (metodo !== "efectivo") setEfectivoRecibido("");
                }}
              >
                {METODOS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </Select>
            </Field>
          </div>

          <div className="p-3.5 rounded-lg bg-surface-sunken border border-border space-y-3">
            <form onSubmit={alEscanear} className="flex items-center gap-2">
              <ScanLine size={17} className="text-content-muted shrink-0" aria-hidden="true" />
              <Input
                ref={refEscaneo}
                value={escaneo}
                onChange={(e) => setEscaneo(e.target.value)}
                placeholder="Escanea un código de barras o escribe y pulsa Enter"
                aria-label="Escáner de código de barras"
                autoComplete="off"
              />
            </form>

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
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      agregarItem();
                    }
                  }}
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
                      <td className="td">
                        <div className="flex justify-center">
                          <div className="stepper">
                            <button
                              type="button"
                              className="stepper-btn rounded-l-lg"
                              onClick={() => cambiarCantidad(it.producto_id, -1)}
                              disabled={it.cantidad <= 1}
                              aria-label={`Quitar una unidad de ${it.nombre}`}
                            >
                              <Minus size={13} aria-hidden="true" />
                            </button>
                            <span className="stepper-value" aria-live="polite">
                              {it.cantidad}
                            </span>
                            <button
                              type="button"
                              className="stepper-btn rounded-r-lg"
                              onClick={() => cambiarCantidad(it.producto_id, 1)}
                              aria-label={`Agregar una unidad de ${it.nombre}`}
                            >
                              <Plus size={13} aria-hidden="true" />
                            </button>
                          </div>
                        </div>
                      </td>
                      <td className="td text-right tabular text-content-muted">{fmtMoney(it.precio)}</td>
                      <td className="td text-right font-medium tabular">
                        {fmtMoney(Number(it.precio) * it.cantidad)}
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
                    <td colSpan={3} className="td text-right">
                      <span className="block text-xs font-normal text-content-subtle">
                        {items.reduce((s, i) => s + i.cantidad, 0)} artículo(s)
                      </span>
                      <span className="font-semibold">Total</span>
                    </td>
                    <td className="td text-right font-bold text-base tabular">
                      {fmtMoney(totalVenta)}
                      <span className="block text-xs font-normal text-content-subtle">
                        {fmtMoneyUSD(totalVenta / tasa)}
                      </span>
                    </td>
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          {esEfectivo && (
            <div className="mt-3 rounded-xl border border-border bg-surface-sunken p-3.5 space-y-2.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <Field
                  label="Efectivo recibido (C$)"
                  required
                  error={vuelto !== null && vuelto < 0 ? "No alcanza para cubrir el total" : undefined}
                >
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={efectivoRecibido}
                    onChange={(e) => setEfectivoRecibido(e.target.value)}
                    placeholder={totalVenta > 0 ? String(totalVenta.toFixed(2)) : "0.00"}
                    autoFocus
                  />
                </Field>
                <div>
                  <span className="label">Vuelto</span>
                  <p
                    className={`text-xl font-bold tabular ${
                      vuelto === null
                        ? "text-content-subtle"
                        : vuelto < 0
                          ? "text-red-600 dark:text-red-400"
                          : "text-secondary-600 dark:text-secondary-400"
                    }`}
                  >
                    {vuelto === null ? "—" : fmtMoney(Math.max(vuelto, 0))}
                  </p>
                  {vuelto !== null && vuelto < 0 && (
                    <p className="text-xs text-red-600 dark:text-red-400">Faltan {fmtMoney(-vuelto)}</p>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => setEfectivoRecibido(totalVenta.toFixed(2))}
                >
                  Pago exacto
                </button>
                {[50, 100, 200, 500, 1000].map((billete) => (
                  <button
                    key={billete}
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() =>
                      setEfectivoRecibido(
                        (Math.ceil(totalVenta / billete) * billete || billete).toFixed(2)
                      )
                    }
                  >
                    C${billete}
                  </button>
                ))}
              </div>
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
                <dt className="text-content-muted text-xs">Fecha</dt>
                <dd className="text-content mt-0.5">{formatFechaHora(detalle.fecha_hora)}</dd>
              </div>
              <div>
                <dt className="text-content-muted text-xs">Estado</dt>
                <dd className="mt-0.5">
                  <BadgeEstado estado={detalle.estado} />
                </dd>
              </div>
              {detalle.efectivo_recibido !== null && detalle.efectivo_recibido !== undefined && (
                <>
                  <div>
                    <dt className="text-content-muted text-xs">Efectivo recibido</dt>
                    <dd className="text-content mt-0.5 tabular">
                      {fmtMoney(detalle.efectivo_recibido)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-content-muted text-xs">Vuelto</dt>
                    <dd className="text-secondary-600 dark:text-secondary-400 font-medium mt-0.5 tabular">
                      {fmtMoney(detalle.vuelto ?? 0)}
                    </dd>
                  </div>
                </>
              )}
              <div>
                <dt className="text-content-muted text-xs">Total</dt>
                <dd className="text-content font-bold tabular mt-0.5">{fmtMoney(detalle.total)}</dd>
              </div>
            </dl>

            {detalle.estado === "anulada" && (
              <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/25 text-xs text-content-muted">
                <p className="font-semibold text-red-600 dark:text-red-400">
                  Venta anulada por {detalle.anulada_por || "—"}
                </p>
                <p className="mt-0.5">
                  {detalle.anulada_en ? formatFechaHora(detalle.anulada_en) : ""}
                  {detalle.motivo_anulacion ? ` · Motivo: ${detalle.motivo_anulacion}` : ""}
                </p>
              </div>
            )}

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
                        {fmtMoney(it.subtotal ?? Number(it.precio_unitario) * it.cantidad)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>

      {/* Anular */}
      <Modal
        open={Boolean(aAnular)}
        onClose={() => setAAnular(null)}
        title={`Anular venta #${aAnular?.id ?? ""}`}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAAnular(null)} disabled={guardando}>
              Cancelar
            </Button>
            <Button variant="danger" onClick={anular} loading={guardando}>
              Anular venta
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-accent-500/5 border border-accent-500/25 text-xs text-content-muted">
            La venta no se borra: queda marcada como anulada, se devuelve el stock y se
            revierte el crédito. La factura histórica conserva su número.
          </div>
          <Field label="Motivo" hint="Queda registrado en la auditoría con tu usuario.">
            <Textarea
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ej: producto defectuoso, error de cobro…"
              maxLength={300}
            />
          </Field>
        </div>
      </Modal>

      {/* Cierre de caja */}
      <Modal
        open={cierreAbierto}
        onClose={() => setCierreAbierto(false)}
        title={`Cierre de caja — ${fecha}`}
        footer={
          <>
            <Button variant="secondary" onClick={exportar} icon={Download}>
              Exportar CSV
            </Button>
            <Button onClick={() => setCierreAbierto(false)}>Listo</Button>
          </>
        }
      >
        {!cierre ? (
          <TableSkeleton filas={4} columnas={2} />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-surface-sunken border border-border">
                <p className="text-xs text-content-muted">Total vendido</p>
                <p className="text-lg font-bold tabular mt-0.5">{fmtMoney(cierre.total)}</p>
              </div>
              <div className="p-3 rounded-lg bg-secondary-500/5 border border-secondary-500/25">
                <p className="text-xs text-content-muted">Efectivo esperado</p>
                <p className="text-lg font-bold tabular mt-0.5">{fmtMoney(cierre.efectivo_esperado)}</p>
              </div>
            </div>

            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Método</th>
                  <th className="th text-right">Operaciones</th>
                  <th className="th text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {cierre.por_metodo.map((m) => (
                  <tr key={m.metodo_pago} className="table-row">
                    <td className="td capitalize">{m.metodo_pago}</td>
                    <td className="td text-right tabular">{m.cantidad}</td>
                    <td className="td text-right font-medium tabular">{fmtMoney(m.total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-border bg-surface-elevated/60">
                  <td className="td font-semibold">Total</td>
                  <td className="td text-right tabular">{cierre.cantidad}</td>
                  <td className="td text-right font-bold tabular">{fmtMoney(cierre.total)}</td>
                </tr>
              </tfoot>
            </table>

            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-content-muted">
              <span>
                Ticket promedio: <strong className="text-content">{fmtMoney(cierre.ticket_promedio)}</strong>
              </span>
              <span>
                Ganancia: <strong className="text-secondary-600 dark:text-secondary-400">{fmtMoney(cierre.ganancia)}</strong>
                {" "}({Number(cierre.margen_pct || 0).toFixed(1)}%)
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-content-muted">
              <span>
                Anuladas: <strong className="text-red-600 dark:text-red-400">{cierre.anuladas.cantidad}</strong>{" "}
                ({fmtMoney(cierre.anuladas.total)})
              </span>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
