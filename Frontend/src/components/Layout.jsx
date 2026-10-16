import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Bot, ChevronLeft, FolderOpen, LayoutDashboard, LogOut, Mail,
  Menu, Monitor, Moon, Package, Settings, ShoppingCart, Sun,
  Tag, Users, X, AlertTriangle,
} from "lucide-react";

import SettingsModal from "./SettingsModal";
import { IconButton } from "./ui/Button";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useTheme } from "../hooks/useTheme";
import { EVENTO_SESION_EXPIRADA } from "../lib/api";
import { aplicarColorAcento } from "../lib/color";

const NAV = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/inventario", icon: Package, label: "Inventario" },
  { to: "/ventas", icon: ShoppingCart, label: "Ventas" },
  { to: "/clientes", icon: Users, label: "Clientes" },
  { to: "/promociones", icon: Tag, label: "Promociones" },
  { to: "/gesti", icon: Bot, label: "Gesti IA" },
  { to: "/organizacion", icon: FolderOpen, label: "Organización" },
];

const TEMA_ETIQUETA = { system: "Tema del sistema", dark: "Modo oscuro", light: "Modo claro" };
const TEMA_ICONO = { system: Monitor, dark: Moon, light: Sun };

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { toast } = useToast();
  const [, tema, ciclarTema] = useTheme();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [colapsado, setColapsado] = useState(
    () => localStorage.getItem("sidebarCollapsed") === "true"
  );
  const [ajustesAbierto, setAjustesAbierto] = useState(false);
  const [ajustesSeccion, setAjustesSeccion] = useState("perfil");
  const [alertaCorreoOculta, setAlertaCorreoOculta] = useState(
    () => sessionStorage.getItem("ocultarAlertaCorreo") === "true"
  );

  const titulo = useMemo(
    () => NAV.find((n) => pathname.startsWith(n.to))?.label ?? "Bravo's Gest",
    [pathname]
  );

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(colapsado));
  }, [colapsado]);

  // Drawer móvil: se cierra con Escape y al cambiar de ruta.
  useEffect(() => {
    if (!drawerAbierto) return;
    const alPresionar = (e) => e.key === "Escape" && setDrawerAbierto(false);
    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [drawerAbierto]);

  useEffect(() => setDrawerAbierto(false), [pathname]);

  // El color de acento vive en sessionStorage: se reaplica al montar.
  useEffect(() => {
    const color = sessionStorage.getItem("color_acento");
    if (color) aplicarColorAcento(color);
  }, []);

  // El backend ahora puede invalidar tokens (cambio de contraseña, cuenta
  // borrada); la API avisa por evento y aquí se cierra la sesión con aviso.
  useEffect(() => {
    function alExpirar() {
      logout();
      toast("Tu sesión expiró. Inicia sesión de nuevo.", "info");
      navigate("/", { replace: true });
    }
    window.addEventListener(EVENTO_SESION_EXPIRADA, alExpirar);
    return () => window.removeEventListener(EVENTO_SESION_EXPIRADA, alExpirar);
  }, [logout, navigate, toast]);

  const abrirAjustes = useCallback((seccion = "perfil") => {
    setAjustesSeccion(seccion);
    setAjustesAbierto(true);
  }, []);

  function cerrarSesion() {
    logout();
    navigate("/", { replace: true });
  }

  const IconoTema = TEMA_ICONO[tema] ?? Monitor;

  const sidebar = (
    <div className="flex flex-col h-full bg-surface-card border-r border-border">
      {/* Cabecera del sidebar */}
      <div className={`flex items-center gap-3 border-b border-border h-16 shrink-0 ${colapsado ? "justify-center px-2" : "px-4"}`}>
        <div
          className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center font-bold text-sm shrink-0 shadow-glow-sm"
          style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
          aria-hidden="true"
        >
          {user?.nombre_negocio?.slice(0, 2).toUpperCase() || "BG"}
        </div>
        {!colapsado && (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-content truncate">
              {user?.nombre_negocio || "Mi Negocio"}
            </p>
            <p className="text-xs text-content-subtle truncate">
              {user?.email || `@${user?.usuario}`}
            </p>
          </div>
        )}
        {!colapsado && (
          <IconButton
            label="Contraer menú"
            icon={ChevronLeft}
            onClick={() => setColapsado(true)}
            className="hidden lg:inline-flex shrink-0"
          />
        )}
      </div>

      {/* Navegación */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-4 space-y-0.5" aria-label="Navegación principal">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            title={colapsado ? label : undefined}
            className={({ isActive }) =>
              `nav-item ${isActive ? "nav-item-active" : "nav-item-idle"} ${
                colapsado ? "justify-center px-0" : ""
              }`
            }
          >
            <Icon size={18} className="shrink-0" aria-hidden="true" />
            {!colapsado && <span className="truncate">{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Pie del sidebar */}
      <div className={`border-t border-border py-3 shrink-0 ${colapsado ? "px-2 space-y-0.5" : "px-2.5 space-y-0.5"}`}>
        <button
          type="button"
          onClick={ciclarTema}
          title={colapsado ? TEMA_ETIQUETA[tema] : undefined}
          className={`nav-item nav-item-idle w-full ${colapsado ? "justify-center px-0" : ""}`}
        >
          <IconoTema size={18} className="shrink-0" aria-hidden="true" />
          {!colapsado && <span>{TEMA_ETIQUETA[tema]}</span>}
        </button>

        <button
          type="button"
          onClick={() => abrirAjustes("perfil")}
          title={colapsado ? "Configuración" : undefined}
          className={`nav-item nav-item-idle w-full ${colapsado ? "justify-center px-0" : ""}`}
        >
          <Settings size={18} className="shrink-0" aria-hidden="true" />
          {!colapsado && <span>Configuración</span>}
        </button>

        <button
          type="button"
          onClick={cerrarSesion}
          title={colapsado ? "Cerrar sesión" : undefined}
          className={`nav-item w-full text-content-muted hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 ${
            colapsado ? "justify-center px-0" : ""
          }`}
        >
          <LogOut size={18} className="shrink-0" aria-hidden="true" />
          {!colapsado && <span>Cerrar sesión</span>}
        </button>

        {colapsado && (
          <IconButton
            label="Expandir menú"
            icon={Menu}
            onClick={() => setColapsado(false)}
            className="hidden lg:inline-flex mx-auto"
          />
        )}
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-surface overflow-hidden">
      {/* Sidebar fijo en escritorio */}
      <aside
        className={`hidden lg:flex flex-col shrink-0 transition-[width] duration-200 ${
          colapsado ? "w-16" : "w-64"
        }`}
      >
        {sidebar}
      </aside>

      {/* Drawer en móvil */}
      <div
        className={`lg:hidden fixed inset-0 z-40 ${drawerAbierto ? "" : "pointer-events-none"}`}
        aria-hidden={!drawerAbierto}
      >
        <div
          className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${
            drawerAbierto ? "opacity-100" : "opacity-0"
          }`}
          onClick={() => setDrawerAbierto(false)}
        />
        <aside
          className={`absolute left-0 top-0 h-full w-72 max-w-[85vw] shadow-lg
                      transition-transform duration-250 ease-out ${
                        drawerAbierto ? "translate-x-0" : "-translate-x-full"
                      }`}
          role="dialog"
          aria-modal={drawerAbierto || undefined}
          aria-label="Menú de navegación"
        >
          <IconButton
            label="Cerrar menú"
            icon={X}
            size={18}
            onClick={() => setDrawerAbierto(false)}
            className="absolute top-4 right-3 z-10"
          />
          {sidebar}
        </aside>
      </div>

      {/* Contenido */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center gap-3 px-4 sm:px-6 h-16 bg-surface-card border-b border-border shrink-0">
          <IconButton
            label="Abrir menú"
            icon={Menu}
            size={20}
            onClick={() => setDrawerAbierto(true)}
            className="lg:hidden"
          />

          <h1 className="text-sm font-semibold text-content truncate">{titulo}</h1>

          <div className="ml-auto flex items-center gap-2">
            <IconButton
              label={TEMA_ETIQUETA[tema]}
              icon={IconoTema}
              size={17}
              onClick={ciclarTema}
            />
            <button
              type="button"
              onClick={() => abrirAjustes("perfil")}
              className="flex items-center gap-2 pl-2 pr-3 py-1.5 rounded-lg hover:bg-surface-hover transition-colors"
              aria-label="Abrir configuración de la cuenta"
            >
              <span
                className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center text-xs font-semibold"
                style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
                aria-hidden="true"
              >
                {user?.usuario?.slice(0, 1).toUpperCase() || "?"}
              </span>
              <span className="hidden sm:block text-sm text-content-muted max-w-[10rem] truncate">
                {user?.usuario}
              </span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          {user && !alertaCorreoOculta && !user.email && (
            <AvisoCompletarPerfil
              onConfigurar={() => abrirAjustes("seguridad")}
              onCerrar={() => {
                setAlertaCorreoOculta(true);
                sessionStorage.setItem("ocultarAlertaCorreo", "true");
              }}
            />
          )}

          {user && !alertaCorreoOculta && user.email && !user.email_verified && (
            <AvisoVerificarCorreo
              onVerificar={() => abrirAjustes("seguridad")}
              onCerrar={() => {
                setAlertaCorreoOculta(true);
                sessionStorage.setItem("ocultarAlertaCorreo", "true");
              }}
            />
          )}

          {children}
        </main>
      </div>

      <SettingsModal
        open={ajustesAbierto}
        seccionInicial={ajustesSeccion}
        onClose={() => setAjustesAbierto(false)}
      />
    </div>
  );
}

function Aviso({ icon: Icon, titulo, texto, accionLabel, onAccion, onCerrar, tono }) {
  const clases =
    tono === "amber"
      ? "bg-accent-500/5 border-accent-500/25 text-accent-700 dark:text-accent-400"
      : "bg-brand-500/5 border-brand-500/25 text-brand-700 dark:text-brand-300";

  return (
    <div
      className={`mb-5 p-3.5 rounded-xl border flex items-start gap-3 ${clases}`}
      role="status"
    >
      <Icon size={17} className="shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-content">{titulo}</p>
        <p className="text-xs text-content-muted mt-0.5">{texto}</p>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <button type="button" onClick={onAccion} className="btn-ghost btn-sm">
          {accionLabel}
        </button>
        <IconButton label="Descartar aviso" icon={X} onClick={onCerrar} />
      </div>
    </div>
  );
}

function AvisoCompletarPerfil({ onConfigurar, onCerrar }) {
  return (
    <Aviso
      icon={Mail}
      tono="brand"
      titulo="Completa tu perfil"
      texto="Agrega tu correo para recibir avisos y poder recuperar el acceso a tu cuenta."
      accionLabel="Configurar"
      onAccion={onConfigurar}
      onCerrar={onCerrar}
    />
  );
}

function AvisoVerificarCorreo({ onVerificar, onCerrar }) {
  return (
    <Aviso
      icon={AlertTriangle}
      tono="amber"
      titulo="Verifica tu correo"
      texto="Revisa tu bandeja de entrada e ingresa el código de 6 dígitos."
      accionLabel="Verificar"
      onAccion={onVerificar}
      onCerrar={onCerrar}
    />
  );
}
