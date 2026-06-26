import { useState, useEffect } from "react";
import { api } from "../lib/api";
import Modal from "../components/Modal";
import { Plus, Pencil, Trash2, Tag, Percent, DollarSign, Package } from "lucide-react";

const TIPOS = [
  { value: "porcentaje", label: "Descuento %", icon: Percent },
  { value: "2x1", label: "2x1", icon: Package },
  { value: "monto_fijo", label: "Descuento fijo (C$)", icon: DollarSign },
];

const EMPTY_FORM = { nombre: "", tipo: "porcentaje", valor: 0, activa: true };

export default function PromocionesPage() {
  const [promos, setPromos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editForm, setEditForm] = useState({ ...EMPTY_FORM, id: null });
  const [saving, setSaving] = useState(false);

  useEffect(() => { cargar(); }, []);

  async function cargar() {
    setLoading(true);
    try {
      const data = await api.get("/promociones/");
      setPromos(data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }

  function setF(key, val) { setForm(f => ({ ...f, [key]: val })); }
  function setEF(key, val) { setEditForm(f => ({ ...f, [key]: val })); }

  async function agregar() {
    if (!form.nombre.trim()) return;
    setSaving(true);
    try {
      await api.post("/promociones/", {
        ...form,
        valor: Number(form.valor),
      });
      setAddOpen(false);
      setForm(EMPTY_FORM);
      cargar();
    } catch (e) { alert(e.message); }
    finally { setSaving(false); }
  }

  function abrirEditar(p) {
    setEditForm({ id: p.id, nombre: p.nombre, tipo: p.tipo, valor: p.valor, activa: p.activa });
    setEditOpen(true);
  }

  async function guardarEdicion() {
    if (!editForm.nombre.trim()) return;
    setSaving(true);
    try {
      await api.put(`/promociones/${editForm.id}`, {
        nombre: editForm.nombre,
        tipo: editForm.tipo,
        valor: Number(editForm.valor),
        activa: editForm.activa,
      });
      setEditOpen(false);
      cargar();
    } catch (e) { alert(e.message); }
    finally { setSaving(false); }
  }

  async function eliminar(id) {
    if (!confirm("¿Eliminar esta promoción?")) return;
    try {
      await api.delete(`/promociones/${id}`);
      cargar();
    } catch (e) { alert(e.message); }
  }

  function descTipo(tipo) {
    const t = TIPOS.find(t => t.value === tipo);
    return t ? t.label : tipo;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="page-header">
        <div>
          <h1>Promociones</h1>
          <p>{promos.filter(p => p.activa).length} activas · {promos.length} total</p>
        </div>
        <button className="btn-primary flex items-center gap-2" onClick={() => { setForm(EMPTY_FORM); setAddOpen(true); }}>
          <Plus size={16} /> Nueva promoción
        </button>
      </div>

      <div className="table-container">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : promos.length === 0 ? (
          <div className="empty-state">
            <Tag size={40} />
            <p>No hay promociones registradas.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">#</th>
                  <th className="th">Nombre</th>
                  <th className="th">Tipo</th>
                  <th className="th text-right">Valor</th>
                  <th className="th text-center">Estado</th>
                  <th className="th text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {promos.map((p, i) => (
                  <tr key={p.id} className="table-row">
                    <td className="td text-content-subtle">{i + 1}</td>
                    <td className="td font-medium text-content">{p.nombre}</td>
                    <td className="td text-content-muted">
                      <div className="flex items-center gap-1.5">
                        {(() => {
                          const Icon = TIPOS.find(t => t.value === p.tipo)?.icon ?? Tag;
                          return <Icon size={14} />;
                        })()}
                        {descTipo(p.tipo)}
                      </div>
                    </td>
                    <td className="td text-right font-medium">
                      {p.tipo === "porcentaje" && `${p.valor}%`}
                      {p.tipo === "2x1" && "—"}
                      {p.tipo === "monto_fijo" && `C$${p.valor}`}
                    </td>
                    <td className="td text-center">
                      <span className={p.activa ? "badge-green" : "badge-red"}>
                        {p.activa ? "Activa" : "Inactiva"}
                      </span>
                    </td>
                    <td className="td">
                      <div className="flex items-center justify-end gap-1">
                        <button onClick={() => abrirEditar(p)} className="btn-ghost p-1.5" title="Editar">
                          <Pencil size={14} />
                        </button>
                        <button onClick={() => eliminar(p.id)} className="btn-ghost p-1.5 text-red-400 hover:text-red-300" title="Eliminar">
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

      {/* Agregar */}
      <Modal title="Nueva promoción" open={addOpen} onClose={() => setAddOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Nombre *</label>
            <input className="input" placeholder="Ej: Descuento de temporada" value={form.nombre} onChange={e => setF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Tipo</label>
            <select className="input" value={form.tipo} onChange={e => setF("tipo", e.target.value)}>
              {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          {form.tipo !== "2x1" && (
            <div>
              <label className="label">{form.tipo === "porcentaje" ? "Porcentaje de descuento" : "Monto de descuento (C$)"}</label>
              <input className="input" type="number" min="0" step="0.01" value={form.valor} onChange={e => setF("valor", e.target.value)} />
            </div>
          )}
          <div className="flex items-center gap-2">
            <input type="checkbox" id="add-activa" checked={form.activa} onChange={e => setF("activa", e.target.checked)}
              className="w-4 h-4 rounded border-border bg-surface text-brand-500 focus:ring-brand-500/40" />
            <label htmlFor="add-activa" className="text-sm text-content">Activa</label>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setAddOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={agregar} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
          </div>
        </div>
      </Modal>

      {/* Editar */}
      <Modal title="Editar promoción" open={editOpen} onClose={() => setEditOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Nombre *</label>
            <input className="input" value={editForm.nombre} onChange={e => setEF("nombre", e.target.value)} />
          </div>
          <div>
            <label className="label">Tipo</label>
            <select className="input" value={editForm.tipo} onChange={e => setEF("tipo", e.target.value)}>
              {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
          {editForm.tipo !== "2x1" && (
            <div>
              <label className="label">{editForm.tipo === "porcentaje" ? "Porcentaje de descuento" : "Monto de descuento (C$)"}</label>
              <input className="input" type="number" min="0" step="0.01" value={editForm.valor} onChange={e => setEF("valor", e.target.value)} />
            </div>
          )}
          <div className="flex items-center gap-2">
            <input type="checkbox" id="edit-activa" checked={editForm.activa} onChange={e => setEF("activa", e.target.checked)}
              className="w-4 h-4 rounded border-border bg-surface text-brand-500 focus:ring-brand-500/40" />
            <label htmlFor="edit-activa" className="text-sm text-content">Activa</label>
          </div>
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setEditOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={guardarEdicion} disabled={saving}>{saving ? "Guardando..." : "Guardar cambios"}</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
