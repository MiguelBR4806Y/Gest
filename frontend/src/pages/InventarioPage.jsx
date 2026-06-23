import { useState, useEffect } from "react";
import { api, fmtMoney } from "../lib/api";
import Modal from "../components/Modal";
import { Plus, Pencil, PackagePlus, History, Trash2, Search, Package } from "lucide-react";

const EMPTY_FORM = { nombre: "", categoria: "", stock: 0, stock_minimo: 5, precio: 0 };

export default function InventarioPage() {
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

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setLoading(true);
    try {
      const data = await api.get("/productos/");
      setProductos(data);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }

  function setF(key, val) { setForm(f => ({ ...f, [key]: val })); }
  function setEF(key, val) { setEditForm(f => ({ ...f, [key]: val })); }

  async function agregar() {
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      await api.post("/productos/", { ...form, stock: Number(form.stock), stock_minimo: Number(form.stock_minimo), precio: Number(form.precio) });
      setAddOpen(false);
      setForm(EMPTY_FORM);
      cargar();
    } catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  function abrirEditar(p) {
    setEditForm({ id: p.id, nombre: p.nombre, categoria: p.categoria ?? "", stock: p.stock, stock_minimo: p.stock_minimo, precio: p.precio });
    setEditOpen(true);
  }

  async function guardarEdicion() {
    setSaving(true);
    try {
      await api.put(`/productos/${editForm.id}`, { nombre: editForm.nombre, categoria: editForm.categoria, stock: Number(editForm.stock), stock_minimo: Number(editForm.stock_minimo), precio: Number(editForm.precio) });
      setEditOpen(false);
      cargar();
    } catch(e) { alert(e.message); }
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
    } catch(e) { alert(e.message); }
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
    } catch(e) { alert(e.message); }
  }

  const filtrados = productos.filter(p =>
    p.nombre.toLowerCase().includes(search.toLowerCase()) ||
    (p.categoria ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const stockBajo = productos.filter(p => p.stock <= p.stock_minimo).length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Inventario</h1>
          <p className="text-sm text-gray-500 mt-0.5">{productos.length} productos registrados · {stockBajo > 0 && <span className="text-red-400">{stockBajo} con stock bajo</span>}</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setForm(EMPTY_FORM); setAddOpen(true); }}>
          <Plus size={16} /> Agregar producto
        </button>
      </div>

      <div className="relative">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input className="input pl-9" placeholder="Buscar por nombre o categoría..."
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-7 h-7 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtrados.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Package size={36} className="text-gray-700" />
            <p className="text-gray-500">No hay productos registrados.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="border-b border-gray-800">
                <tr>
                  <th className="th">#</th>
                  <th className="th">Nombre</th>
                  <th className="th hidden sm:table-cell">Categoría</th>
                  <th className="th text-center">Stock</th>
                  <th className="th text-center hidden md:table-cell">Mínimo</th>
                  <th className="th text-right hidden sm:table-cell">Precio</th>
                  <th className="th text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map((p, i) => {
                  const bajo = p.stock <= p.stock_minimo;
                  return (
                    <tr key={p.id} className="table-row">
                      <td className="td text-gray-600">{i + 1}</td>
                      <td className="td font-medium text-gray-200">{p.nombre}</td>
                      <td className="td hidden sm:table-cell text-gray-500">{p.categoria || "—"}</td>
                      <td className="td text-center">
                        <span className={bajo ? "badge-red" : "badge-green"}>{p.stock}</span>
                      </td>
                      <td className="td text-center hidden md:table-cell text-gray-500">{p.stock_minimo}</td>
                      <td className="td text-right hidden sm:table-cell text-gray-300">{fmtMoney(p.precio)}</td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => abrirEditar(p)} className="btn-ghost p-1.5" title="Editar">
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => abrirRecargar(p)} className="btn-ghost p-1.5 text-blue-400 hover:text-blue-300" title="Recargar">
                            <PackagePlus size={14} />
                          </button>
                          <button onClick={() => abrirHistorial(p)} className="btn-ghost p-1.5 text-gray-400" title="Historial">
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
          <p className="text-sm text-gray-500 py-4">Sin movimientos registrados.</p>
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
                  <td className="td text-right text-gray-500 text-xs">{h.fecha_hora ?? h.fecha}</td>
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
