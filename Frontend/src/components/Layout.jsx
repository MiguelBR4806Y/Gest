import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Activity, Bot, Calculator, ChevronDown, ChevronLeft, ChevronsRight, FolderOpen,
  LayoutDashboard, LogOut, Mail, Percent, Menu, Monitor, Moon, Package, Receipt,
  Settings, ShoppingCart, Sun, Truck, UserCog, Tag, Users, X, AlertTriangle, Wallet,
  UsersRound,
} from "lucide-react";

import SettingsModal from "./SettingsModal";
import { IconButton } from "./ui/Button";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useTheme } from "../hooks/useTheme";
import { EVENTO_SESION_EXPIRADA } from "../lib/api";
import { aplicarColorAcento } from "../lib/color";

const NAV = [
  {
    grupo: "Principal",
    items: [{ to: "/dashboard", icon: LayoutDashboard, label: "Dashboard", soloAdmin: true }],
  },
  {
    grupo: "Operación",
    modulo: "ventas",
    items: [
      { to: "/ventas", icon: ShoppingCart, label: "Ventas" },
      { to: "/inventario", icon: Package, label: "Inventario" },
      { to: "/clientes", icon: Users, label: "Clientes" },
      { to: "/promociones", icon: Tag, label: "Promociones", soloAdmin: true },
    ],
  },
  {
    grupo: "Contabilidad",
    modulo: "contabilidad",
    items: [
      { to: "/contabilidad", icon: Calculator, label: "Resumen" },
      { to: "/gastos", icon: Wallet, label: "Gastos" },
      { to: "/compras", icon: Receipt, label: "Compras" },
      { to: "/proveedores", icon: Truck, label: "Proveedores" },
      { to: "/rentabilidad", icon: Percent, label: "Rentabilidad" },
    ],
  },
  {
    grupo: "RRHH",
    modulo: "rrhh",
    items: [{ to: "/rrhh", icon: UsersRound, label: "Plantilla y nómina" }],
  },
  {
    grupo: "Análisis",
    soloAdmin: true,
    items: [
      { to: "/gesti", icon: Bot, label: "Gesti IA" },
      { to: "/actividad", icon: Activity, label: "Actividad" },
    ],
  },
  {
    grupo: "Documentos",
    soloAdmin: true,
    items: [{ to: "/organizacion", icon: FolderOpen, label: "Organización" }],
  },
  {
    grupo: "Administración",
    soloAdmin: true,
    items: [{ to: "/vendedores", icon: UserCog, label: "Vendedores" }],
  },
];

// Accesos del pulgar para móvil: el resto vive en el drawer.
const NAV_MOVIL = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Inicio", soloAdmin: true },
  { to: "/ventas", icon: ShoppingCart, label: "Ventas" },
  { to: "/inventario", icon: Package, label: "Stock" },
  { to: "/clientes", icon: Users, label: "Clientes" },
];

const TEMA_ETIQUETA = { system: "Tema del sistema", dark: "Modo oscuro", light: "Modo claro" };
const TEMA_ICONO = { system: Monitor, dark: Moon, light: Sun };

const CLAVE_GRUPOS = "navGruposAbiertos";

/** Grupos plegados: por defecto todos abiertos. */
function leerGruposCerrados() {
  try {
    const guardado = JSON.parse(localStorage.getItem(CLAVE_GRUPOS) || "[]");
    return new Set(Array.isArray(guardado) ? guardado : []);
  } catch {
    return new Set();
  }
}

