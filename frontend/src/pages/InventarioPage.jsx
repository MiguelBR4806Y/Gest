import { useState, useEffect } from "react";
import { api, fmtMoney, fmtMoneyUSD, formatHora } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import Modal from "../components/Modal";
import { Plus, Pencil, PackagePlus, History, Trash2, Search, Package, Tag } from "lucide-react";
import { useToast } from "../context/ToastContext";

const EMPTY_FORM = { nombre: "", categoria: "", stock: 0, stock_minimo: 5, precio: 0, precio_dolar: 0, promocion_id: null };

export default function InventarioPage() {
  const { user } = useAuth();
  const { toast } = useToast();
  const tasa = user?.tasa_cambio ?? 36;
  const [productos, setProductos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  const [addOpen, setAddOpen]         = useState(false);
  const [editOpen, setEditOpen]       = useState(false);
  const [recargarOpen, setRecargarOpen] = useState(false);
  const [historialOpen, setHistorialOpen] = useState(false);

  const [form, setForm]               = useState(EMPTY_FORM);
  const [editForm, setEditForm]       = useState({ ...EMPTY_FORM, id: null });
  const [recargarData, setRecargarData] = useState({ id: null, nombre: "", cantidad: 1 });
  const [historial, setHistorial]     = useState([]);
  const [saving, setSaving]           = useState(false);
  const [promociones, setPromociones] = useState([]);

  useEffect(() => { cargar(); cargarPromos(); }, []);

  async function cargar() {
    setLoading(true);
    try {
      const data = await api.get("/productos/");
      setProductos(data);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }

  async function cargarPromos() {
    try {
      const data = await api.get("/promociones/");
      setPromociones(data.filter(p => p.activa));
    } catch {}
  }

  function setF(key, val) { setForm(f => ({ ...f, [key]: val })); }
  function setEF(key, val) { setEditForm(f => ({ ...f, [key]: val })); }

  async function agregar() {
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      await api.post("/productos/", {
        ...form,
        stock: Number(form.stock),
        stock_minimo: Number(form.stock_minimo),
        precio: Number(form.precio),
        precio_dolar: Number(form.precio_dolar),
        promocion_id: form.promocion_id ? Number(form.promocion_id) : null,
      });
      setAddOpen(false);
      setForm(EMPTY_FORM);
      cargar();
    } catch(e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  function abrirEditar(p) {
    setEditForm({
      id: p.id, nombre: p.nombre, categoria: p.categoria ?? "",
      stock: p.stock, stock_minimo: p.stock_minimo,
      precio: p.precio, precio_dolar: p.precio_dolar,
      promocion_id: p.promocion_id,
    });
    setEditOpen(true);
  }

  async function guardarEdicion() {
    setSaving(true);
    try {
      await api.put(`/productos/${editForm.id}`, {
        nombre: editForm.nombre, categoria: editForm.categoria,
        stock: Number(editForm.stock), stock_minimo: Number(editForm.stock_minimo),
        precio: Number(editForm.precio), precio_dolar: Number(editForm.precio_dolar),
        promocion_id: editForm.promocion_id ? Number(editForm.promocion_id) : null,
      });
      setEditOpen(false);
      cargar();
    } catch(e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  function abrirRecargar(p) {
    setRecargarData({ id: p.id, nombre: p.nombre, cantidad: 1 });
    setRecargarOpen(true);
  }

  async function confirmarRecarga() {
    setSaving(true);
    try {
      await api.post(`/productos/${recargarData.id}/recargar`, { cantidad: Number(recargarData.cantidad) });
      setRecargarOpen(false);
      cargar();
    } catch(e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  async function abrirHistorial(p) {
    setHistorialOpen(true);
    setHistorial([]);
    try {
      const data = await api.get(`/productos/${p.id}/movimientos`);
      setHistorial(data);
    } catch(e) { console.error(e); }
  }

  async function eliminar(id) {
    if (!confirm("¿Eliminar este producto?")) return;
    try {
      await api.delete(`/productos/${id}`);
      cargar();
    } catch(e) { toast(e.message, "error"); }
  }

  const filtrados = productos.filter(p =>
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    (p.categoria ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const stockBajo = productos.filter(p => p.stock <= p.stock_minimo).length;

  function labelPromo(promo) {
    if (!promo) return null;
    const map = { porcentaje: `${promo.valor}%`, "2x1": "2x1", monto_fijo: `C$${promo.valor}` };
    return map[promo.tipo] ?? "";
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Inventario</h1>
          <p>{productos.length} productos registrados · {stockBajo > 0 && <span className="text-red-400">{stockBajo} con stock bajo</span>}</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setForm(EMPTY_FORM); setAddOpen(true); }}>
          <Plus size={16} /> Agregar producto
        </button>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-content-muted" />
        <input className="input pl-10" placeholder="Buscar por nombre o categoría..."
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      <div className="table-container">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtrados.length === 0 ? (
          <div className="empty-state">
            <Package size={40} />
            <p>No hay productos registrados.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">#</th>
                  <th className="th">Nombre</th>
                  <th className="th hidden sm:table-cell">Categoría</th>
                  <th className="th text-center">Stock</th>
                  <th className="th text-right hidden sm:table-cell">Precio</th>
                  <th className="th text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map((p, i) => {
                  const bajo = p.stock <= p.stock_minimo;
                  return (
                    <tr key={p.id} className="table-row">
                      <td className="td text-content-subtle">{i + 1}</td>
                      <td className="td font-medium text-content">
                        <div className="flex items-center gap-2">
                          {p.nombre}
                          {p.promocion && (
                            <span className="badge-yellow text-[10px] px-1.5 py-0.5 flex items-center gap-0.5">
                              <Tag size={9} />{labelPromo(p.promocion)}
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="td hidden sm:table-cell text-content-muted">{p.categoria || "—"}</td>
                      <td className="td text-center">
                        <span className={bajo ? "badge-red" : "badge-green"}>{p.stock}</span>
                      </td>
                      <td className="td text-right hidden sm:table-cell">
                        <div className="flex flex-col leading-tight">
                          <span className="text-xs font-medium">{fmtMoneyUSD(p.precio_dolar)}</span>
                          <span className="text-[10px] text-content-subtle">{fmtMoney(p.precio)}</span>
                        </div>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => abrirEditar(p)} className="btn-ghost p-1.5" title="Editar">
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => abrirRecargar(p)} className="btn-ghost p-1.5 text-secondary-400 hover:text-secondary-300" title="Recargar">
                            <PackagePlus size={14} />
                          </button>
                          <button onClick={() => abrirHistorial(p)} className="btn-ghost p-1.5 text-content-muted" title="Historial">
                            <History size={14} />
                          </button>
                          <button onClick={() => eliminar(p.id)} className="btn-ghost p-1.5 text-red-400 hover:text-red-300" title="Eliminar">
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Agregar */}
      <Modal title="Agregar producto" open={addOpen} onClose={() => setAddOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Nombre *</label>
            <input className="input" placeholder="Nombre del producto" value={form.nombre} onChange={e => setF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Categoría</label>
            <input className="input" placeholder="Ej: Bebidas, Lácteos..." value={form.categoria} onChange={e => setF("categoria", e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Stock inicial</label>
              <input className="input" type="number" min="0" value={form.stock} onChange={e => setF("stock", e.target.value)} />
            </div>
            <div>
              <label className="label">Stock mínimo *</label>
              <input className="input" type="number" min="1" value={form.stock_minimo} onChange={e => setF("stock_minimo", e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">Precio (C$)</label>
            <input className="input" type="number" min="0" step="0.01" value={form.precio} onChange={e => setF("precio", e.target.value)} />
            {form.precio > 0 && (
              <p className="text-xs text-content-subtle mt-1">
                ≈ {fmtMoneyUSD(Number(form.precio) / tasa)} <span className="text-[10px]">(tasa {tasa})</span>
              </p>
            )}
          </div>
          <div>
            <label className="label">Promoción</label>
            <select className="input" value={form.promocion_id ?? ""} onChange={e => setF("promocion_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">Sin promoción</option>
              {promociones.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setAddOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={agregar} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
          </div>
        </div>
      </Modal>

      {/* Editar */}
      <Modal title="Editar producto" open={editOpen} onClose={() => setEditOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Nombre *</label>
            <input className="input" value={editForm.nombre} onChange={e => setEF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Categoría</label>
            <input className="input" value={editForm.categoria} onChange={e => setEF("categoria", e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Stock</label>
              <input className="input" type="number" min="0" value={editForm.stock} onChange={e => setEF("stock", e.target.value)} />
            </div>
            <div>
              <label className="label">Stock mínimo *</label>
              <input className="input" type="number" min="1" value={editForm.stock_minimo} onChange={e => setEF("stock_minimo", e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">Precio (C$)</label>
            <input className="input" type="number" min="0" step="0.01" value={editForm.precio} onChange={e => setEF("precio", e.target.value)} />
            {editForm.precio > 0 && (
              <p className="text-xs text-content-subtle mt-1">
                ≈ {fmtMoneyUSD(Number(editForm.precio) / tasa)} <span className="text-[10px]">(tasa {tasa})</span>
              </p>
            )}
          </div>
          <div>
            <label className="label">Promoción</label>
            <select className="input" value={editForm.promocion_id ?? ""} onChange={e => setEF("promocion_id", e.target.value ? Number(e.target.value) : null)}>
              <option value="">Sin promoción</option>
              {promociones.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setEditOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarEdicion} disabled={saving}>{saving ? "Guardando..." : "Guardar cambios"}</button>
          </div>
        </div>
      </Modal>

      {/* Recargar */}
      <Modal title="Recargar inventario" open={recargarOpen} onClose={() => setRecargarOpen(false)} size="sm">
        <div className="space-y-4">
          <p className="text-sm text-brand-400 font-medium">{recargarData.nombre}</p>
          <div>
            <label className="label">Cantidad a añadir *</label>
            <input className="input" type="number" min="1" value={recargarData.cantidad}
              onChange={e => setRecargarData(d => ({ ...d, cantidad: e.target.value }))} />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setRecargarOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={confirmarRecarga} disabled={saving}>{saving ? "Guardando..." : "Confirmar recarga"}</button>
          </div>
        </div>
      </Modal>

      {/* Historial */}
      <Modal title="Historial de movimientos" open={historialOpen} onClose={() => setHistorialOpen(false)}>
        {historial.length === 0 ? (
          <p className="text-sm text-content-muted py-4">Sin movimientos registrados.</p>
        ) : (
          <table className="w-full">
            <thead><tr>
              <th className="th">Tipo</th>
              <th className="th text-center">Cantidad</th>
              <th className="th text-right">Fecha</th>
            </tr></thead>
            <tbody>
              {historial.map((h, i) => (
                <tr key={i} className="table-row">
                  <td className="td">
                    <span className={h.tipo === "entrada" ? "badge-green" : "badge-red"}>{h.tipo}</span>
                  </td>
                  <td className="td text-center">{h.cantidad}</td>
                  <td className="td text-right text-content-muted text-xs">{formatHora(h.fecha_hora ?? h.fecha)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex justify-end mt-4">
          <button className="btn-secondary" onClick={() => setHistorialOpen(false)}>Cerrar</button>
        </div>
      </Modal>
    </div>
  );
}
