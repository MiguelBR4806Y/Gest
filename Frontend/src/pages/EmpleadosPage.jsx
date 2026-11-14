import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Calculator, Download, Eye, Gift, Palmtree, Pencil, Plus, Search, Trash2,
  UserCog, UserRound, UsersRound, Wallet,
} from "lucide-react";

import { api, fmtMoney } from "../lib/api";
import { useToast } from "../context/ToastContext";
import { useAuth } from "../context/AuthContext";
import { useDebounce } from "../hooks/useDebounce";
import { Button, IconButton } from "../components/ui/Button";
import { Card, EmptyState, StatCard } from "../components/ui/Card";
import { Field, Input, Textarea, Checkbox } from "../components/ui/Field";
import { TableSkeleton } from "../components/ui/Feedback";
import CredencialesBox from "../components/CredencialesBox";
import BonosModal from "../components/BonosModal";
import VacacionesModal from "../components/VacacionesModal";
import CalculadoraNomina, { DesgloseNomina } from "../components/Nomina";
import Modal, { ConfirmDialog } from "../components/Modal";

const VACIO = {
  nombre: "", puesto: "", salario: "", comision_pct: "", fecha_ingreso: "",
  telefono: "", notas: "", activo: true,
  dar_acceso: false, modulos: ["ventas"], usuario: "", password: "",
};

const MODULOS = [
  { id: "ventas", label: "Ventas", texto: "Cobrar y ver inventario" },
  { id: "contabilidad", label: "Contabilidad", texto: "Gastos, compras y reportes" },
  { id: "rrhh", label: "RRHH", texto: "Plantilla y nómina" },
];

const PUESTOS_SUGERIDOS = [
  "Limpiador", "Limpieza", "Seguridad", "Bodega", "Cajero", "Repartidor",
  "Cocinero", "Atención al cliente", "Administración",
];

