import { useState, useEffect } from "react";
import { api, fmtMoney, formatHora } from "../lib/api";
import Modal from "../components/Modal";
import { Plus, Pencil, Users, CreditCard, History, Trash2, Search } from "lucide-react";

const EMPTY = { nombre: "", telefono: "", credito_limite: 0 };

export default function ClientesPage() {
  const [clientes, setClientes]     = useState([]);
  const [loading, setLoading]       = useState(true);
  const [search, setSearch]         = useState("");

  const [addOpen, setAddOpen]       = useState(false);
  const [editOpen, setEditOpen]     = useState(false);
  const [comprasOpen, setComprasOpen] = useState(false);

  const [form, setForm]             = useState(EMPTY);
  const [editForm, setEditForm]     = useState({ ...EMPTY, id: null, codigo: "", credito_usado: 0 });
  const [compras, setCompras]       = useState([]);
  const [saving, setSaving]         = useState(false);

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setLoading(true);
    try { setClientes(await api.get("/clientes/")); }
    catch(e) { console.error(e); }
    finally { setLoading(false); }
  }

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })); }
  function setEF(k, v) { setEditForm(f => ({ ...f, [k]: v })); }

  async function agregar() {
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      await api.post("/clientes/", { ...form, credito_limite: Number(form.credito_limite) });
      setAddOpen(false);
      setForm(EMPTY);
      cargar();
    } catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  function abrirEditar(c) {
    setEditForm({ id: c.id, codigo: c.codigo, nombre: c.nombre, telefono: c.telefono ?? "", credito_limite: c.credito_limite ?? 0, credito_usado: c.credito_usado ?? 0 });
    setEditOpen(true);
  }

  async function guardarEdicion() {
    setSaving(true);
    try {
      await api.put(`/clientes/${editForm.id}`, {
        nombre: editForm.nombre, telefono: editForm.telefono,
        credito_limite: Number(editForm.credito_limite),
        credito_usado: Number(editForm.credito_usado),
      });
      setEditOpen(false);
      cargar();
    } catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  async function abrirCompras(c) {
    setComprasOpen(true);
    setCompras([]);
    try { setCompras(await api.get(`/clientes/${c.id}/compras`)); }
    catch(e) { console.error(e); }
  }

  async function eliminar(id) {
    if (!confirm("¿Eliminar este cliente?")) return;
    try { await api.delete(`/clientes/${id}`); cargar(); }
    catch(e) { alert(e.message); }
  }

  const filtrados = clientes.filter(c =>
    c.nombre.toLowerCase().includes(search.toLowerCase()) ||
    (c.telefono ?? "").includes(search) ||
    (c.codigo ?? "").toLowerCase().includes(search.toLowerCase())
  );

  const totalClientes    = clientes.length;
  const conCredito       = clientes.filter(c => (c.credito_usado ?? 0) > 0).length;
  const totalDeuda       = clientes.reduce((s, c) => s + (c.credito_usado ?? 0), 0);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Clientes</h1>
          <p>{totalClientes} clientes registrados</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setForm(EMPTY); setAddOpen(true); }}>
          <Plus size={16} /> Agregar cliente
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="metric-card border border-brand-500/20 bg-gradient-to-br from-brand-500/5 to-transparent">
          <div className="metric-icon bg-brand-500/10">
            <Users size={20} className="text-brand-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Total clientes</p>
            <p className="text-xl font-bold text-content">{totalClientes}</p>
          </div>
        </div>
        <div className="card-gradient p-5 flex items-start gap-4 border border-accent-500/20 bg-gradient-to-br from-accent-500/5 to-transparent">
          <div className="metric-icon bg-accent-500/10">
            <CreditCard size={20} className="text-accent-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Con crédito activo</p>
            <p className="text-xl font-bold text-content">{conCredito}</p>
          </div>
        </div>
        <div className="card-gradient p-5 flex items-start gap-4 border border-red-500/20 bg-gradient-to-br from-red-500/5 to-transparent">
          <div className="metric-icon bg-red-500/10">
            <CreditCard size={20} className="text-red-400" />
          </div>
          <div>
            <p className="text-xs text-content-muted">Total en créditos</p>
            <p className="text-xl font-bold text-red-400">{fmtMoney(totalDeuda)}</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-content-muted" />
        <input className="input pl-10" placeholder="Buscar por nombre o teléfono..."
          value={search} onChange={e => setSearch(e.target.value)} />
      </div>

      {/* Table */}
      <div className="table-container">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtrados.length === 0 ? (
          <div className="empty-state">
            <Users size={40} />
            <p>No hay clientes registrados.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">#</th>
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
                {filtrados.map((c, i) => {
                  const pct = c.credito_limite > 0 ? (c.credito_usado / c.credito_limite) * 100 : 0;
                  const badgeClass = pct >= 90 ? "badge-red" : pct >= 60 ? "badge-yellow" : "badge-green";
                  return (
                    <tr key={c.id} className="table-row">
                      <td className="td text-content-subtle">{i + 1}</td>
                      <td className="td font-mono text-xs text-brand-400 font-semibold">{c.codigo}</td>
                      <td className="td font-medium text-content">{c.nombre}</td>
                      <td className="td hidden sm:table-cell text-content-muted">{c.telefono || "—"}</td>
                      <td className="td text-right">
                        {(c.credito_usado ?? 0) > 0
                          ? <span className={badgeClass}>{fmtMoney(c.credito_usado)}</span>
                          : <span className="text-content-subtle text-xs">—</span>
                        }
                      </td>
                      <td className="td text-right hidden md:table-cell text-content-muted">{fmtMoney(c.credito_limite)}</td>
                      <td className="td hidden lg:table-cell text-content-muted text-xs">{c.ultima_compra ?? "—"}</td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <button onClick={() => abrirEditar(c)} className="btn-ghost p-1.5" title="Editar">
                            <Pencil size={14} />
                          </button>
                          <button onClick={() => abrirCompras(c)} className="btn-ghost p-1.5 text-secondary-400 hover:text-secondary-300" title="Historial de compras">
                            <History size={14} />
                          </button>
                          <button onClick={() => eliminar(c.id)} className="btn-ghost p-1.5 text-red-400 hover:text-red-300" title="Eliminar">
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
      <Modal title="Agregar cliente" open={addOpen} onClose={() => setAddOpen(false)} size="sm">
        <div className="space-y-4">
          <div>
            <label className="label">Nombre *</label>
            <input className="input" placeholder="Nombre del cliente" value={form.nombre} onChange={e => setF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Teléfono</label>
            <input className="input" placeholder="Ej: 8888-8888" value={form.telefono} onChange={e => setF("telefono", e.target.value)} />
          </div>
          <div>
            <label className="label">Límite de crédito (C$)</label>
            <input className="input" type="number" min="0" step="0.01" value={form.credito_limite} onChange={e => setF("credito_limite", e.target.value)} />
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setAddOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={agregar} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
          </div>
        </div>
      </Modal>

      {/* Editar */}
      <Modal title="Editar cliente" open={editOpen} onClose={() => setEditOpen(false)} size="sm">
        <div className="space-y-4">
          <div>
            <label className="label">Código</label>
            <div className="input font-mono text-brand-400 bg-surface-alt/50 select-all">{editForm.codigo}</div>
          </div>
          <div>
            <label className="label">Nombre *</label>
            <input className="input" value={editForm.nombre} onChange={e => setEF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Teléfono</label>
            <input className="input" value={editForm.telefono} onChange={e => setEF("telefono", e.target.value)} />
          </div>
          <div>
            <label className="label">Límite de crédito (C$)</label>
            <input className="input" type="number" min="0" step="0.01" value={editForm.credito_limite} onChange={e => setEF("credito_limite", e.target.value)} />
          </div>
          <div>
            <label className="label">Crédito usado actual</label>
            <input className="input" type="number" min="0" step="0.01" value={editForm.credito_usado} onChange={e => setEF("credito_usado", e.target.value)} />
            <p className="text-xs text-content-subtle mt-1.5">Edita para ajustar el crédito usado.</p>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setEditOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarEdicion} disabled={saving}>{saving ? "Guardando..." : "Guardar cambios"}</button>
          </div>
        </div>
      </Modal>

      {/* Historial compras */}
      <Modal title="Historial de compras" open={comprasOpen} onClose={() => setComprasOpen(false)}>
        {compras.length === 0 ? (
          <p className="text-sm text-content-muted py-4">Sin compras registradas.</p>
        ) : (
          <table className="w-full">
            <thead><tr>
              <th className="th text-right">Total</th>
              <th className="th">Método</th>
              <th className="th text-right">Fecha</th>
            </tr></thead>
            <tbody>
              {compras.map((c, i) => (
                <tr key={i} className="table-row">
                  <td className="td text-right font-medium text-brand-400">{fmtMoney(c.total)}</td>
                  <td className="td"><span className="badge-blue">{c.metodo_pago}</span></td>
                  <td className="td text-right text-content-muted text-xs">{formatHora(c.fecha_hora ?? c.fecha)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="flex justify-end mt-4">
          <button className="btn-secondary" onClick={() => setComprasOpen(false)}>Cerrar</button>
        </div>
      </Modal>
    </div>
  );
}
