import { useCallback, useEffect, useMemo, useState } from "react";
import {
  History, Package, PackagePlus, Pencil, Plus, Search, Tag, Trash2,
} from "lucide-react";

import Modal, { ConfirmDialog } from "../components/Modal";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Select } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useDebounce } from "../hooks/useDebounce";
import { api, formatHora, fmtMoney, fmtMoneyUSD } from "../lib/api";

const VACIO = {
  nombre: "",
  categoria: "",
  stock: 0,
  stock_minimo: 5,
  precio: 0,
  promocion_id: "",
};

const etiquetaPromo = (promo) => {
  if (!promo) return null;
  if (promo.tipo === "porcentaje") return `${promo.valor}%`;
  if (promo.tipo === "monto_fijo") return `C$${promo.valor}`;
  return "2x1";
};

export default function InventarioPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const tasa = Number(user?.tasa_cambio) || 36;

  const [productos, setProductos] = useState([]);
  const [promociones, setPromociones] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);

  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [recarga, setRecarga] = useState(null);
  const [historialDe, setHistorialDe] = useState(null);
  const [historial, setHistorial] = useState([]);
  const [cargandoHistorial, setCargandoHistorial] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const [p, promos] = await Promise.all([
        api.get("/productos/"),
        api.get("/promociones/").catch(() => []),
      ]);
      setProductos(Array.isArray(p) ? p : []);
      setPromociones(Array.isArray(promos) ? promos.filter((x) => x.activa) : []);
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

  function abrirEditar(p) {
    setEditando(p.id);
    setForm({
      nombre: p.nombre,
      categoria: p.categoria ?? "",
      stock: p.stock,
      stock_minimo: p.stock_minimo,
      precio: p.precio,
      promocion_id: p.promocion_id ?? "",
    });
    setAbierta(true);
  }

  async function guardar() {
    if (!form.nombre.trim()) return;
    setGuardando(true);
    try {
      const cuerpo = {
        nombre: form.nombre.trim(),
        categoria: form.categoria.trim() || null,
        stock: Number(form.stock) || 0,
        stock_minimo: Number(form.stock_minimo) || 0,
        precio: Number(form.precio) || 0,
        promocion_id: form.promocion_id ? Number(form.promocion_id) : null,
      };
      if (editando) await api.put(`/productos/${editando}`, cuerpo);
      else await api.post("/productos/", cuerpo);
      setAbierta(false);
      toast(editando ? "Producto actualizado" : "Producto creado");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarRecarga() {
    if (!recarga) return;
    setGuardando(true);
    try {
      await api.post(`/productos/${recarga.id}/recargar`, {
        cantidad: Number(recarga.cantidad) || 0,
      });
      setRecarga(null);
      toast("Inventario recargado");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function abrirHistorial(p) {
    setHistorialDe(p);
    setHistorial([]);
    setCargandoHistorial(true);
    try {
      const datos = await api.get(`/productos/${p.id}/movimientos`);
      setHistorial(Array.isArray(datos) ? datos : []);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargandoHistorial(false);
    }
  }

  async function eliminar() {
    if (!aEliminar) return;
    setGuardando(true);
    try {
      await api.delete(`/productos/${aEliminar.id}`);
      toast("Producto eliminado");
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
    if (!q) return productos;
    return productos.filter(
      (p) =>
        p.nombre.toLowerCase().includes(q) ||
        (p.categoria ?? "").toLowerCase().includes(q)
    );
  }, [productos, busquedaDiferida]);

  const conStockBajo = productos.filter((p) => p.stock <= p.stock_minimo);
  const valorInventario = productos.reduce((s, p) => s + p.precio * p.stock, 0);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Inventario</h1>
          <p>Control de productos y existencias</p>
        </div>
        <Button icon={Plus} onClick={abrirNuevo}>
          Agregar producto
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Package} label="Productos" value={productos.length} sub="Registrados" />
        <StatCard
          icon={Tag}
          label="Valor del inventario"
          value={fmtMoney(valorInventario)}
          sub="A precio de venta"
          tono="green"
        />
        <StatCard
          icon={PackagePlus}
          label="Stock bajo"
          value={conStockBajo.length}
          sub={conStockBajo.length ? "Requieren reposición" : "Todo en orden"}
          tono={conStockBajo.length ? "red" : "brand"}
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
          placeholder="Buscar por nombre o categoría…"
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
          aria-label="Buscar productos"
        />
      </div>

      {cargando ? (
        <TableSkeleton filas={6} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {filtrados.length === 0 ? (
            <EmptyState
              icon={Package}
              title={productos.length === 0 ? "Sin productos" : "Sin resultados"}
              text={
                productos.length === 0
                  ? "Agrega tu primer producto para empezar a registrar ventas."
                  : "Prueba con otro término de búsqueda."
              }
              action={
                productos.length === 0 && (
                  <Button size="sm" icon={Plus} onClick={abrirNuevo}>
                    Agregar producto
                  </Button>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Producto</th>
                    <th className="th hidden sm:table-cell">Categoría</th>
                    <th className="th text-center">Stock</th>
                    <th className="th text-right">Precio</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((p) => {
                    const bajo = p.stock <= p.stock_minimo;
                    return (
                      <tr key={p.id} className="table-row">
                        <td className="td font-medium">
                          <span className="flex items-center gap-2 min-w-0">
                            <span className="truncate">{p.nombre}</span>
                            {p.promocion && (
                              <span className="badge-yellow shrink-0">
                                <Tag size={9} aria-hidden="true" />
                                {etiquetaPromo(p.promocion)}
                              </span>
                            )}
                          </span>
                        </td>
                        <td className="td hidden sm:table-cell text-content-muted max-w-[10rem] truncate">
                          {p.categoria || "—"}
                        </td>
                        <td className="td text-center">
                          <span className={bajo ? "badge-red" : "badge-green"}>
                            {p.stock}
                            <span className="sr-only"> unidades</span>
                          </span>
                        </td>
                        <td className="td text-right tabular">
                          <span className="block font-medium">{fmtMoney(p.precio)}</span>
                          <span className="block text-xs text-content-subtle">
                            {fmtMoneyUSD(p.precio / tasa)}
                          </span>
                        </td>
                        <td className="td">
                          <div className="flex items-center justify-end gap-0.5">
                            <IconButton label="Editar" icon={Pencil} onClick={() => abrirEditar(p)} />
                            <IconButton
                              label="Recargar stock"
                              icon={PackagePlus}
                              onClick={() => setRecarga({ id: p.id, nombre: p.nombre, cantidad: 1 })}
                            />
                            <IconButton
                              label="Ver movimientos"
                              icon={History}
                              onClick={() => abrirHistorial(p)}
                            />
                            <IconButton
                              label="Eliminar"
                              icon={Trash2}
                              onClick={() => setAEliminar(p)}
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

      {/* Crear / editar */}
      <Modal
        open={abierta}
        onClose={() => setAbierta(false)}
        title={editando ? "Editar producto" : "Agregar producto"}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAbierta(false)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={guardar} loading={guardando} disabled={!form.nombre.trim()}>
              {editando ? "Guardar cambios" : "Agregar producto"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Field label="Nombre" required>
            <Input
              value={form.nombre}
              onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              placeholder="Nombre del producto"
              maxLength={120}
            />
          </Field>

          <Field label="Categoría">
            <Input
              value={form.categoria}
              onChange={(e) => setForm((f) => ({ ...f, categoria: e.target.value }))}
              placeholder="Ej: Bebidas, Lácteos…"
              maxLength={80}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={editando ? "Stock actual" : "Stock inicial"}>
              <Input
                type="number"
                min="0"
                inputMode="numeric"
                value={form.stock}
                onChange={(e) => setForm((f) => ({ ...f, stock: e.target.value }))}
              />
            </Field>
            <Field label="Stock mínimo" hint="Debajo de esto se marca como crítico.">
              <Input
                type="number"
                min="0"
                inputMode="numeric"
                value={form.stock_minimo}
                onChange={(e) => setForm((f) => ({ ...f, stock_minimo: e.target.value }))}
              />
            </Field>
          </div>

          <Field
            label="Precio (C$)"
            hint={
              Number(form.precio) > 0
                ? `≈ ${fmtMoneyUSD(Number(form.precio) / tasa)} con tasa ${tasa}`
                : "Es el precio con el que se factura la venta."
            }
          >
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={form.precio}
              onChange={(e) => setForm((f) => ({ ...f, precio: e.target.value }))}
            />
          </Field>

          <Field
            label="Promoción"
            hint={promociones.length === 0 ? "Aún no tienes promociones activas." : undefined}
          >
            <Select
              value={form.promocion_id}
              onChange={(e) => setForm((f) => ({ ...f, promocion_id: e.target.value }))}
            >
              <option value="">Sin promoción</option>
              {promociones.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.nombre} ({etiquetaPromo(p)})
                </option>
              ))}
            </Select>
          </Field>
        </div>
      </Modal>

      {/* Recargar */}
      <Modal
        open={Boolean(recarga)}
        onClose={() => setRecarga(null)}
        title="Recargar inventario"
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setRecarga(null)} disabled={guardando}>
              Cancelar
            </Button>
            <Button onClick={confirmarRecarga} loading={guardando}>
              Confirmar recarga
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm text-content">
            Producto: <span className="font-medium">{recarga?.nombre}</span>
          </p>
          <Field label="Unidades a añadir" required>
            <Input
              type="number"
              min="1"
              inputMode="numeric"
              value={recarga?.cantidad ?? 1}
              onChange={(e) => setRecarga((r) => ({ ...r, cantidad: e.target.value }))}
            />
          </Field>
        </div>
      </Modal>

      {/* Historial */}
      <Modal
        open={Boolean(historialDe)}
        onClose={() => setHistorialDe(null)}
        title={`Movimientos — ${historialDe?.nombre ?? ""}`}
        footer={
          <Button variant="secondary" onClick={() => setHistorialDe(null)}>
            Cerrar
          </Button>
        }
      >
        {cargandoHistorial ? (
          <TableSkeleton filas={4} columnas={3} />
        ) : historial.length === 0 ? (
          <EmptyState
            icon={History}
            title="Sin movimientos"
            text="Aquí verás las entradas y salidas de este producto."
          />
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Tipo</th>
                <th className="th text-center">Cantidad</th>
                <th className="th text-right">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {historial.map((h, i) => (
                <tr key={i} className="table-row">
                  <td className="td">
                    <span className={h.tipo === "entrada" ? "badge-green" : "badge-red"}>
                      {h.tipo === "entrada" ? "Entrada" : "Salida"}
                    </span>
                  </td>
                  <td className="td text-center tabular">{h.cantidad}</td>
                  <td className="td text-right text-content-muted text-xs">
                    {formatHora(h.fecha_hora)}
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
        title="Eliminar producto"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.nombre ?? ""}" junto con su historial de movimientos. Las facturas ya emitidas no se modifican.`}
      />
    </div>
  );
}