export default function EmpleadosPage() {
  const { toast } = useToast();
  const [datos, setDatos] = useState({
    items: [], total: 0, con_acceso: 0, sin_acceso: 0, resumen: null,
  });
  const [cargando, setCargando] = useState(true);
  const [busqueda, setBusqueda] = useState("");
  const busquedaDiferida = useDebounce(busqueda, 250);
  const [filtro, setFiltro] = useState("todos");

  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState(null);
  const [abierta, setAbierta] = useState(false);
  const [aEliminar, setAEliminar] = useState(null);
  const [guardando, setGuardando] = useState(false);
  const [nominaDe, setNominaDe] = useState(null);
  const [calculadoraAbierta, setCalculadoraAbierta] = useState(false);
  const [salarioCalculadora, setSalarioCalculadora] = useState(0);
  const [credenciales, setCredenciales] = useState(null);
  const [bonosDe, setBonosDe] = useState(null);
  const [vacacionesDe, setVacacionesDe] = useState(null);
  const { esAdmin, puede } = useAuth();

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const data = await api.get("/empleados/");
      setDatos({
        items: data?.items ?? [],
        total: data?.total ?? 0,
        con_acceso: data?.con_acceso ?? 0,
        sin_acceso: data?.sin_acceso ?? 0,
        resumen: data?.resumen ?? null,
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

  const filtrados = useMemo(() => {
    const q = busquedaDiferida.trim().toLowerCase();
    return datos.items.filter((e) => {
      if (filtro === "acceso" && !e.con_acceso) return false;
      if (filtro === "sin" && e.con_acceso) return false;
      if (!q) return true;
      return (
        e.nombre.toLowerCase().includes(q) ||
        e.puesto.toLowerCase().includes(q) ||
        (e.usuario ?? "").toLowerCase().includes(q)
      );
    });
  }, [datos.items, busquedaDiferida, filtro]);

  function abrirNuevo() {
    setForm(VACIO);
    setEditando(null);
    setAbierta(true);
  }

  function abrirEdicion(e) {
    setForm({
      nombre: e.nombre,
      puesto: e.puesto ?? "",
      salario: e.salario ? String(e.salario) : "",
      comision_pct: e.comision_pct ? String(e.comision_pct) : "",
      fecha_ingreso: e.fecha_ingreso ?? "",
      telefono: e.telefono ?? "",
      notas: e.notas ?? "",
      activo: e.activo,
      dar_acceso: false,
      modulos: e.modulos?.length ? e.modulos : ["ventas"],
      usuario: "",
      password: "",
    });
    setEditando(e);
    setAbierta(true);
  }

  async function guardar(ev) {
    ev?.preventDefault();
    if (!form.nombre.trim() || !form.puesto.trim()) return;
    if (form.dar_acceso && form.modulos.length === 0) {
      toast("Marca al menos un módulo para dar acceso", "error");
      return;
    }
    setGuardando(true);
    try {
      const cuerpo = {
        nombre: form.nombre.trim(),
        puesto: form.puesto.trim(),
        salario: Number(form.salario) || 0,
        comision_pct: Number(form.comision_pct) || 0,
        fecha_ingreso: form.fecha_ingreso || null,
        telefono: form.telefono.trim() || null,
        notas: form.notas.trim() || null,
        activo: form.activo,
        dar_acceso: Boolean(form.dar_acceso),
        modulos: form.dar_acceso ? form.modulos : [],
      };
      if (form.dar_acceso) {
        if (form.usuario.trim()) cuerpo.usuario = form.usuario.trim();
        if (form.password) cuerpo.password = form.password;
      }

      if (editando) {
        await api.put(`/empleados/${editando.id}`, {
          nombre: cuerpo.nombre,
          puesto: cuerpo.puesto,
          salario: cuerpo.salario,
          comision_pct: cuerpo.comision_pct,
          fecha_ingreso: cuerpo.fecha_ingreso,
          telefono: cuerpo.telefono,
          notas: cuerpo.notas,
          activo: cuerpo.activo,
        });
      } else {
        const creado = await api.post("/empleados/", cuerpo);
        if (creado?.credenciales) {
          setCredenciales({
            usuario: creado.credenciales.usuario,
            password: creado.credenciales.password,
          });
        }
      }

      setAbierta(false);
      toast(
        editando
          ? "Empleado actualizado"
          : form.dar_acceso
            ? "Empleado creado con acceso al sistema"
            : "Empleado registrado"
      );
      cargar();
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  function alternarModulo(id) {
    setForm((f) => ({
      ...f,
      modulos: f.modulos.includes(id)
        ? f.modulos.filter((m) => m !== id)
        : [...f.modulos, id],
    }));
  }

  async function eliminar() {
    setGuardando(true);
    try {
      await api.delete(`/empleados/${aEliminar.id}`);
      toast("Empleado eliminado");
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
          <h1>RRHH · Plantilla</h1>
          <p>{datos.total} registrados · {datos.con_acceso} con acceso al sistema</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            icon={Download}
            onClick={() => api.descargar("/empleados/exportar", "planilla.csv")}
          >
            Exportar planilla
          </Button>
          <Button icon={Calculator} variant="secondary" onClick={() => setCalculadoraAbierta(true)}>
            Calcular impuestos
          </Button>
          <Button icon={Plus} onClick={abrirNuevo}>
            Registrar empleado
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={UsersRound} label="Empleados" value={datos.total} sub="Plantilla completa" />
        <StatCard
          icon={UserCog}
          label="Con acceso"
          value={datos.con_acceso}
          tono="green"
          sub="Vendedores con cuenta"
        />
        <StatCard
          icon={UserRound}
          label="Sin acceso"
          value={datos.sin_acceso}
          tono="yellow"
          sub="Solo registro"
        />
      </div>

      {datos.resumen && datos.resumen.cantidad > 0 && (
        <Card className="p-5">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h3 className="section-title">Planilla mensual</h3>
              <p className="text-xs text-content-subtle mt-0.5">
                {datos.resumen.cantidad} con salario configurado
                {datos.resumen.sin_salario > 0 &&
                  ` · ${datos.resumen.sin_salario} sin salario`}
              </p>
            </div>
            <Calculator size={18} className="text-content-subtle" aria-hidden="true" />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Salarios brutos", valor: datos.resumen.total_bruto },
              { label: "Neto a pagar", valor: datos.resumen.total_neto },
              { label: "INSS + IR retenido", valor: datos.resumen.total_inss_laboral + datos.resumen.total_ir },
              { label: "Costo de la empresa", valor: datos.resumen.costo_empresa },
            ].map((m) => (
              <div key={m.label}>
                <p className="text-[11px] uppercase tracking-wide text-content-subtle">{m.label}</p>
                <p className="text-lg font-semibold tabular text-content mt-0.5">
                  {fmtMoney(m.valor)}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-border/70 flex flex-wrap gap-x-6 gap-y-1 text-xs text-content-muted">
            <span>INSS patronal: <span className="tabular">{fmtMoney(datos.resumen.total_inss_patronal)}</span></span>
            <span>INATEC: <span className="tabular">{fmtMoney(datos.resumen.total_inatec)}</span></span>
          </div>
        </Card>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-content-subtle pointer-events-none"
          />
          <Input
            className="pl-10"
            placeholder="Buscar por nombre, puesto o usuario…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar empleados"
          />
        </div>
        <div className="segmented shrink-0" role="tablist" aria-label="Filtrar empleados">
          {[
            { id: "todos", label: "Todos" },
            { id: "acceso", label: "Con acceso" },
            { id: "sin", label: "Sin acceso" },
          ].map((opcion) => (
            <button
              key={opcion.id}
              type="button"
              role="tab"
              aria-selected={filtro === opcion.id}
              className={`segment ${filtro === opcion.id ? "segment-active" : ""}`}
              onClick={() => setFiltro(opcion.id)}
            >
              {opcion.label}
            </button>
          ))}
        </div>
      </div>

      {cargando ? (
        <TableSkeleton filas={6} columnas={5} />
      ) : (
        <Card className="overflow-hidden">
          {filtrados.length === 0 ? (
            <EmptyState
              icon={UsersRound}
              title={datos.total === 0 ? "Sin empleados" : "Sin resultados"}
              text={
                datos.total === 0
                  ? "Los vendedores aparecen aquí automáticamente. Registra al resto del personal."
                  : "Prueba con otro término o cambia el filtro."
              }
              action={
                datos.total === 0 && (
                  <Button size="sm" icon={Plus} onClick={abrirNuevo}>
                    Registrar empleado
                  </Button>
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full table-sticky">
                <thead>
                  <tr>
                    <th className="th">Nombre</th>
                    <th className="th">Puesto</th>
                    <th className="th hidden sm:table-cell text-right">Salario</th>
                    <th className="th hidden lg:table-cell text-right">Comisión</th>
                    <th className="th hidden sm:table-cell text-right">Neto</th>
                    <th className="th hidden lg:table-cell text-right">Vacaciones</th>
                    <th className="th hidden lg:table-cell">Acceso</th>
                    <th className="th hidden lg:table-cell">Estado</th>
                    <th className="th text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {filtrados.map((e) => (
                    <tr key={`${e.tipo}-${e.id}`} className="table-row">
                      <td className="td">
                        <p className="font-medium text-content">{e.nombre}</p>
                        {e.usuario && (
                          <p className="text-xs font-mono text-content-subtle">@{e.usuario}</p>
                        )}
                      </td>
                      <td className="td">
                        <span className="badge-neutral">{e.puesto}</span>
                      </td>
                      <td className="td hidden sm:table-cell text-right tabular">
                        {e.salario > 0 ? fmtMoney(e.salario) : <span className="text-content-subtle">Sin salario</span>}
                      </td>
                      <td className="td hidden lg:table-cell text-right tabular">
                        {e.comision_pct > 0 ? (
                          <span>
                            {Number(e.comision_pct).toFixed(2)}%
                            {e.comision?.comision > 0 && (
                              <span className="block text-xs text-content-subtle">
                                {fmtMoney(e.comision.comision)}
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-content-subtle">—</span>
                        )}
                      </td>
                      <td className="td hidden sm:table-cell text-right tabular">
                        {e.nomina ? (
                          <span className="font-medium text-secondary-600 dark:text-secondary-400">
                            {fmtMoney(e.nomina.salario_neto)}
                          </span>
                        ) : (
                          <span className="text-content-subtle">—</span>
                        )}
                      </td>
                      <td className="td hidden lg:table-cell text-right tabular">
                        {e.vacaciones?.configurado ? (
                          <span>
                            {Number(e.vacaciones.dias_disponibles).toFixed(1)} d
                            <span className="block text-xs text-content-subtle">
                              {fmtMoney(e.vacaciones.valor_dias)}
                            </span>
                          </span>
                        ) : (
                          <span className="text-content-subtle" title="Falta la fecha de ingreso">
                            —
                          </span>
                        )}
                      </td>
                      <td className="td hidden lg:table-cell">
                        {e.con_acceso ? (
                          <span className="badge-green">Con cuenta</span>
                        ) : (
                          <span className="badge-yellow">Solo registro</span>
                        )}
                      </td>
                      <td className="td hidden lg:table-cell">
                        <span className={e.activo ? "badge-green" : "badge-neutral"}>
                          {e.activo ? "Activo" : "Inactivo"}
                        </span>
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-0.5">
                          <IconButton
                            label="Bonos"
                            icon={Gift}
                            onClick={() => setBonosDe(e)}
                          />
                          <IconButton
                            label="Vacaciones"
                            icon={Palmtree}
                            onClick={() => setVacacionesDe(e)}
                          />
                          {e.nomina && (
                            <>
                              <IconButton
                                label="Ver desglose de nómina"
                                icon={Eye}
                                onClick={() => setNominaDe(e)}
                              />
                              <IconButton
                                label="Simular este salario"
                                icon={Wallet}
                                onClick={() => {
                                  setSalarioCalculadora(e.salario);
                                  setCalculadoraAbierta(true);
                                }}
                              />
                            </>
                          )}
                          {e.con_acceso ? (
                            <span className="text-xs text-content-subtle pr-1">
                              Se edita en Vendedores
                            </span>
                          ) : (
                            <>
                              <IconButton label="Editar" icon={Pencil} onClick={() => abrirEdicion(e)} />
                              <IconButton
                                label="Eliminar"
                                icon={Trash2}
                                onClick={() => setAEliminar(e)}
                                className="text-red-500 hover:bg-red-500/10"
                              />
                            </>
                          )}
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
        title={editando ? "Editar empleado" : "Registrar empleado"}
        footer={
          <>
            <button type="button" className="btn-secondary" onClick={() => setAbierta(false)}>
              Cancelar
            </button>
            <Button
              onClick={guardar}
              loading={guardando}
              disabled={!form.nombre.trim() || !form.puesto.trim()}
            >
              {editando ? "Guardar cambios" : "Registrar empleado"}
            </Button>
          </>
        }
      >
        <form onSubmit={guardar} className="space-y-4">
          <Field label="Nombre" required>
            <Input
              value={form.nombre}
              onChange={(e2) => setForm((f) => ({ ...f, nombre: e2.target.value }))}
              placeholder="María López"
              autoFocus
            />
          </Field>

          <Field label="Puesto" required hint="Escribe el puesto que quieras: limpieza, seguridad, bodega…">
            <Input
              value={form.puesto}
              onChange={(e2) => setForm((f) => ({ ...f, puesto: e2.target.value }))}
              placeholder="Limpiador"
              list="puestos-sugeridos"
            />
          </Field>
          <datalist id="puestos-sugeridos">
            {PUESTOS_SUGERIDOS.map((p) => (
              <option key={p} value={p} />
            ))}
          </datalist>

          <Field
            label="Salario bruto mensual (C$)"
            hint={
              Number(form.salario) > 0
                ? "El desglose de INSS e IR se muestra al guardar."
                : "Opcional. Déjalo en 0 si no lleva salario en el sistema."
            }
          >
            <Input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              value={form.salario}
              onChange={(e2) => setForm((f) => ({ ...f, salario: e2.target.value }))}
              placeholder="12000"
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Field
              label="Comisión (%)"
              hint="Solo aplica a cuentas con ventas propias. En personal sin cuenta no genera comisión."
            >
              <Input
                type="number"
                min="0"
                max="100"
                step="0.01"
                inputMode="decimal"
                value={form.comision_pct}
                onChange={(e2) => setForm((f) => ({ ...f, comision_pct: e2.target.value }))}
                placeholder="0"
              />
            </Field>
            <Field label="Fecha de ingreso" hint="Base para calcular las vacaciones.">
              <Input
                type="date"
                value={form.fecha_ingreso}
                onChange={(e2) => setForm((f) => ({ ...f, fecha_ingreso: e2.target.value }))}
              />
            </Field>
          </div>

          <Field label="Teléfono">
            <Input
              value={form.telefono}
              onChange={(e2) => setForm((f) => ({ ...f, telefono: e2.target.value }))}
              placeholder="8888-1234"
              inputMode="tel"
            />
          </Field>

          <Field label="Notas" hint="Horario, días de trabajo, observaciones…">
            <Textarea
              value={form.notas}
              onChange={(e2) => setForm((f) => ({ ...f, notas: e2.target.value }))}
              placeholder="Trabaja lunes, miércoles y viernes por la mañana."
            />
          </Field>

          {!editando && (
            <div className="rounded-xl border border-border p-4 space-y-3">
              <Checkbox
                label="Dar acceso al sistema"
                checked={form.dar_acceso}
                onChange={(e2) => setForm((f) => ({ ...f, dar_acceso: e2.target.checked }))}
              />

              {form.dar_acceso ? (
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                    {MODULOS.map((m) => {
                      // RRHH no puede conceder módulos que él mismo no tiene.
                      const disponible = esAdmin || puede(m.id);
                      return (
                        <label
                          key={m.id}
                          className={`rounded-lg border p-2.5 text-xs cursor-pointer transition-colors ${
                            form.modulos.includes(m.id)
                              ? "border-brand-500/50 bg-brand-500/5"
                              : "border-border"
                          } ${disponible ? "" : "opacity-40 cursor-not-allowed"}`}
                        >
                          <input
                            type="checkbox"
                            className="sr-only"
                            checked={form.modulos.includes(m.id)}
                            disabled={!disponible}
                            onChange={() => alternarModulo(m.id)}
                          />
                          <span className="block font-medium text-content">{m.label}</span>
                          <span className="block text-content-subtle mt-0.5">{m.texto}</span>
                        </label>
                      );
                    })}
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Field label="Usuario" hint="Si lo dejas vacío se genera">
                      <Input
                        value={form.usuario}
                        onChange={(e2) => setForm((f) => ({ ...f, usuario: e2.target.value }))}
                        placeholder="ana.perez"
                        autoComplete="off"
                      />
                    </Field>
                    <Field label="Contraseña" hint="Si la dejas vacía se genera">
                      <Input
                        type="text"
                        value={form.password}
                        onChange={(e2) => setForm((f) => ({ ...f, password: e2.target.value }))}
                        placeholder="••••••••••••"
                        autoComplete="new-password"
                      />
                    </Field>
                  </div>

                  <p className="text-xs text-content-subtle">
                    Al guardar se muestran las credenciales una vez. Podrás consultarlas después
                    en Vendedores.
                  </p>
                </>
              ) : (
                <p className="text-xs text-content-subtle">
                  Sin acceso solo queda como registro de personal. Si necesita cobrar ventas o
                  llevar contabilidad, marca la casilla.
                </p>
              )}
            </div>
          )}

          {editando && (
            <p className="text-xs text-content-subtle">
              Los datos de acceso y credenciales se editan en{" "}
              <span className="font-medium">Vendedores</span>.
            </p>
          )}
        </form>
      </Modal>

      <Modal
        open={Boolean(nominaDe)}
        onClose={() => setNominaDe(null)}
        title={`Nómina — ${nominaDe?.nombre ?? ""}`}
        size="sm"
        footer={
          <button type="button" className="btn-secondary" onClick={() => setNominaDe(null)}>
            Cerrar
          </button>
        }
      >
        {nominaDe && (
          <div className="space-y-3">
            <p className="text-sm text-content-muted">
              {nominaDe.puesto}
              {nominaDe.salario > 0 && ` · ${fmtMoney(nominaDe.salario)} brutos`}
            </p>
            <DesgloseNomina nomina={nominaDe.nomina} />
          </div>
        )}
      </Modal>

      <CalculadoraNomina
        open={calculadoraAbierta}
        onClose={() => setCalculadoraAbierta(false)}
        salarioInicial={salarioCalculadora}
      />

      <BonosModal
        persona={bonosDe ? { ...bonosDe, tipo: bonosDe.tipo === "vendedor" ? "cuenta" : "empleado" } : null}
        open={Boolean(bonosDe)}
        onClose={() => setBonosDe(null)}
        onCambio={cargar}
      />

      <VacacionesModal
        persona={vacacionesDe ? { ...vacacionesDe, tipo: vacacionesDe.tipo === "vendedor" ? "cuenta" : "empleado" } : null}
        open={Boolean(vacacionesDe)}
        onClose={() => setVacacionesDe(null)}
        onCambio={cargar}
      />

      <Modal
        open={Boolean(credenciales)}
        onClose={() => setCredenciales(null)}
        title="Credenciales de acceso"
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
        title="Eliminar empleado"
        confirmLabel="Eliminar"
        mensaje={`Se eliminará "${aEliminar?.nombre ?? ""}" del registro de personal.`}
      />
    </div>
  );
}
