import { useCallback, useEffect, useMemo, useState } from "react";
import { Ban, Plus, Receipt, Trash2 } from "lucide-react";

import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Select, Textarea } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import Modal, { ConfirmDialog } from "../components/Modal";

const LINEA_VACIA = { producto_id: "", cantidad: 1, costo_unitario: "" };

export default function ComprasPage() {
  const { toast } = useToast();
  const [compras, setCompras] = useState([]);
  const [productos, setProductos] = useState([]);
  const [proveedores, setProveedores] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [abierta, setAbierta] = useState(false);
  const [proveedorId, setProveedorId] = useState("");
  const [nota, setNota] = useState("");
  const [lineas, setLineas] = useState([{ ...LINEA_VACIA }]);
  const [guardando, setGuardando] = useState(false);
  const [aAnular, setAAnular] = useState(null);
  const [detalle, setDetalle] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const params = new URLSearchParams();
      if (desde) params.set("desde", desde);
      if (hasta) params.set("hasta", hasta);
      const consulta = params.toString();

      const [lista, prods, provs] = await Promise.all([
        api.get(`/compras/${consulta ? `?${consulta}` : ""}`),
        api.get("/productos/").catch(() => []),
        api.get("/proveedores/").catch(() => []),
      ]);
      setCompras(lista?.items ?? []);
      setProductos(Array.isArray(prods) ? prods : []);
      setProveedores(Array.isArray(provs) ? provs : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [desde, hasta, toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const porId = useMemo(
    () => Object.fromEntries(productos.map((p) => [String(p.id), p])),
    [productos]
  );

  const totalBorrador = useMemo(
    () =>
      lineas.reduce((suma, l) => {
        const cantidad = Number(l.cantidad) || 0;
        const costo = Number(l.costo_unitario) || 0;
        return suma + cantidad * costo;
      }, 0),
    [lineas]
  );

  const totalPeriodo = useMemo(
    () =>
      compras
        .filter((c) => c.estado === "completada")
        .reduce((suma, c) => suma + Number(c.total), 0),
    [compras]
  );

  function abrirNueva() {
    setProveedorId("");
    setNota("");
    setLineas([{ ...LINEA_VACIA }]);
    setAbierta(true);
  }

  function actualizarLinea(indice, campo, valor) {
    setLineas((actuales) =>
      actuales.map((l, i) => (i === indice ? { ...l, [campo]: valor } : l))
    );
  }

  function agregarLinea() {
    setLineas((actuales) => [...actuales, { ...LINEA_VACIA }]);
  }

  function quitarLinea(indice) {
    setLineas((actuales) => actuales.filter((_, i) => i !== indice));
  }

  async function guardar(e) {
    e?.preventDefault();
    const items = lineas
      .filter((l) => l.producto_id && Number(l.cantidad) > 0)
      .map((l) => ({
        producto_id: Number(l.producto_id),
        cantidad: Number(l.cantidad),
        costo_unitario: Number(l.costo_unitario) || 0,
      }));
    if (items.length === 0) {
      toast("Agrega al menos un producto con cantidad", "error");
      return;
    }

    setGuardando(true);
    try {
      await api.post("/compras/", {
        proveedor_id: proveedorId ? Number(proveedorId) : null,
        items,
        nota: nota.trim() || null,
      });
      setAbierta(false);
      toast("Compra registrada: stock y costo actualizados");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function anular() {
    setGuardando(true);
    try {
      await api.post(`/compras/${aAnular.id}/anular`);
      toast("Compra anulada; el stock fue restaurado");
      setAAnular(null);
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
          <h1>Compras</h1>
          <p>{compras.length} registradas</p>
        </div>
        <Button icon={Plus} onClick={abrirNueva}>
          Registrar compra
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Receipt} label="Compras" value={compras.length} sub="En el periodo" />
        <StatCard icon={Receipt} label="Total comprado" value={fmtMoney(totalPeriodo)} tono="red" />
        <StatCard
          icon={Receipt}
          label="Anuladas"
          value={compras.filter((c) => c.estado === "anulada").length}
          tono="yellow"
          sub="Stock revertido"
        />
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label="Desde">
            <Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
          </Field>
          <Field label="Hasta">
            <Input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} />
          </Field>
        </div>
      </Card>

      {cargando ? (
        <TableSkeleton filas={5} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {compras.length === 0 ? (
            <EmptyState
              icon={Receipt}
              title="Sin compras registradas"
              text="Al registrar una compra, el stock sube y el costo promedio del producto se actualiza."
              action={<Button icon={Plus} onClick={abrirNueva}>Registrar compra</Button>}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Número</th>
                    <th className="th hidden sm:table-cell">Proveedor</th>
                    <th className="th hidden md:table-cell">Fecha</th>
                    <th className="th text-right">Total</th>
                    <th className="th">Estado</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {compras.map((c) => (
                    <tr key={c.id} className="table-row">
                      <td className="td">
                        <button
                          type="button"
                          onClick={() => setDetalle(c)}
                          className="font-medium text-brand-600 dark:text-brand-300 hover:underline"
                        >
                          {c.numero}
                        </button>
                        <p className="text-xs text-content-subtle">{c.items.length} líneas</p>
                      </td>
                      <td className="td hidden sm:table-cell text-content-muted">
                        {c.proveedor_nombre || "—"}
                      </td>
                      <td className="td hidden md:table-cell text-content-muted tabular">
                        {new Date(c.fecha).toLocaleDateString("es-NI")}
                      </td>
                      <td className="td text-right tabular font-medium">{fmtMoney(c.total)}</td>
                      <td className="td">
                        <span className={c.estado === "anulada" ? "badge-red" : "badge-green"}>
                          {c.estado === "anulada" ? "Anulada" : "Completada"}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton
                            label="Anular compra"
                            icon={Ban}
                            onClick={() => setAAnular(c)}
                            disabled={c.estado === "anulada"}
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
        title="Registrar compra"
        size="lg"
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAbierta(false)}>
              Cancelar
            </button>
            <Button onClick={guardar} loading={guardando}>
              Registrar compra por {fmtMoney(totalBorrador)}
            </Button>
          </>
        }
      >
        <form onSubmit={guardar} className="space-y-4">
          <Field label="Proveedor" hint="Opcional">
            <Select value={proveedorId} onChange={(e) => setProveedorId(e.target.value)}>
              <option value="">Sin proveedor</option>
              {proveedores.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre}
                </option>
              ))}
            </Select>
          </Field>

          <div className="space-y-2">
            <p className="label">Productos</p>
            {lineas.map((linea, indice) => {
              const producto = porId[String(linea.producto_id)];
              const cantidad = Number(linea.cantidad) || 0;
              const costo = Number(linea.costo_unitario) || 0;
              const costoNuevo =
                producto && cantidad > 0
                  ? ((Number(producto.costo) * Number(producto.stock) + costo * cantidad) /
                      (Number(producto.stock) + cantidad)).toFixed(2)
                  : null;

              return (
                <div
                  key={indice}
                  className="rounded-xl border border-border/70 bg-surface-elevated/40 p-3 space-y-2"
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <Select
                        value={linea.producto_id}
                        onChange={(e) => actualizarLinea(indice, "producto_id", e.target.value)}
                        aria-label={`Producto de la línea ${indice + 1}`}
                      >
                        <option value="">Selecciona un producto</option>
                        {productos.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.nombre} (stock {p.stock})
                          </option>
                        ))}
                      </Select>
                    </div>
                    <IconButton
                      label="Quitar línea"
                      icon={Trash2}
                      onClick={() => quitarLinea(indice)}
                      disabled={lineas.length === 1}
                      className="text-red-500 hover:bg-red-500/10 mt-1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      type="number"
                      min="1"
                      step="1"
                      value={linea.cantidad}
                      onChange={(e) => actualizarLinea(indice, "cantidad", e.target.value)}
                      placeholder="Cantidad"
                      aria-label={`Cantidad de la línea ${indice + 1}`}
                    />
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={linea.costo_unitario}
                      onChange={(e) => actualizarLinea(indice, "costo_unitario", e.target.value)}
                      placeholder="Costo unitario C$"
                      aria-label={`Costo unitario de la línea ${indice + 1}`}
                    />
                  </div>
                  {costoNuevo !== null && (
                    <p className="text-xs text-content-subtle">
                      Costo promedio resultante: <span className="tabular">{fmtMoney(costoNuevo)}</span>
                    </p>
                  )}
                </div>
              );
            })}

            <button type="button" className="btn-secondary btn-sm" onClick={agregarLinea}>
              <Plus size={14} aria-hidden="true" /> Agregar línea
            </button>
          </div>

          <Field label="Nota" hint="Opcional">
            <Textarea
              value={nota}
              onChange={(e) => setNota(e.target.value)}
              placeholder="Factura del proveedor, condiciones…"
            />
          </Field>

          <div className="flex items-center justify-between rounded-xl bg-surface-elevated px-4 py-3">
            <span className="text-sm text-content-muted">Total de la compra</span>
            <span className="text-lg font-semibold tabular">{fmtMoney(totalBorrador)}</span>
          </div>
        </form>
      </Modal>

      <Modal
        open={Boolean(detalle)}
        onClose={() => setDetalle(null)}
        title={detalle ? `Compra ${detalle.numero}` : "Detalle"}
        size="md"
      >
        {detalle && (
          <div className="space-y-3">
            <p className="text-sm text-content-muted">
              {detalle.proveedor_nombre || "Sin proveedor"} ·{" "}
              {new Date(detalle.fecha).toLocaleString("es-NI")}
            </p>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Producto</th>
                    <th className="th text-right">Cant.</th>
                    <th className="th text-right">Costo</th>
                    <th className="th text-right">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {detalle.items.map((item) => (
                    <tr key={item.producto_id} className="table-row">
                      <td className="td">{item.producto_nombre}</td>
                      <td className="td text-right tabular">{item.cantidad}</td>
                      <td className="td text-right tabular">{fmtMoney(item.costo_unitario)}</td>
                      <td className="td text-right tabular font-medium">{fmtMoney(item.subtotal)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {detalle.nota && <p className="text-sm text-content-muted">{detalle.nota}</p>}
          </div>
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(aAnular)}
        onClose={() => setAAnular(null)}
        onConfirm={anular}
        loading={guardando}
        title="Anular compra"
        confirmLabel="Anular"
        mensaje={`Se revertirá el stock de ${aAnular?.numero ?? ""} y se eliminará su gasto. El costo promedio no se recalcula.`}
      />
    </div>
  );
}