export default function Layout({ children }) {
  const { user, esAdmin, puede, logout } = useAuth();
  const { toast } = useToast();
  const [, tema, ciclarTema] = useTheme();
  const navigate = useNavigate();
  const { pathname } = useLocation();

  // El vendedor solo ve Ventas e Inventario; contabilidad y RRHH aparecen si
  // la cuenta tiene el módulo. Lo que no se ve, el backend igual lo rechaza.
  const navVisible = useMemo(() => {
    const visible = (item) =>
      esAdmin || (item.modulo ? puede(item.modulo) : !item.soloAdmin);

    return NAV.filter((g) => esAdmin || !g.soloAdmin || (g.modulo && puede(g.modulo)))
      .map((g) => ({ ...g, items: g.items.filter(visible) }))
      .filter((g) => g.items.length > 0);
  }, [esAdmin, puede]);

  const navPlanoVisible = useMemo(() => navVisible.flatMap((g) => g.items), [navVisible]);
  const navMovilVisible = useMemo(
    () => NAV_MOVIL.filter((i) => esAdmin || !i.soloAdmin),
    [esAdmin]
  );
  const [drawerAbierto, setDrawerAbierto] = useState(false);
  const [colapsado, setColapsado] = useState(
    () => localStorage.getItem("sidebarCollapsed") === "true"
  );
  const [gruposCerrados, setGruposCerrados] = useState(leerGruposCerrados);
  const [ajustesAbierto, setAjustesAbierto] = useState(false);
  const [ajustesSeccion, setAjustesSeccion] = useState("perfil");
  const [alertaCorreoOculta, setAlertaCorreoOculta] = useState(
    () => sessionStorage.getItem("ocultarAlertaCorreo") === "true"
  );

  const titulo = useMemo(
    () => navPlanoVisible.find((n) => pathname.startsWith(n.to))?.label ?? "Bravo's Gest",
    [pathname, navPlanoVisible]
  );

  const fechaHoy = useMemo(
    () => new Date().toLocaleDateString("es-NI", {
      weekday: "long",
      day: "numeric",
      month: "long",
      timeZone: user?.zona_horaria || "America/Managua",
    }),
    [user?.zona_horaria]
  );

  useEffect(() => {
    localStorage.setItem("sidebarCollapsed", String(colapsado));
  }, [colapsado]);

  useEffect(() => {
    try {
      localStorage.setItem(CLAVE_GRUPOS, JSON.stringify([...gruposCerrados]));
    } catch {
      /* localStorage puede estar bloqueado */
    }
  }, [gruposCerrados]);

  // Cada grupo se abre y se cierra desde su cabecera. La ruta activa se
  // despliega sola para que el usuario siempre vea dónde está.
  const grupoDeRuta = useMemo(
    () => navVisible.find((g) => g.items.some((i) => pathname.startsWith(i.to)))?.grupo,
    [navVisible, pathname]
  );

  const alternarGrupo = useCallback((nombre) => {
    setGruposCerrados((actuales) => {
      const siguiente = new Set(actuales);
      if (siguiente.has(nombre)) siguiente.delete(nombre);
      else siguiente.add(nombre);
      return siguiente;
    });
  }, []);

  // Al navegar a otra sección, su grupo se despliega. Solo reacciona al cambio
  // de ruta: cerrar un grupo a mano no lo reabre.
  useEffect(() => {
    if (!grupoDeRuta) return;
    setGruposCerrados((actuales) => {
      if (!actuales.has(grupoDeRuta)) return actuales;
      const siguiente = new Set(actuales);
      siguiente.delete(grupoDeRuta);
      return siguiente;
    });
  }, [pathname, grupoDeRuta]);

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

  // `compacto` se pasa como argumento: el drawer móvil se dibuja siempre
  // expandido aunque el sidebar de escritorio esté contraído.
  const sidebar = (compacto) => (
    <div className="flex flex-col h-full bg-surface-card border-r border-border">
      {/* Cabecera del sidebar */}
      <div className={`flex items-center gap-3 border-b border-border h-16 shrink-0 ${compacto ? "justify-center px-2" : "px-4"}`}>
        <div
          className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center font-bold text-sm shrink-0 shadow-glow-sm"
          style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
          aria-hidden="true"
        >
          {user?.nombre_negocio?.slice(0, 2).toUpperCase() || "BG"}
        </div>
        {!compacto && (
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-content truncate">
              {user?.nombre_negocio || "Mi Negocio"}
            </p>
            <p className="text-xs text-content-subtle truncate">
              {user?.rol === "vendedor"
                ? `${user?.nombre || user?.usuario} · vendedor`
                : user?.email || `@${user?.usuario}`}
            </p>
          </div>
        )}
        {!compacto && (
          <IconButton
            label="Contraer menú"
            icon={ChevronLeft}
            onClick={() => setColapsado(true)}
            className="hidden lg:inline-flex shrink-0"
          />
        )}
      </div>

      {/* Navegación */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-4 space-y-2" aria-label="Navegación principal">
        {navVisible.map((grupo) => {
          const abierto = !gruposCerrados.has(grupo.grupo);
          const contieneRuta = grupoDeRuta === grupo.grupo;

          return (
            <div key={grupo.grupo}>
              {compacto ? (
                // Contraído no caben los títulos: separa los grupos con una línea.
                <div className="mx-2 mb-1.5 h-px bg-border/70" aria-hidden="true" />
              ) : (
                <button
                  type="button"
                  onClick={() => alternarGrupo(grupo.grupo)}
                  aria-expanded={abierto}
                  title={abierto ? `Ocultar ${grupo.grupo}` : `Mostrar ${grupo.grupo}`}
                  className={`group flex w-full items-center gap-1.5 rounded-md px-3 py-1.5
                              text-[10px] font-semibold uppercase tracking-[0.12em]
                              transition-colors hover:bg-surface-hover ${
                                contieneRuta && !abierto
                                  ? "text-brand-700 dark:text-brand-300"
                                  : "text-content-subtle hover:text-content-muted"
                              }`}
                >
                  <span className="flex-1 text-left">{grupo.grupo}</span>
                  <ChevronDown
                    size={12}
                    aria-hidden="true"
                    className={`shrink-0 transition-transform duration-200 ${
                      abierto ? "" : "-rotate-90"
                    }`}
                  />
                </button>
              )}

              <div hidden={!abierto && !compacto} className="space-y-0.5 pt-0.5">
                {grupo.items.map(({ to, icon: Icon, label }) => (
                  <NavLink
                    key={to}
                    to={to}
                    title={compacto ? label : undefined}
                    className={({ isActive }) =>
                      `nav-item ${isActive ? "nav-item-active" : "nav-item-idle"} ${
                        compacto ? "justify-center px-0" : ""
                      }`
                    }
                  >
                    <Icon size={18} className="shrink-0" aria-hidden="true" />
                    {!compacto && <span className="truncate">{label}</span>}
                  </NavLink>
                ))}
              </div>
            </div>
          );
        })}
      </nav>

      {/* Pie del sidebar */}
      <div className="border-t border-border py-3 shrink-0 px-2.5 space-y-0.5">
        <button
          type="button"
          onClick={ciclarTema}
          title={compacto ? TEMA_ETIQUETA[tema] : undefined}
          className={`nav-item nav-item-idle w-full ${compacto ? "justify-center px-0" : ""}`}
        >
          <IconoTema size={18} className="shrink-0" aria-hidden="true" />
          {!compacto && <span>{TEMA_ETIQUETA[tema]}</span>}
        </button>

        <button
          type="button"
          onClick={() => abrirAjustes("perfil")}
          title={compacto ? "Configuración" : undefined}
          className={`nav-item nav-item-idle w-full ${compacto ? "justify-center px-0" : ""}`}
        >
          <Settings size={18} className="shrink-0" aria-hidden="true" />
          {!compacto && <span>Configuración</span>}
        </button>

        <button
          type="button"
          onClick={cerrarSesion}
          title={compacto ? "Cerrar sesión" : undefined}
          className={`nav-item w-full text-content-muted hover:text-red-600 dark:hover:text-red-400 hover:bg-red-500/10 ${
            compacto ? "justify-center px-0" : ""
          }`}
        >
          <LogOut size={18} className="shrink-0" aria-hidden="true" />
          {!compacto && <span>Cerrar sesión</span>}
        </button>

        {compacto && (
          <button
            type="button"
            onClick={() => setColapsado(false)}
            title="Expandir menú"
            aria-label="Expandir menú"
            className="nav-item nav-item-idle w-full justify-center px-0 hidden lg:flex"
          >
            <ChevronsRight size={18} className="shrink-0" aria-hidden="true" />
          </button>
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
        {sidebar(colapsado)}
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
          {sidebar(false)}
        </aside>
      </div>

      {/* Contenido */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:top-3 focus:left-3 focus:rounded-lg focus:bg-surface-card focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-content focus:shadow-lg"
        >
          Saltar al contenido
        </a>
        <header className="flex items-center gap-3 px-4 sm:px-6 h-16 bg-surface-card border-b border-border shrink-0">
          <IconButton
            label="Abrir menú"
            icon={Menu}
            size={20}
            onClick={() => setDrawerAbierto(true)}
            className="lg:hidden"
          />

          <h1 className="text-sm font-semibold text-content truncate">{titulo}</h1>
          <span className="hidden md:block text-xs text-content-subtle capitalize truncate">
            {fechaHoy}
          </span>

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
                {user?.rol === "vendedor" && (
                  <span className="ml-1.5 text-[10px] uppercase tracking-wide text-content-subtle">
                    vendedor
                  </span>
                )}
              </span>
            </button>
          </div>
        </header>

        <main id="contenido" className="flex-1 overflow-y-auto p-4 pb-28 sm:p-6 sm:pb-28 lg:p-8 lg:pb-8">
          {esAdmin && user && !alertaCorreoOculta && !user.email && (
            <AvisoCompletarPerfil
              onConfigurar={() => abrirAjustes("seguridad")}
              onCerrar={() => {
                setAlertaCorreoOculta(true);
                sessionStorage.setItem("ocultarAlertaCorreo", "true");
              }}
            />
          )}

          {esAdmin && user && !alertaCorreoOculta && user.email && !user.email_verified && (
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

      <nav
        className="lg:hidden fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface-card/95 backdrop-blur-md"
        style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
        aria-label="Navegación rápida"
      >
        <div
          className="grid"
          style={{ gridTemplateColumns: `repeat(${navMovilVisible.length + 1}, minmax(0, 1fr))` }}
        >
          {navMovilVisible.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium transition-colors ${
                  isActive
                    ? "text-brand-700 dark:text-brand-300"
                    : "text-content-muted hover:text-content"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`flex h-8 w-8 items-center justify-center rounded-lg transition-colors ${
                      isActive ? "bg-brand-500/15" : ""
                    }`}
                  >
                    <Icon size={18} aria-hidden="true" />
                  </span>
                  {label}
                </>
              )}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={() => setDrawerAbierto(true)}
            className="flex flex-col items-center justify-center gap-1 py-2.5 text-[11px] font-medium text-content-muted hover:text-content transition-colors"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-lg">
              <Menu size={18} aria-hidden="true" />
            </span>
            Más
          </button>
        </div>
      </nav>

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
