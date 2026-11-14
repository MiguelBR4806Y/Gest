import { Navigate, Route, Routes } from "react-router-dom";

import AuroraBackground from "./components/AuroraBackground";
import Layout from "./components/Layout";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ActividadPage from "./pages/ActividadPage";
import ClientesPage from "./pages/ClientesPage";
import ComprasPage from "./pages/ComprasPage";
import ContabilidadPage from "./pages/ContabilidadPage";
import DashboardPage from "./pages/DashboardPage";
import EmpleadosPage from "./pages/EmpleadosPage";
import GastosPage from "./pages/GastosPage";
import GestiPage from "./pages/GestiPage";
import InventarioPage from "./pages/InventarioPage";
import LoginPage from "./pages/LoginPage";
import OrganizacionPage from "./pages/OrganizacionPage";
import PromocionesPage from "./pages/PromocionesPage";
import ProveedoresPage from "./pages/ProveedoresPage";
import RentabilidadPage from "./pages/RentabilidadPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import VendedoresPage from "./pages/VendedoresPage";
import VentasPage from "./pages/VentasPage";

/** A dónde mandar a cada cuenta al entrar o tras un rechazo de permisos. */
export function rutaInicio(user) {
  const rol = user?.rol ?? "admin";
  if (rol === "admin") return "/dashboard";
  const modulos = user?.modulos ?? [];
  if (modulos.includes("ventas")) return "/ventas";
  if (modulos.includes("contabilidad")) return "/contabilidad";
  if (modulos.includes("rrhh")) return "/rrhh";
  return "/ventas";
}

function Cargando() {
  return (
    <div className="flex items-center justify-center h-screen bg-surface">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Cargando />;
  if (!user) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

/** Exige uno o varios módulos. El admin siempre pasa. */
function ModuloRoute({ modulo, children }) {
  const { user, loading, puede } = useAuth();
  if (loading) return <Cargando />;
  if (!user) return <Navigate to="/" replace />;

  const requeridos = Array.isArray(modulo) ? modulo : [modulo];
  if (!requeridos.some((m) => puede(m))) {
    return <Navigate to={rutaInicio(user)} replace />;
  }
  return <Layout>{children}</Layout>;
}

function AdminRoute({ children }) {
  const { user, loading, esAdmin } = useAuth();
  if (loading) return <Cargando />;
  if (!user) return <Navigate to="/" replace />;
  if (!esAdmin) return <Navigate to={rutaInicio(user)} replace />;
  return <Layout>{children}</Layout>;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to={rutaInicio(user)} replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/reset" element={<ResetPasswordPage />} />

      {/* Ventas */}
      <Route path="/ventas"     element={<ModuloRoute modulo="ventas"><VentasPage /></ModuloRoute>} />
      <Route path="/inventario" element={<ModuloRoute modulo={["ventas", "contabilidad"]}><InventarioPage /></ModuloRoute>} />
      <Route path="/clientes"   element={<ModuloRoute modulo={["ventas", "contabilidad"]}><ClientesPage /></ModuloRoute>} />

      {/* Contabilidad */}
      <Route path="/contabilidad" element={<ModuloRoute modulo="contabilidad"><ContabilidadPage /></ModuloRoute>} />
      <Route path="/gastos"       element={<ModuloRoute modulo="contabilidad"><GastosPage /></ModuloRoute>} />
      <Route path="/compras"      element={<ModuloRoute modulo="contabilidad"><ComprasPage /></ModuloRoute>} />
      <Route path="/proveedores"  element={<ModuloRoute modulo="contabilidad"><ProveedoresPage /></ModuloRoute>} />
      <Route path="/rentabilidad" element={<ModuloRoute modulo="contabilidad"><RentabilidadPage /></ModuloRoute>} />

      {/* RRHH */}
      <Route path="/rrhh"      element={<ModuloRoute modulo="rrhh"><EmpleadosPage /></ModuloRoute>} />
      <Route path="/empleados" element={<Navigate to="/rrhh" replace />} />

      {/* Solo el dueño del negocio */}
      <Route path="/dashboard"    element={<AdminRoute><DashboardPage /></AdminRoute>} />
      <Route path="/organizacion" element={<AdminRoute><OrganizacionPage /></AdminRoute>} />
      <Route path="/promociones"  element={<AdminRoute><PromocionesPage /></AdminRoute>} />
      <Route path="/gesti"        element={<AdminRoute><GestiPage /></AdminRoute>} />
      <Route path="/actividad"    element={<AdminRoute><ActividadPage /></AdminRoute>} />
      <Route path="/vendedores"   element={<AdminRoute><VendedoresPage /></AdminRoute>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuroraBackground>
        <AppRoutes />
      </AuroraBackground>
    </AuthProvider>
  );
}
