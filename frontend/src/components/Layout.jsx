import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import Modal from "./Modal";
import {
  LayoutDashboard, Package, ShoppingCart, Users, FolderOpen,
  LogOut, Menu, X, Settings, ChevronRight
} from "lucide-react";

const NAV = [
  { to: "/dashboard",    icon: LayoutDashboard, label: "Dashboard" },
  { to: "/inventario",   icon: Package,         label: "Inventario" },
  { to: "/ventas",       icon: ShoppingCart,    label: "Ventas" },
  { to: "/clientes",     icon: Users,           label: "Clientes" },
  { to: "/organizacion", icon: FolderOpen,      label: "Organización" },
];

export default function Layout({ children }) {
  const { user, logout, updateNegocio } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileData, setProfileData] = useState({ nombre_negocio: "", color_acento: "#16a34a" });
  const [saving, setSaving] = useState(false);

  async function openProfile() {
    try {
      const d = await api.get("/auth/perfil");
      setProfileData({ nombre_negocio: d.nombre_negocio ?? "", color_acento: d.color_acento ?? "#16a34a" });
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
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 px-5 py-5 border-b border-gray-800">
        <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center font-bold text-white text-sm shrink-0">BG</div>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-gray-100 truncate">{user?.nombre_negocio || "Mi Negocio"}</p>
          <p className="text-xs text-gray-500 truncate">{user?.usuario}</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group ` +
              (isActive
                ? "bg-brand-600/20 text-brand-400 border border-brand-600/30"
                : "text-gray-400 hover:text-gray-100 hover:bg-gray-800")
            }
          >
            <Icon size={18} className="shrink-0" />
            <span>{label}</span>
            <ChevronRight size={14} className="ml-auto opacity-0 group-hover:opacity-50 transition-opacity" />
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-gray-800 space-y-1">
        <button onClick={openProfile}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-gray-400 hover:text-gray-100 hover:bg-gray-800 w-full transition-colors">
          <Settings size={18} />
          Configuración
        </button>
        <button onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-red-400 hover:text-red-300 hover:bg-red-900/20 w-full transition-colors">
          <LogOut size={18} />
          Cerrar sesión
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex flex-col w-60 bg-gray-900 border-r border-gray-800 shrink-0">
        {sidebar}
      </aside>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60" onClick={() => setSidebarOpen(false)} />
          <aside className="relative w-64 bg-gray-900 border-r border-gray-800 z-50 flex flex-col">
            <button onClick={() => setSidebarOpen(false)} className="absolute top-4 right-4 text-gray-400 hover:text-white">
              <X size={20} />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile topbar */}
        <header className="lg:hidden flex items-center gap-3 px-4 py-3 bg-gray-900 border-b border-gray-800">
          <button onClick={() => setSidebarOpen(true)} className="text-gray-400 hover:text-white">
            <Menu size={22} />
          </button>
          <span className="text-sm font-semibold text-gray-100">{user?.nombre_negocio || "Bravo's Gest"}</span>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          {children}
        </main>
      </div>

      {/* Profile Modal */}
      <Modal title="Configuración del negocio" open={profileOpen} onClose={() => setProfileOpen(false)}>
        <div className="space-y-4">
          <div>
            <label className="label">Nombre del negocio</label>
            <input className="input" value={profileData.nombre_negocio}
              onChange={e => setProfileData(d => ({ ...d, nombre_negocio: e.target.value }))} />
          </div>
          <div>
            <label className="label">Color de acento</label>
            <input type="color" className="w-10 h-10 rounded cursor-pointer border border-gray-700 bg-transparent"
              value={profileData.color_acento}
              onChange={e => setProfileData(d => ({ ...d, color_acento: e.target.value }))} />
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
