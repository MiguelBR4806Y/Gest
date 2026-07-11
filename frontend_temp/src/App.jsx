import { Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Layout from "./components/Layout";
import AuroraBackground from "./components/AuroraBackground";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import InventarioPage from "./pages/InventarioPage";
import VentasPage from "./pages/VentasPage";
import ClientesPage from "./pages/ClientesPage";
import OrganizacionPage from "./pages/OrganizacionPage";
import PromocionesPage from "./pages/PromocionesPage";
import GestiPage from "./pages/GestiPage";


function PrivateRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return (
    <div className="flex items-center justify-center h-screen bg-surface">
      <div className="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!user) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/dashboard"    element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
      <Route path="/inventario"   element={<PrivateRoute><InventarioPage /></PrivateRoute>} />
      <Route path="/ventas"       element={<PrivateRoute><VentasPage /></PrivateRoute>} />
      <Route path="/clientes"     element={<PrivateRoute><ClientesPage /></PrivateRoute>} />
      <Route path="/organizacion" element={<PrivateRoute><OrganizacionPage /></PrivateRoute>} />
      <Route path="/promociones"  element={<PrivateRoute><PromocionesPage /></PrivateRoute>} />
      <Route path="/gesti"        element={<PrivateRoute><GestiPage /></PrivateRoute>} />
      <Route path="*"             element={<Navigate to="/" replace />} />
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
