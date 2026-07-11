import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { api, ZONAS } from "../lib/api";
import { useTheme } from "../hooks/useTheme";
import Modal from "./Modal";
import {
  LayoutDashboard, Package, ShoppingCart, Users, FolderOpen, Tag, Bot,
  LogOut, Menu, X, Settings, ChevronRight, Sun, Moon, Monitor, ChevronLeft,
  Lock, Trash2, AlertTriangle
} from "lucide-react";

const NAV = [
  { to: "/dashboard",    icon: LayoutDashboard, label: "Dashboard" },
  { to: "/inventario",   icon: Package,         label: "Inventario" },
  { to: "/ventas",       icon: ShoppingCart,    label: "Ventas" },
  { to: "/clientes",     icon: Users,           label: "Clientes" },
  { to: "/promociones",  icon: Tag,             label: "Promociones" },
  { to: "/gesti",        icon: Bot,              label: "Gesti IA" },
  { to: "/organizacion", icon: FolderOpen,      label: "Organización" },
];

export default function Layout({ children }) {
  const { user, logout, updateNegocio, updateUser } = useAuth();
  const { toast } = useToast();
  const [dark, theme, cycleTheme] = useTheme();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem("sidebarCollapsed") === "true");
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState({ nombre_negocio: "", email: "", color_acento: "#428dc7", tasa_cambio: 36.0, zona_horaria: "America/Managua" });
  const [saving, setSaving] = useState(false);
  const [dismissEmailAlert, setDismissEmailAlert] = useState(() => sessionStorage.getItem("dismissEmailAlert") === "true");
  const [showSecurity, setShowSecurity] = useState(false);
  const [passwordData, setPasswordData] = useState({ password_actual: "", password_nuevo: "" });
  const [changingPassword, setChangingPassword] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [otpOpen, setOtpOpen] = useState(false);
  const [otpCodigo, setOtpCodigo] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [emailEditConfirm, setEmailEditConfirm] = useState(false);
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [passwordEditConfirm, setPasswordEditConfirm] = useState(false);

  async function openProfile(goToSecurity) {
    try {
      const d = await api.get("/auth/perfil");
      setProfileData({ nombre_negocio: d.nombre_negocio ?? "", email: d.email ?? "", color_acento: d.color_acento ?? "#428dc7", tasa_cambio: d.tasa_cambio ?? 36.0, zona_horaria: d.zona_horaria || "America/Managua" });
      setProfileOpen(true);
      if (goToSecurity) setShowSecurity(true);
    } catch { setProfileOpen(true); if (goToSecurity) setShowSecurity(true); }
  }

  async function saveProfile() {
    if (!profileData.nombre_negocio.trim()) return;
    setSaving(true);
    try {
      await api.put("/auth/perfil", profileData);
      updateNegocio(profileData.nombre_negocio);
      const emailCambio = profileData.email !== user?.email;
      updateUser({ email: profileData.email, email_verified: false, tasa_cambio: profileData.tasa_cambio, tasa_cambio_configurada: true, zona_horaria: profileData.zona_horaria });
      setProfileOpen(false);
      toast("Perfil actualizado correctamente");
      if (emailCambio && profileData.email) {
        setOtpOpen(true);
        setOtpCodigo("");
        api.post("/auth/enviar-verificacion").then(res => {
          if (res.codigo_dev) setOtpCodigo(res.codigo_dev);
        }).catch(() => {});
      }
    } catch(e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  async function verifyOtp() {
    if (otpCodigo.length !== 6) return;
    setOtpLoading(true);
    try {
      await api.post("/auth/verificar-codigo", { codigo: otpCodigo });
      updateUser({ email_verified: true });
      setOtpOpen(false);
      setOtpCodigo("");
      toast("Correo verificado exitosamente");
    } catch (e) { toast(e.message, "error"); }
    finally { setOtpLoading(false); }
  }

  async function resendOtp() {
    try {
      const res = await api.post("/auth/enviar-verificacion");
      toast(res.mensaje);
      if (res.codigo_dev) {
        setOtpCodigo(res.codigo_dev);
        toast("Código de desarrollo: " + res.codigo_dev, "info");
      }
    } catch (e) { toast(e.message, "error"); }
  }

  async function handleEmailChange() {
    if (!nuevoEmail.trim()) return;
    setSaving(true);
    try {
      await api.put("/auth/perfil", { ...profileData, email: nuevoEmail });
      updateNegocio(profileData.nombre_negocio);
      updateUser({ email: nuevoEmail, email_verified: false });
      setEmailEditConfirm(false);
      setNuevoEmail("");
      setShowSecurity(false);
      setProfileOpen(false);
      toast("Correo actualizado correctamente");
      setOtpOpen(true);
      setOtpCodigo("");
      api.post("/auth/enviar-verificacion").then(res => {
        if (res.codigo_dev) setOtpCodigo(res.codigo_dev);
      }).catch(() => {});
    } catch(e) { toast(e.message, "error"); }
    finally { setSaving(false); }
  }

  async function changePassword() {
    if (!passwordData.password_actual || !passwordData.password_nuevo) return;
    setChangingPassword(true);
    try {
      await api.put("/auth/password", passwordData);
      toast("Contraseña actualizada correctamente");
      setPasswordData({ password_actual: "", password_nuevo: "" });
      setPasswordEditConfirm(false);
      setShowSecurity(false);
    } catch (e) { toast(e.message, "error"); }
    finally { setChangingPassword(false); }
  }

  async function deleteAccount() {
    if (!user?.provider && !deletePassword) return;
    setDeleting(true);
    try {
      await api.delete("/auth/cuenta", { password: deletePassword || "" });
      toast("Cuenta eliminada");
      logout();
      navigate("/");
    } catch (e) { toast(e.message, "error"); }
    finally { setDeleting(false); }
  }

  function handleLogout() {
    logout();
    navigate("/");
  }

  function toggleSidebarCollapse() {
    setSidebarCollapsed(p => {
      const next = !p;
      localStorage.setItem("sidebarCollapsed", next);
      return next;
    });
  }

  const sidebar = (
    <div className="flex flex-col h-full bg-surface-card border-r border-border">
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-500 to-secondary-500 flex items-center justify-center font-bold text-white text-sm shadow-glow-sm shrink-0 ring-1 ring-white/20">
          BG
        </div>
        {!sidebarCollapsed && (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-content truncate">{user?.nombre_negocio || "Mi Negocio"}</p>
            <p className="text-xs text-content-muted truncate">{user?.email || `@${user?.usuario}`}</p>
          </div>
        )}
        <button onClick={toggleSidebarCollapse}
          className="shrink-0 text-content-muted hover:text-content transition-colors p-1 rounded-lg hover:bg-surface-hover hidden lg:block">
          {sidebarCollapsed ? <Menu size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center ${sidebarCollapsed ? 'justify-center px-0 mx-auto w-10' : 'gap-3 px-3.5'} py-2.5 rounded-2xl text-sm font-medium transition-all duration-200 group ` +
              (isActive
                ? "bg-brand-500/[0.08] text-brand-500 dark:text-brand-400 font-semibold"
                : "text-content-muted hover:text-content hover:bg-surface-hover hover:scale-[1.02]")
            }
          >
            <Icon size={18} className="shrink-0" />
            {!sidebarCollapsed && <span>{label}</span>}
            {!sidebarCollapsed && <ChevronRight size={14} className="ml-auto opacity-0 group-hover:opacity-40 transition-all duration-200 -translate-x-2 group-hover:translate-x-0" />}
          </NavLink>
        ))}
      </nav>

      {/* Theme toggle + bottom */}
      <div className={`px-3 py-4 border-t border-border ${sidebarCollapsed ? 'flex flex-col items-center' : 'space-y-1'}`}>
        <button onClick={cycleTheme}
          className={`flex items-center rounded-2xl text-sm font-medium transition-all duration-200 w-full ${sidebarCollapsed ? 'justify-center px-0 py-2.5 w-10 text-content-muted hover:text-content hover:bg-surface-hover' : 'gap-3 px-3.5 py-2.5 text-content-muted hover:text-content hover:bg-surface-hover'}`}
          title={theme === "system" ? "Tema del sistema" : theme === "dark" ? "Modo oscuro" : "Modo claro"}>
          {theme === "system" ? <Monitor size={18} /> : dark ? <Sun size={18} /> : <Moon size={18} />}
          {!sidebarCollapsed && (theme === "system" ? "Tema sistema" : dark ? "Modo claro" : "Modo oscuro")}
        </button>
        <button onClick={() => openProfile()}
          className={`flex items-center rounded-2xl text-sm font-medium transition-all duration-200 w-full ${sidebarCollapsed ? 'justify-center px-0 py-2.5 w-10 text-content-muted hover:text-content hover:bg-surface-hover' : 'gap-3 px-3.5 py-2.5 text-content-muted hover:text-content hover:bg-surface-hover'}`}
          title="Configuración">
          <Settings size={18} />
          {!sidebarCollapsed && "Configuración"}
        </button>
        <button onClick={handleLogout}
          className={`flex items-center rounded-2xl text-sm font-medium transition-all duration-200 w-full ${sidebarCollapsed ? 'justify-center px-0 py-2.5 w-10 text-red-400 hover:text-red-300 hover:bg-red-900/15' : 'gap-3 px-3.5 py-2.5 text-red-400 hover:text-red-300 hover:bg-red-900/15'}`}
          title="Cerrar sesión">
          <LogOut size={18} />
          {!sidebarCollapsed && "Cerrar sesión"}
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      <aside className={`hidden lg:flex flex-col ${sidebarCollapsed ? 'w-16' : 'w-64'} shrink-0 transition-all duration-200`}>{sidebar}</aside>

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-72 bg-surface-card z-50 flex flex-col animate-slide-up">
            <button onClick={() => setSidebarOpen(false)} className="absolute top-4 right-4 text-content-muted hover:text-content transition-colors">
              <X size={20} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center gap-3 px-4 py-3 bg-surface-card border-b border-border">
          <button onClick={() => setSidebarOpen(true)} className="lg:hidden text-content-muted hover:text-content transition-colors">
            <Menu size={22} />
          </button>
          <button onClick={toggleSidebarCollapse} className="hidden lg:block text-content-muted hover:text-content transition-colors">
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-content">{user?.nombre_negocio || "Bravo's Gest"}</span>
        </header>

        <main className="flex-1 overflow-y-auto p-5 lg:p-8">
          {user && !dismissEmailAlert && (
            !user.email ? (
              <div className="mb-5 p-4 rounded-xl bg-accent-500/5 border border-accent-500/20 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-accent-400"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-content">Completa tu perfil</p>
                  <p className="text-xs text-content-muted mt-0.5">Agrega tu correo electrónico en Configuración para recibir notificaciones y mantener tus datos actualizados.</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => openProfile(true)}
                    className="text-xs font-medium text-accent-400 hover:text-accent-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-accent-500/10">
                    Configurar
                  </button>
                  <button onClick={() => { setDismissEmailAlert(true); sessionStorage.setItem("dismissEmailAlert", "true"); }}
                    className="text-content-muted hover:text-content transition-colors p-1">
                    <X size={15} />
                  </button>
                </div>
              </div>
            ) : !user.email_verified ? (
              <div className="mb-5 p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-amber-500/15 flex items-center justify-center shrink-0 mt-0.5">
                  <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber-400"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                </div>
                <div className="flex-1">
                  <p className="text-sm font-semibold text-content">Verifica tu correo</p>
                  <p className="text-xs text-content-muted mt-0.5">Revisa tu bandeja de entrada e ingresa el código de 6 dígitos.</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => { setOtpOpen(true); setOtpCodigo(""); }}
                    className="text-xs font-medium text-amber-400 hover:text-amber-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-amber-500/10">
                    Ingresar código
                  </button>
                  <button onClick={() => { setDismissEmailAlert(true); sessionStorage.setItem("dismissEmailAlert", "true"); }}
                    className="text-content-muted hover:text-content transition-colors p-1">
                    <X size={15} />
                  </button>
                </div>
              </div>
            ) : null
          )}
          {children}
        </main>
      </div>

      <Modal title="Verificar correo" open={otpOpen} onClose={() => setOtpOpen(false)}>
        <div className="space-y-5 text-center">
          <p className="text-sm text-content-muted">
            Hemos enviado un código de 6 dígitos a <strong className="text-content">{user?.email}</strong>
          </p>
          <div>
            <input className="input text-center text-2xl tracking-[8px] font-mono max-w-[200px] mx-auto"
              type="text" maxLength={6} placeholder="000000"
              value={otpCodigo}
              onChange={e => setOtpCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))} />
          </div>
          <button className="btn-primary w-full" onClick={verifyOtp} disabled={otpLoading || otpCodigo.length !== 6}>
            {otpLoading ? "Verificando..." : "Verificar código"}
          </button>
          <button onClick={resendOtp}
            className="text-sm text-accent-400 hover:text-accent-300 transition-colors">
            ¿No recibiste el código? Reenviar
          </button>
        </div>
      </Modal>

      <Modal title="Configuración" open={profileOpen} onClose={() => { setProfileOpen(false); setShowSecurity(false); setDeleteConfirm(false); setEmailEditConfirm(false); setNuevoEmail(""); setPasswordEditConfirm(false); }}>
        {!showSecurity ? (
          <div className="space-y-5">
            <div>
              <label className="label">Nombre del negocio</label>
              <input className="input" value={profileData.nombre_negocio}
                onChange={e => setProfileData(d => ({ ...d, nombre_negocio: e.target.value }))} />
            </div>
            <div>
              <label className="label">Color de acento</label>
              <div className="flex items-center gap-3">
                <input type="color" className="w-11 h-11 rounded-xl cursor-pointer border border-border bg-transparent"
                  value={profileData.color_acento}
                  onChange={e => setProfileData(d => ({ ...d, color_acento: e.target.value }))} />
                <span className="text-sm text-content-muted font-mono">{profileData.color_acento}</span>
              </div>
            </div>
            <div>
              <label className="label">Tasa de cambio (C$ por USD)</label>
              <input className="input" type="number" min="1" step="0.01" value={profileData.tasa_cambio}
                onChange={e => setProfileData(d => ({ ...d, tasa_cambio: Number(e.target.value) }))} />
              <p className="text-xs text-content-subtle mt-1">Usada para referencia en precios en dólares</p>
            </div>
            <div>
              <label className="label">Zona horaria</label>
              <select className="input" value={profileData.zona_horaria}
                onChange={e => setProfileData(d => ({ ...d, zona_horaria: e.target.value }))}>
                {ZONAS.map(z => <option key={z} value={z}>{z.replace(/_/g, " ").replace(/\//g, " / ")}</option>)}
              </select>
            </div>
            <div className="flex items-center justify-between pt-2 border-t border-border">
              <button onClick={() => setShowSecurity(true)}
                className="text-sm text-content-muted hover:text-content transition-colors flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-surface-hover">
                <Lock size={15} />
                Seguridad
              </button>
              <div className="flex gap-3">
                <button className="btn-secondary" onClick={() => setProfileOpen(false)}>Cancelar</button>
                <button className="btn-primary" onClick={saveProfile} disabled={saving}>
                  {saving ? "Guardando..." : "Guardar cambios"}
                </button>
              </div>
            </div>
          </div>
        ) : !deleteConfirm ? (
          <div className="space-y-6">
            <button onClick={() => setShowSecurity(false)}
              className="text-sm text-content-muted hover:text-content transition-colors flex items-center gap-1.5 mb-2">
              <ChevronLeft size={15} />
              Volver
            </button>

            {/* Tarjeta 1 — Correo electrónico */}
            <div className="p-4 rounded-xl bg-surface border border-border">
              <h4 className="text-sm font-semibold text-content flex items-center gap-2 mb-3">
                <Lock size={16} className="text-accent-400" />
                Correo electrónico
              </h4>
              {!emailEditConfirm ? (
                <div className="flex items-center justify-between">
                  <p className="text-sm text-content">{user?.email || <span className="text-content-muted">No configurado</span>}</p>
                  <button onClick={() => setEmailEditConfirm(true)}
                    className="text-xs font-medium text-accent-400 hover:text-accent-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-accent-500/10">
                    Cambiar correo
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-content-muted">¿Estás seguro de que deseas cambiar tu correo?</p>
                  <div className="flex gap-2">
                    <input className="input flex-1" type="email" placeholder="Nuevo correo electrónico"
                      value={nuevoEmail}
                      onChange={e => setNuevoEmail(e.target.value)} />
                    <button className="btn-primary shrink-0" onClick={handleEmailChange}
                      disabled={saving || !nuevoEmail.trim()}>
                      {saving ? "Guardando..." : "Guardar correo"}
                    </button>
                    <button className="btn-secondary shrink-0" onClick={() => { setEmailEditConfirm(false); setNuevoEmail(""); }}>
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Tarjeta 2 — Contraseña */}
            <div className="p-4 rounded-xl bg-surface border border-border">
              <h4 className="text-sm font-semibold text-content flex items-center gap-2 mb-3">
                <Lock size={16} className="text-accent-400" />
                Contraseña
              </h4>
              {!passwordEditConfirm ? (
                <button onClick={() => setPasswordEditConfirm(true)}
                  className="text-xs font-medium text-accent-400 hover:text-accent-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-accent-500/10">
                  Cambiar contraseña
                </button>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-content-muted">¿Estás seguro de que deseas cambiar tu contraseña?</p>
                  <div>
                    <label className="label">Contraseña actual</label>
                    <input className="input" type="password"
                      value={passwordData.password_actual}
                      onChange={e => setPasswordData(d => ({ ...d, password_actual: e.target.value }))} />
                  </div>
                  <div>
                    <label className="label">Nueva contraseña</label>
                    <input className="input" type="password"
                      value={passwordData.password_nuevo}
                      onChange={e => setPasswordData(d => ({ ...d, password_nuevo: e.target.value }))} />
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-primary" onClick={changePassword} disabled={changingPassword}>
                      {changingPassword ? "Cambiando..." : "Cambiar"}
                    </button>
                    <button className="btn-secondary" onClick={() => { setPasswordEditConfirm(false); setPasswordData({ password_actual: "", password_nuevo: "" }); }}>
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Tarjeta 3 — Zona de peligro */}
            <div className="p-4 rounded-xl bg-red-500/5 border border-red-500/20">
              <h4 className="text-sm font-semibold text-red-400 flex items-center gap-2 mb-2">
                <Trash2 size={16} />
                Zona de peligro
              </h4>
              <p className="text-xs text-content-muted mb-3">Eliminará permanentemente tu cuenta y todos los datos asociados (productos, clientes, ventas, etc.). Esta acción no se puede deshacer.</p>
              <button onClick={() => setDeleteConfirm(true)}
                className="text-sm font-medium text-red-400 hover:text-red-300 transition-colors px-3 py-1.5 rounded-lg hover:bg-red-500/10">
                Eliminar cuenta
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            <button onClick={() => setDeleteConfirm(false)}
              className="text-sm text-content-muted hover:text-content transition-colors flex items-center gap-1.5 mb-2">
              <ChevronLeft size={15} />
              Volver
            </button>

            <div className="flex items-center gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30">
              <AlertTriangle size={24} className="text-red-400 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-content">¿Estás seguro?</p>
                <p className="text-xs text-content-muted mt-0.5">Se eliminarán todos tus datos de forma permanente.</p>
              </div>
            </div>
            {user?.provider === "google" ? (
              <p className="text-sm text-content-muted">No se requiere contraseña para cuentas de Google.</p>
            ) : (
              <div>
                <label className="label">Ingresa tu contraseña para confirmar</label>
                <input className="input" type="password"
                  value={deletePassword}
                  onChange={e => setDeletePassword(e.target.value)} />
              </div>
            )}
            <div className="flex gap-3">
              <button className="btn-secondary flex-1" onClick={() => setDeleteConfirm(false)}>Cancelar</button>
              <button className="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                onClick={deleteAccount} disabled={deleting || (!user?.provider && !deletePassword)}>
                {deleting ? "Eliminando..." : "Eliminar cuenta"}
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
