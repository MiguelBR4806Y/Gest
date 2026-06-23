import { useState, useEffect, useCallback } from "react";
import { api, formatHora, fmtMoney } from "../lib/api";
import Modal from "../components/Modal";
import { Plus, Trash2, ShoppingCart, TrendingUp, Receipt, Search } from "lucide-react";

const METODOS = ["efectivo", "tarjeta", "transferencia", "credito"];

export default function VentasPage() {
  const [ventas, setVentas]       = useState([]);
  const [clientes, setClientes]   = useState([]);
  const [productos, setProductos] = useState([]);
  const [resumen, setResumen]     = useState({ total: 0, transacciones: 0, promedio: 0 });
  const [loading, setLoading]     = useState(true);
  const [fecha, setFecha]         = useState(new Date().toISOString().slice(0, 10));

  const [nuevaOpen, setNuevaOpen] = useState(false);
  const [detalleOpen, setDetalleOpen] = useState(false);
  const [ventaDetalle, setVentaDetalle] = useState(null);

  const [vForm, setVForm] = useState({ cliente_id: "", metodo_pago: "efectivo" });
  const [items, setItems] = useState([]);
  const [selProd, setSelProd] = useState("");
  const [selCant, setSelCant] = useState(1);
  const [saving, setSaving] = useState(false);

  const cargar = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get(`/ventas/resumen-dia?fecha=${fecha}`);
      const lista = data.ultimas_ventas ?? [];
      setVentas(lista);
      const total = lista.reduce((s, v) => s + (v.total ?? 0), 0);
      setResumen({ total, transacciones: lista.length, promedio: lista.length ? total / lista.length : 0 });
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [fecha]);

  useEffect(() => { cargar(); }, [cargar]);

  async function abrirNueva() {
    const [c, p] = await Promise.all([
      api.get("/clientes/").catch(() => []),
      api.get("/productos/").catch(() => []),
    ]);
    setClientes(c);
    setProductos(p);
    setVForm({ cliente_id: "", metodo_pago: "efectivo" });
    setItems([]);
    setNuevaOpen(true);
  }

  function agregarItem() {
    if (!selProd) return;
    const prod = productos.find(p => String(p.id) === String(selProd));
    if (!prod) return;
    setItems(it => {
      const existing = it.findIndex(i => i.producto_id === prod.id);
      if (existing >= 0) {
        return it.map((i, idx) => idx === existing ? { ...i, cantidad: i.cantidad + Number(selCant) } : i);
      }
      return [...it, { producto_id: prod.id, nombre: prod.nombre, precio: prod.precio, cantidad: Number(selCant) }];
    });
    setSelProd("");
    setSelCant(1);
  }

  function quitarItem(idx) { setItems(it => it.filter((_, i) => i !== idx)); }

  const totalVenta = items.reduce((s, i) => s + i.precio * i.cantidad, 0);

  async function registrarVenta() {
    if (items.length === 0) { alert("Agrega al menos un producto"); return; }
    setSaving(true);
    try {
      await api.post("/ventas/", {
        cliente_id: vForm.cliente_id ? Number(vForm.cliente_id) : null,
        metodo_pago: vForm.metodo_pago,
        items: items.map(i => ({ producto_id: i.producto_id, cantidad: i.cantidad, precio_unitario: i.precio })),
      });
      setNuevaOpen(false);
      cargar();
    } catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  async function abrirDetalle(v) {
    try {
      const d = await api.get(`/ventas/${v.id}`);
      setVentaDetalle(d);
    } catch { setVentaDetalle(v); }
    setDetalleOpen(true);
  }

  async function anularVenta(id) {
    if (!confirm("¿Anular esta venta?")) return;
    try { await api.delete(`/ventas/${id}`); cargar(); }
    catch(e) { alert(e.message); }
  }

  const metodoBadge = (m) => {
    const map = { efectivo: "badge-green", tarjeta: "badge-blue", transferencia: "badge-blue", credito: "badge-yellow" };
    return map[m] ?? "badge-blue";
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Ventas</h1>
          <p>Registro y control de transacciones</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={abrirNueva}>
          <Plus size={16} /> Nueva venta
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="metric-card border border-brand-500/20 bg-gradient-to-br from-brand-500/5 to-transparent">
          <div className="metric-icon bg-brand-500/10">
            <TrendingUp size={20} className="text-brand-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Total del día</p>
            <p className="text-xl font-bold text-brand-400">{fmtMoney(resumen.total)}</p>
          </div>
        </div>
        <div className="card-gradient p-5 flex items-start gap-4">
          <div className="metric-icon bg-secondary-500/10">
            <Receipt size={20} className="text-secondary-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Transacciones</p>
            <p className="text-xl font-bold text-content">{resumen.transacciones}</p>
          </div>
        </div>
        <div className="card-gradient p-5 flex items-start gap-4">
          <div className="metric-icon bg-accent-500/10">
            <ShoppingCart size={20} className="text-accent-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Promedio</p>
            <p className="text-xl font-bold text-accent-400">{fmtMoney(resumen.promedio)}</p>
          </div>
        </div>
      </div>

      {/* Date filter */}
      <div className="flex items-center gap-3">
        <label className="text-sm text-content-muted font-medium">Fecha:</label>
        <input type="date" className="input w-auto" value={fecha} onChange={e => setFecha(e.target.value)} />
      </div>

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : ventas.length === 0 ? (
          <div className="empty-state">
            <ShoppingCart size={40} />
            <p>No hay ventas para esta fecha.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">#</th>
                  <th className="th">Cliente</th>
                  <th className="th hidden md:table-cell">Productos</th>
                  <th className="th hidden sm:table-cell">Hora</th>
                  <th className="th text-right">Total</th>
                  <th className="th hidden sm:table-cell">Método</th>
                  <th className="th text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {ventas.map((v, i) => (
                  <tr key={v.id} className="table-row">
                    <td className="td text-content-subtle">{i + 1}</td>
                    <td className="td font-medium text-content">{v.cliente_nombre ?? v.cliente ?? "—"}</td>
                    <td className="td hidden md:table-cell text-content-muted text-xs">{v.productos ?? "—"}</td>
                    <td className="td hidden sm:table-cell text-content-muted">{formatHora(v.fecha_hora ?? v.hora ?? v.fecha)}</td>
                    <td className="td text-right font-semibold text-brand-400">{fmtMoney(v.total)}</td>
                    <td className="td hidden sm:table-cell">
                      <span className={metodoBadge(v.metodo_pago)}>{v.metodo_pago}</span>
                    </td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => abrirDetalle(v)} className="btn-ghost p-1.5 text-content-muted">
                          <Search size={14} />
                        </button>
                        <button onClick={() => anularVenta(v.id)} className="btn-ghost p-1.5 text-red-400 hover:text-red-300">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Nueva venta modal */}
      <Modal title="Nueva venta" open={nuevaOpen} onClose={() => setNuevaOpen(false)} size="lg">
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Cliente (opcional)</label>
              <select className="input" value={vForm.cliente_id} onChange={e => setVForm(f => ({ ...f, cliente_id: e.target.value }))}>
                <option value="">Sin cliente</option>
                {clientes.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Método de pago</label>
              <select className="input" value={vForm.metodo_pago} onChange={e => setVForm(f => ({ ...f, metodo_pago: e.target.value }))}>
                {METODOS.map(m => <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>)}
              </select>
            </div>
          </div>

          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <label className="label">Producto</label>
              <select className="input" value={selProd} onChange={e => setSelProd(e.target.value)}>
                <option value="">Seleccionar...</option>
                {productos.map(p => <option key={p.id} value={p.id}>{p.nombre} — {fmtMoney(p.precio)}</option>)}
              </select>
            </div>
            <div className="w-20">
              <label className="label">Cant.</label>
              <input className="input" type="number" min="1" value={selCant} onChange={e => setSelCant(e.target.value)} />
            </div>
            <button className="btn-secondary flex items-center gap-1 shrink-0" onClick={agregarItem}>
              <Plus size={14} /> Agregar
            </button>
          </div>

          {items.length > 0 && (
            <div className="bg-surface rounded-2xl overflow-hidden border border-border/40">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border/40">
                  <th className="th">Producto</th>
                  <th className="th text-center">Cant.</th>
                  <th className="th text-right">Precio</th>
                  <th className="th text-right">Subtotal</th>
                  <th className="th"></th>
                </tr></thead>
                <tbody>
                  {items.map((it, i) => (
                    <tr key={i} className="table-row">
                      <td className="td">{it.nombre}</td>
                      <td className="td text-center">{it.cantidad}</td>
                      <td className="td text-right text-content-muted">{fmtMoney(it.precio)}</td>
                      <td className="td text-right font-medium text-brand-400">{fmtMoney(it.precio * it.cantidad)}</td>
                      <td className="td">
                        <button onClick={() => quitarItem(i)} className="btn-ghost p-1 text-red-400 hover:text-red-300">
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr className="border-t border-border/50">
                    <td colSpan={3} className="td text-right font-bold text-content">Total:</td>
                    <td className="td text-right font-bold text-brand-400 text-base">{fmtMoney(totalVenta)}</td>
                    <td />
                  </tr>
                </tfoot>
              </table>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setNuevaOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={registrarVenta} disabled={saving || items.length === 0}>
              {saving ? "Guardando..." : "Registrar venta"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Detalle */}
      <Modal title="Detalle de venta" open={detalleOpen} onClose={() => setDetalleOpen(false)}>
        {ventaDetalle && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><span className="text-content-muted">Cliente:</span> <span className="text-content ml-1">{ventaDetalle.cliente ?? "—"}</span></div>
              <div><span className="text-content-muted">Método:</span> <span className={`ml-1 ${metodoBadge(ventaDetalle.metodo_pago)}`}>{ventaDetalle.metodo_pago}</span></div>
              <div><span className="text-content-muted">Hora:</span> <span className="text-content ml-1">{formatHora(ventaDetalle.hora ?? ventaDetalle.fecha)}</span></div>
              <div><span className="text-content-muted">Total:</span> <span className="text-brand-400 font-bold ml-1">{fmtMoney(ventaDetalle.total)}</span></div>
            </div>
            {ventaDetalle.items && (
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border/50">
                  <th className="th">Producto</th>
                  <th className="th text-center">Cant.</th>
                  <th className="th text-right">Subtotal</th>
                </tr></thead>
                <tbody>
                  {ventaDetalle.items.map((it, i) => (
                    <tr key={i} className="table-row">
                      <td className="td">{it.nombre ?? it.producto}</td>
                      <td className="td text-center">{it.cantidad}</td>
                      <td className="td text-right text-brand-400">{fmtMoney(it.subtotal ?? (it.precio * it.cantidad))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="flex justify-end">
              <button className="btn-secondary" onClick={() => setDetalleOpen(false)}>Cerrar</button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
