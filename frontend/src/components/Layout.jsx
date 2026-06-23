import { useState, useEffect } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import Modal from "./Modal";
import {
  LayoutDashboard, Package, ShoppingCart, Users, FolderOpen,
  LogOut, Menu, X, Settings, ChevronRight, Sun, Moon
} from "lucide-react";

const NAV = [
  { to: "/dashboard",    icon: LayoutDashboard, label: "Dashboard" },
  { to: "/inventario",   icon: Package,         label: "Inventario" },
  { to: "/ventas",       icon: ShoppingCart,    label: "Ventas" },
  { to: "/clientes",     icon: Users,           label: "Clientes" },
  { to: "/organizacion", icon: FolderOpen,      label: "Organización" },
];

function useTheme() {
  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem("theme");
    if (stored) return stored === "dark";
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);

  return [dark, () => setDark(d => !d)];
}

export default function Layout({ children }) {
  const { user, logout, updateNegocio } = useAuth();
  const [dark, toggleTheme] = useTheme();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState({ nombre_negocio: "", color_acento: "#428dc7" });
  const [saving, setSaving] = useState(false);

  async function openProfile() {
    try {
      const d = await api.get("/auth/perfil");
      setProfileData({ nombre_negocio: d.nombre_negocio ?? "", color_acento: d.color_acento ?? "#428dc7" });
      setProfileOpen(true);
    } catch { setProfileOpen(true); }
  }

  async function saveProfile() {
    if (!profileData.nombre_negocio.trim()) return;
    setSaving(true);
    try {
      await api.put("/auth/perfil", profileData);
      updateNegocio(profileData.nombre_negocio);
      setProfileOpen(false);
    } catch(e) { alert(e.message); }
    finally { setSaving(false); }
  }

  function handleLogout() {
    logout();
    navigate("/");
  }

  const sidebar = (
    <div className="flex flex-col h-full bg-surface-card border-r border-border">
      <div className="flex items-center gap-3 px-5 py-5 border-b border-border">
        <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-500 to-secondary-500 flex items-center justify-center font-bold text-white text-sm shadow-glow-sm shrink-0">
          BG
        </div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-content truncate">{user?.nombre_negocio || "Mi Negocio"}</p>
          <p className="text-xs text-content-muted truncate">@{user?.usuario}</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-5 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-sm font-medium transition-all duration-200 group ` +
              (isActive
                ? "bg-brand-500/15 text-brand-500 dark:text-brand-400 border border-brand-500/20 shadow-glow-sm"
                : "text-content-muted hover:text-content hover:bg-surface-hover")
            }
          >
            <Icon size={18} className="shrink-0" />
            <span>{label}</span>
            <ChevronRight size={14} className="ml-auto opacity-0 group-hover:opacity-40 transition-all duration-200 -translate-x-2 group-hover:translate-x-0" />
          </NavLink>
        ))}
      </nav>

      {/* Theme toggle + bottom */}
      <div className="px-3 py-4 border-t border-border space-y-1">
        <button onClick={toggleTheme}
          className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-sm font-medium text-content-muted hover:text-content hover:bg-surface-hover w-full transition-all duration-200">
          {dark ? <Sun size={18} /> : <Moon size={18} />}
          {dark ? "Modo claro" : "Modo oscuro"}
        </button>
        <button onClick={openProfile}
          className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-sm font-medium text-content-muted hover:text-content hover:bg-surface-hover w-full transition-all duration-200">
          <Settings size={18} />
          Configuración
        </button>
        <button onClick={handleLogout}
          className="flex items-center gap-3 px-3.5 py-2.5 rounded-2xl text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-900/15 w-full transition-all duration-200">
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      <aside className="hidden lg:flex flex-col w-64 shrink-0">{sidebar}</aside>

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
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-surface-card border-b border-border">
          <button onClick={() => setSidebarOpen(true)} className="text-content-muted hover:text-content transition-colors">
            <Menu size={22} />
          </button>
          <span className="text-sm font-semibold text-content">{user?.nombre_negocio || "Bravo's Gest"}</span>
        </header>

        <main className="flex-1 overflow-y-auto p-5 lg:p-8">{children}</main>
      </div>

      <Modal title="Configuración del negocio" open={profileOpen} onClose={() => setProfileOpen(false)}>
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
          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={() => setProfileOpen(false)}>Cancelar</button>
            <button className="btn-primary" onClick={saveProfile} disabled={saving}>
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
