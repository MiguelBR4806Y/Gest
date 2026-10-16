import { useEffect, useState } from "react";
import {
  AlertTriangle, Check, ChevronLeft, Lock, Mail, Palette, Trash2,
} from "lucide-react";

import Modal from "./Modal";
import { Button } from "./ui/Button";
import { Field, Input, Select } from "./ui/Field";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { ZONAS, api } from "../lib/api";
import { aplicarColorAcento, esHexValido } from "../lib/color";

const PERFIL_VACIO = {
  nombre_negocio: "",
  email: "",
  color_acento: "#1D9E75",
  tasa_cambio: 36,
  zona_horaria: "America/Managua",
};

const COLORES_SUGERIDOS = [
  "#1D9E75", "#2563EB", "#7C3AED", "#DB2777",
  "#EA580C", "#CA8A04", "#0891B2", "#475569",
];

export default function SettingsModal({ open, onClose, seccionInicial = "perfil" }) {
  const { user, logout, updateNegocio, updateUser } = useAuth();
  const { toast } = useToast();

  const [seccion, setSeccion] = useState(seccionInicial);
  const [perfil, setPerfil] = useState(PERFIL_VACIO);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [errorNombre, setErrorNombre] = useState("");
  const [errorTasa, setErrorTasa] = useState("");

  const [otpAbierto, setOtpAbierto] = useState(false);
  const [otpCodigo, setOtpCodigo] = useState("");
  const [otpCargando, setOtpCargando] = useState(false);

  const [editandoEmail, setEditandoEmail] = useState(false);
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [editandoPassword, setEditandoPassword] = useState(false);
  const [passwordData, setPasswordData] = useState({ password_actual: "", password_nuevo: "" });
  const [confirmandoBorrado, setConfirmandoBorrado] = useState(false);
  const [passwordBorrado, setPasswordBorrado] = useState("");
  const [borrando, setBorrando] = useState(false);

  // Al abrir se recarga el perfil desde el servidor.
  useEffect(() => {
    if (!open) return;
    setSeccion(seccionInicial);
    setEditandoEmail(false);
    setEditandoPassword(false);
    setConfirmandoBorrado(false);
    setNuevoEmail("");
    setPasswordBorrado("");
    setPasswordData({ password_actual: "", password_nuevo: "" });

    let cancelado = false;
    setCargando(true);
    api
      .get("/auth/perfil")
      .then((d) => {
        if (cancelado) return;
        setPerfil({
          nombre_negocio: d.nombre_negocio ?? "",
          email: d.email ?? "",
          color_acento: d.color_acento ?? "#1D9E75",
          tasa_cambio: d.tasa_cambio ?? 36,
          zona_horaria: d.zona_horaria || "America/Managua",
        });
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelado) setCargando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [open, seccionInicial]);

  // Previsualiza el color mientras se elige, sin guardar.
  useEffect(() => {
    if (!open) return;
    if (esHexValido(perfil.color_acento)) aplicarColorAcento(perfil.color_acento);
  }, [perfil.color_acento, open]);

  function set(campo, valor) {
    setPerfil((p) => ({ ...p, [campo]: valor }));
    if (campo === "nombre_negocio") setErrorNombre("");
    if (campo === "tasa_cambio") setErrorTasa("");
  }

  function validar() {
    let ok = true;
    if (!perfil.nombre_negocio.trim()) {
      setErrorNombre("El nombre del negocio es obligatorio");
      ok = false;
    }
    const tasa = Number(perfil.tasa_cambio);
    if (!Number.isFinite(tasa) || tasa <= 0) {
      setErrorTasa("La tasa debe ser mayor a cero");
      ok = false;
    }
    return ok;
  }

  async function guardarPerfil() {
    if (!validar()) return;
    setGuardando(true);
    try {
      await api.put("/auth/perfil", {
        ...perfil,
        tasa_cambio: Number(perfil.tasa_cambio),
      });

      const emailCambio = (perfil.email || "") !== (user?.email || "");

      updateNegocio(perfil.nombre_negocio);
      updateUser({
        email: perfil.email,
        email_verified: emailCambio ? false : user?.email_verified,
        tasa_cambio: Number(perfil.tasa_cambio),
        tasa_cambio_configurada: true,
        zona_horaria: perfil.zona_horaria,
      });

      toast("Configuración guardada");
      onClose?.();

      if (emailCambio && perfil.email) {
        setOtpCodigo("");
        setOtpAbierto(true);
      }
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function verificarOtp() {
    if (otpCodigo.length !== 6) return;
    setOtpCargando(true);
    try {
      await api.post("/auth/verificar-codigo", { codigo: otpCodigo });
      updateUser({ email_verified: true });
      setOtpAbierto(false);
      setOtpCodigo("");
      toast("Correo verificado");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setOtpCargando(false);
    }
  }

  async function reenviarOtp() {
    if (otpCargando) return;
    setOtpCargando(true);
    try {
      const r = await api.post("/auth/enviar-verificacion");
      toast(r.mensaje ?? "Código reenviado");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setOtpCargando(false);
    }
  }

  async function cambiarEmail() {
    const email = nuevoEmail.trim();
    if (!email) return;
    setGuardando(true);
    try {
      await api.put("/auth/perfil", { ...perfil, tasa_cambio: Number(perfil.tasa_cambio), email });
      updateUser({ email, email_verified: false });
      setPerfil((p) => ({ ...p, email }));
      setEditandoEmail(false);
      setNuevoEmail("");
      onClose?.();
      setOtpCodigo("");
      setOtpAbierto(true);
      toast("Correo actualizado");
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function cambiarPassword() {
    if (!passwordData.password_actual || !passwordData.password_nuevo) return;
    setGuardando(true);
    try {
      await api.put("/auth/password", passwordData);
      setPasswordData({ password_actual: "", password_nuevo: "" });
      setEditandoPassword(false);
      toast("Contraseña actualizada. Vuelve a iniciar sesión.");
      // El backend invalida los tokens anteriores al cambiar la contraseña.
      setTimeout(() => {
        logout();
        window.location.href = "/";
      }, 1200);
    } catch (e) {
      toast(e.message, "error");
    } finally {
      setGuardando(false);
    }
  }

  async function borrarCuenta() {
    setBorrando(true);
    try {
      await api.delete("/auth/cuenta", { password: passwordBorrado || "" });
      toast("Cuenta eliminada");
      logout();
      window.location.href = "/";
    } catch (e) {
      toast(e.message, "error");
      setBorrando(false);
    }
  }

  const esGoogle = user?.provider === "google";

  return (
    <>
      <Modal
        open={open}
        onClose={onClose}
        title={seccion === "perfil" ? "Configuración" : "Seguridad"}
        size="md"
        footer={
          seccion === "perfil" ? (
            <>
              <Button variant="secondary" onClick={onClose} disabled={guardando}>
                Cancelar
              </Button>
              <Button variant="primary" onClick={guardarPerfil} loading={guardando} disabled={cargando}>
                Guardar cambios
              </Button>
            </>
          ) : null
        }
      >
        {seccion === "perfil" ? (
          <div className="space-y-5">
            <Field
              label="Nombre del negocio"
              required
              error={errorNombre}
              hint="Aparece en el sidebar y en las facturas PDF."
            >
              <Input
                value={perfil.nombre_negocio}
                onChange={(e) => set("nombre_negocio", e.target.value)}
                placeholder="Ej: Tienda Los Andes"
                maxLength={120}
                error={errorNombre}
              />
            </Field>

            <div>
              <span className="label flex items-center gap-1.5">
                <Palette size={13} aria-hidden="true" />
                Color de acento
              </span>
              <div className="flex items-center gap-3 flex-wrap">
                <input
                  type="color"
                  aria-label="Elegir color de acento"
                  className="w-11 h-11 rounded-lg cursor-pointer border border-border bg-transparent p-0.5"
                  value={esHexValido(perfil.color_acento) ? perfil.color_acento : "#1D9E75"}
                  onChange={(e) => set("color_acento", e.target.value.toUpperCase())}
                />
                <div className="flex gap-1.5 flex-wrap">
                  {COLORES_SUGERIDOS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => set("color_acento", c)}
                      aria-label={`Usar color ${c}`}
                      aria-pressed={perfil.color_acento?.toUpperCase() === c}
                      className="w-7 h-7 rounded-md border border-border flex items-center justify-center
                                 transition-transform hover:scale-110"
                      style={{ backgroundColor: c }}
                    >
                      {perfil.color_acento?.toUpperCase() === c && (
                        <Check size={13} className="text-white drop-shadow" aria-hidden="true" />
                      )}
                    </button>
                  ))}
                </div>
                <span className="text-xs font-mono text-content-subtle">{perfil.color_acento}</span>
              </div>
              <p className="field-hint">Se aplica a botones, enlaces y resaltados de toda la interfaz.</p>
            </div>

            <Field
              label="Tasa de cambio (C$ por US$)"
              error={errorTasa}
              hint="Se usa en precios en dólares y en las facturas."
            >
              <Input
                type="number"
                min="1"
                step="0.01"
                inputMode="decimal"
                value={perfil.tasa_cambio}
                onChange={(e) => set("tasa_cambio", e.target.value)}
                error={errorTasa}
              />
            </Field>

            <Field label="Zona horaria" hint="Define cómo se muestran las horas en ventas y facturas.">
              <Select
                value={perfil.zona_horaria}
                onChange={(e) => set("zona_horaria", e.target.value)}
              >
                {ZONAS.map((z) => (
                  <option key={z} value={z}>
                    {z.replace(/_/g, " ").replace(/\//g, " / ")}
                  </option>
                ))}
              </Select>
            </Field>

            <button
              type="button"
              onClick={() => setSeccion("seguridad")}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium
                         text-content-muted hover:text-content hover:bg-surface-hover transition-colors
                         border border-border"
            >
              <Lock size={15} aria-hidden="true" />
              Seguridad de la cuenta
              <ChevronLeft size={15} className="ml-auto rotate-180" aria-hidden="true" />
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => setSeccion("perfil")}
              className="flex items-center gap-1.5 text-sm text-content-muted hover:text-content transition-colors"
            >
              <ChevronLeft size={15} aria-hidden="true" />
              Volver
            </button>

            {/* Correo */}
            <section className="p-4 rounded-xl bg-surface-sunken border border-border">
              <h4 className="text-sm font-semibold text-content flex items-center gap-2 mb-3">
                <Mail size={15} className="text-brand-500 dark:text-brand-300" aria-hidden="true" />
                Correo electrónico
              </h4>

              {!editandoEmail ? (
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-content truncate">
                    {user?.email || <span className="text-content-subtle">Sin configurar</span>}
                  </p>
                  <Button variant="ghost" size="sm" onClick={() => setEditandoEmail(true)}>
                    Cambiar
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <Field label="Nuevo correo">
                    <Input
                      type="email"
                      placeholder="nuevo@correo.com"
                      value={nuevoEmail}
                      onChange={(e) => setNuevoEmail(e.target.value)}
                      autoComplete="email"
                    />
                  </Field>
                  <p className="field-hint">
                    Se enviará un código de 6 dígitos para confirmar el cambio.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      onClick={cambiarEmail}
                      loading={guardando}
                      disabled={!nuevoEmail.trim()}
                    >
                      Guardar correo
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setEditandoEmail(false);
                        setNuevoEmail("");
                      }}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </section>

            {/* Contraseña */}
            <section className="p-4 rounded-xl bg-surface-sunken border border-border">
              <h4 className="text-sm font-semibold text-content flex items-center gap-2 mb-3">
                <Lock size={15} className="text-brand-500 dark:text-brand-300" aria-hidden="true" />
                Contraseña
              </h4>

              {esGoogle ? (
                <p className="text-sm text-content-muted">
                  Esta cuenta usa Google para iniciar sesión, no tiene contraseña local.
                </p>
              ) : !editandoPassword ? (
                <Button variant="ghost" size="sm" onClick={() => setEditandoPassword(true)}>
                  Cambiar contraseña
                </Button>
              ) : (
                <div className="space-y-3">
                  <Field label="Contraseña actual">
                    <Input
                      type="password"
                      autoComplete="current-password"
                      value={passwordData.password_actual}
                      onChange={(e) =>
                        setPasswordData((d) => ({ ...d, password_actual: e.target.value }))
                      }
                    />
                  </Field>
                  <Field
                    label="Nueva contraseña"
                    hint="Mínimo 8 caracteres, con letras y números."
                  >
                    <Input
                      type="password"
                      autoComplete="new-password"
                      value={passwordData.password_nuevo}
                      onChange={(e) =>
                        setPasswordData((d) => ({ ...d, password_nuevo: e.target.value }))
                      }
                    />
                  </Field>
                  <p className="field-hint">
                    Al cambiarla se cerrarán todas las sesiones abiertas.
                  </p>
                  <div className="flex gap-2">
                    <Button
                      onClick={cambiarPassword}
                      loading={guardando}
                      disabled={!passwordData.password_actual || !passwordData.password_nuevo}
                    >
                      Cambiar
                    </Button>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setEditandoPassword(false);
                        setPasswordData({ password_actual: "", password_nuevo: "" });
                      }}
                    >
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </section>

            {/* Zona de peligro */}
            <section className="p-4 rounded-xl bg-red-500/5 border border-red-500/25">
              <h4 className="text-sm font-semibold text-red-600 dark:text-red-400 flex items-center gap-2 mb-2">
                <Trash2 size={15} aria-hidden="true" />
                Zona de peligro
              </h4>

              {!confirmandoBorrado ? (
                <>
                  <p className="text-xs text-content-muted mb-3">
                    Elimina tu cuenta y todos los datos asociados (productos, clientes, ventas, promociones).
                    Esta acción no se puede deshacer.
                  </p>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmandoBorrado(true)}
                    className="text-red-600 dark:text-red-400 hover:bg-red-500/10">
                    Eliminar cuenta
                  </Button>
                </>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-start gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
                    <AlertTriangle size={18} className="text-red-500 shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                      <p className="text-sm font-semibold text-content">¿Confirmas la eliminación?</p>
                      <p className="text-xs text-content-muted mt-0.5">
                        Se borrarán todos tus datos de forma permanente.
                      </p>
                    </div>
                  </div>

                  {!esGoogle && (
                    <Field label="Escribe tu contraseña para confirmar">
                      <Input
                        type="password"
                        autoComplete="current-password"
                        value={passwordBorrado}
                        onChange={(e) => setPasswordBorrado(e.target.value)}
                      />
                    </Field>
                  )}

                  <div className="flex gap-2">
                    <Button
                      variant="danger"
                      onClick={borrarCuenta}
                      loading={borrando}
                      disabled={!esGoogle && !passwordBorrado}
                    >
                      Eliminar definitivamente
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirmandoBorrado(false)}>
                      Cancelar
                    </Button>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </Modal>

      <Modal
        open={otpAbierto}
        onClose={() => setOtpAbierto(false)}
        title="Verifica tu correo"
        size="sm"
      >
        <div className="space-y-5 text-center">
          <p className="text-sm text-content-muted">
            Enviamos un código de 6 dígitos a{" "}
            <strong className="text-content">{perfil.email || user?.email}</strong>
          </p>
          <Field label="Código de verificación">
            <Input
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="000000"
              className="text-center text-2xl tracking-[0.5em] font-mono"
              value={otpCodigo}
              onChange={(e) => setOtpCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))}
            />
          </Field>
          <Button
            onClick={verificarOtp}
            loading={otpCargando}
            disabled={otpCodigo.length !== 6}
            className="w-full"
          >
            Verificar código
          </Button>
          <button
            type="button"
            onClick={reenviarOtp}
            disabled={otpCargando}
            className="text-sm text-brand-600 dark:text-brand-300 hover:underline disabled:opacity-50"
          >
            ¿No lo recibiste? Reenviar
          </button>
        </div>
      </Modal>
    </>
  );
}
