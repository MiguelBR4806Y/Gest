import { useCallback, useEffect, useMemo, useState } from "react";
import { KeyRound, Pencil, Plus, Power, Trash2, UserCog } from "lucide-react";

import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import CredencialesBox from "../components/CredencialesBox";
import Modal, { ConfirmDialog } from "../components/Modal";

const VACIO = {
  nombre: "", puesto: "", salario: "", comision_pct: "", fecha_ingreso: "",
  usuario: "", password: "", modulos: ["ventas"],
};

const MODULOS = [
  { id: "ventas", label: "Ventas" },
  { id: "contabilidad", label: "Contabilidad" },
  { id: "rrhh", label: "RRHH" },
];

export default function VendedoresPage() {
  const { toast } = useToast();
  const { user } = useAuth();
  const [datos, setDatos] = useState({ items: [], total: 0, limite: 10 });
  const [cargando, setCargando] = useState(true);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [credenciales, setCredenciales] = useState(null);
  const [aEliminar, setAEliminar] = useState(null);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get("/vendedores/");
      setDatos({
        items: data?.items ?? [],
        total: data?.total ?? 0,
        limite: data?.limite ?? 10,
      });
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setCargando(false);
    }
  }, [toast]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const limiteAlcanzado = datos.total >= datos.limite;
  const activos = useMemo(() => datos.items.filter((v) => v.activo).length, [datos.items]);

  function abrirNuevo() {
    setForm(VACIO);
    setEditando(null);
    setAbierta(true);
  }

  function abrirEdicion(v) {
    setForm({
      nombre: v.nombre,
      puesto: v.puesto ?? "",
      salario: v.salario ? String(v.salario) : "",
      comision_pct: v.comision_pct ? String(v.comision_pct) : "",
      fecha_ingreso: v.fecha_ingreso ?? "",
      usuario: v.usuario,
      password: "",
      modulos: v.modulos?.length ? v.modulos : ["ventas"],
    });
    setEditando(v);
    setAbierta(true);
  }

  async function guardar(e) {
    e?.preventDefault();
    if (!form.nombre.trim()) return;
    setGuardando(true);
    try {
      if (editando) {
        const cuerpo = {
          nombre: form.nombre.trim(),
          salario: Number(form.salario) || 0,
          comision_pct: Number(form.comision_pct) || 0,
          fecha_ingreso: form.fecha_ingreso || null,
          modulos: form.modulos,
        };
        if (form.puesto.trim()) cuerpo.puesto = form.puesto.trim();
        if (form.usuario.trim() && form.usuario.trim() !== editando.usuario) {
          cuerpo.usuario = form.usuario.trim();
        }
        if (form.password) cuerpo.password = form.password;
        const actualizado = await api.put(`/vendedores/${editando.id}`, cuerpo);
        setAbierta(false);
        toast("Vendedor actualizado");
        if (actualizado?.password) {
          setCredenciales({ usuario: actualizado.usuario, password: actualizado.password });
        }
      } else {
        const cuerpo = {
          nombre: form.nombre.trim(),
          salario: Number(form.salario) || 0,
          comision_pct: Number(form.comision_pct) || 0,
          fecha_ingreso: form.fecha_ingreso || null,
          modulos: form.modulos,
        };
        if (form.puesto.trim()) cuerpo.puesto = form.puesto.trim();
        if (form.usuario.trim()) cuerpo.usuario = form.usuario.trim();
        if (form.password) cuerpo.password = form.password;
        const creado = await api.post("/vendedores/", cuerpo);
        setAbierta(false);
        setCredenciales({ usuario: creado.usuario, password: creado.password });
        toast("Vendedor creado con sus credenciales");
      }
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function verCredenciales(v) {
    try {
      const data = await api.get(`/vendedores/${v.id}/credenciales`);
      setCredenciales({ usuario: data.usuario, password: data.password });
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function alternarActivo(v) {
    try {
      await api.put(`/vendedores/${v.id}`, { activo: !v.activo });
      toast(v.activo ? "Vendedor desactivado" : "Vendedor activado");
      cargar();
    } catch (e) {
      toast(e.message, "error");
    }
  }

  async function eliminar() {
    setGuardando(true);
    try {
      const r = await api.delete(`/vendedores/${aEliminar.id}`);
      toast(r?.mensaje ?? "Vendedor eliminado", r?.desactivado ? "info" : undefined);
      setAEliminar(null);
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
          <h1>Vendedores</h1>
          <p>
            {datos.total} de {datos.limite} cuentas usadas
          </p>
        </div>
        <Button icon={Plus} onClick={abrirNuevo} disabled={limiteAlcanzado}>
          {limiteAlcanzado ? "Límite alcanzado" : "Crear vendedor"}
        </Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard
          icon={UserCog}
          label="Vendedores"
          value={`${datos.total}/${datos.limite}`}
          sub="Límite por negocio"
        />
        <StatCard icon={UserCog} label="Activos" value={activos} tono="green" sub="Pueden vender" />
        <StatCard
          icon={UserCog}
          label="Desactivados"
          value={datos.total - activos}
          tono="yellow"
          sub="Sin acceso"
        />
      </div>

      {limiteAlcanzado && (
        <div className="card p-4 border-accent-500/30 bg-accent-500/5 text-sm text-content-muted" role="status">
          Alcanzaste el límite de {datos.limite} vendedores. Desactiva o elimina uno para crear otro.
        </div>
      )}

      {cargando ? (
        <TableSkeleton filas={4} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {datos.items.length === 0 ? (
            <EmptyState
              icon={UserCog}
              title="Aún no hay vendedores"
              text="Crea una cuenta y comparte las credenciales. Solo podrá vender y ver el inventario."
              action={<Button icon={Plus} onClick={abrirNuevo}>Crear vendedor</Button>}
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Nombre</th>
                    <th className="th">Usuario</th>
                    <th className="th hidden sm:table-cell">Ventas</th>
                    <th className="th hidden md:table-cell">Estado</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.items.map((v) => (
                    <tr key={v.id} className="table-row">
                      <td className="td">
                        <p className="font-medium text-content">{v.nombre}</p>
                        <p className="text-xs text-content-subtle">{v.puesto || "Vendedor"}</p>
                      </td>
                      <td className="td font-mono text-sm text-content-muted">{v.usuario}</td>
                      <td className="td hidden sm:table-cell tabular">{v.ventas}</td>
                      <td className="td hidden md:table-cell">
                        <span className={v.activo ? "badge-green" : "badge-neutral"}>
                          {v.activo ? "Activo" : "Desactivado"}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton
                            label="Ver credenciales"
                            icon={KeyRound}
                            onClick={() => verCredenciales(v)}
                          />
                          <IconButton label="Editar" icon={Pencil} onClick={() => abrirEdicion(v)} />
                          <IconButton
                            label={v.activo ? "Desactivar" : "Activar"}
                            icon={Power}
                            onClick={() => alternarActivo(v)}
                            className={v.activo ? "text-accent-600 hover:bg-accent-500/10" : "text-secondary-600"}
                          />
                          <IconButton
                            label="Eliminar"
                            icon={Trash2}
                            onClick={() => setAEliminar(v)}
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
        title={editando ? "Editar vendedor" : "Nuevo vendedor"}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAbierta(false)}>
              Cancelar
            </button>
            <Button onClick={guardar} loading={guardando} disabled={!form.nombre.trim()}>
              {editando ? "Guardar cambios" : "Crear y generar credenciales"}
            </Button>
          </>
        }
      >
        <form onSubmit={guardar} className="space-y-4">
          <Field label="Nombre" required hint="Se usa para generar el usuario si lo dejas vacío">
            <Input
              value={form.nombre}
              onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              placeholder="Ana Pérez"
              autoFocus
            />
          </Field>
          <Field label="Puesto" hint="Aparece en Empleados. Por defecto: Vendedor">
            <Input
              value={form.puesto}
              onChange={(e) => setForm((f) => ({ ...f, puesto: e.target.value }))}
              placeholder="Vendedor"
              maxLength={80}
            />
          </Field>
          <Field label="Salario bruto mensual (C$)" hint="Opcional. Se usa para la planilla en Empleados.">
            <Input
              type="number"
              min="0"
              step="0.01"
              value={form.salario}
              onChange={(e) => setForm((f) => ({ ...f, salario: e.target.value }))}
              placeholder="12000"
              inputMode="decimal"
            />
          </Field>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field
              label="Comisión (%)"
              hint="Porcentaje sobre sus propias ventas del mes."
            >
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={form.comision_pct}
                onChange={(e) => setForm((f) => ({ ...f, comision_pct: e.target.value }))}
                placeholder="0"
                inputMode="decimal"
              />
            </Field>
            <Field label="Fecha de ingreso" hint="Base para calcular vacaciones.">
              <Input
                type="date"
                value={form.fecha_ingreso}
                onChange={(e) => setForm((f) => ({ ...f, fecha_ingreso: e.target.value }))}
              />
            </Field>
          </div>
          <Field label="Módulos" hint="Qué puede usar esta cuenta al iniciar sesión.">
            <div className="flex flex-wrap gap-1.5">
              {MODULOS.map((m) => {
                const activo = form.modulos.includes(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    aria-pressed={activo}
                    onClick={() =>
                      setForm((f) => ({
                        ...f,
                        modulos: activo
                          ? f.modulos.filter((x) => x !== m.id)
                          : [...f.modulos, m.id],
                      }))
                    }
                    className={`badge cursor-pointer transition-colors ${
                      activo ? "badge-green" : "badge-neutral opacity-60"
                    }`}
                  >
                    {m.label}
                  </button>
                );
              })}
            </div>
          </Field>
          <Field label="Usuario" hint="Letras, números, punto, guion y guion bajo">
            <Input
              value={form.usuario}
              onChange={(e) => setForm((f) => ({ ...f, usuario: e.target.value }))}
              placeholder={editando?.usuario || "ana.perez"}
              autoComplete="off"
            />
          </Field>
          <Field
            label="Contraseña"
            hint={
              editando
                ? "Déjala vacía para conservar la actual"
                : "Déjala vacía para generar una segura automáticamente"
            }
          >
            <Input
              type="text"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              placeholder="••••••••••••"
              autoComplete="new-password"
            />
          </Field>
          {!editando && (
            <p className="text-xs text-content-subtle">
              Negocio: {user?.nombre_negocio}. El vendedor verá el mismo inventario y clientes que tú.
            </p>
          )}
        </form>
      </Modal>

      <Modal
        open={Boolean(credenciales)}
        onClose={() => setCredenciales(null)}
        title="Credenciales del vendedor"
        size="sm"
        footer={
          <button type="button" className="btn-primary" onClick={() => setCredenciales(null)}>
            Entendido
          </button>
        }
      >
        {credenciales && (
          <CredencialesBox usuario={credenciales.usuario} password={credenciales.password} />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(aEliminar)}
        onClose={() => setAEliminar(null)}
        onConfirm={eliminar}
        loading={guardando}
        title="Eliminar vendedor"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará la cuenta de "${aEliminar?.nombre ?? ""}". Si ya registró ventas, solo se desactivará para no alterar el historial.`}
      />
    </div>
  );
}
