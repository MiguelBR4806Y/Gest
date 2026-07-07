import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Package, ChartBar as BarChart3, Users, Sparkles, Eye, EyeOff, Sun, Moon } from "lucide-react";

export default function LoginPage() {
  const { login, registro } = useAuth();
  const navigate = useNavigate();
  const [dark, setDark] = useState(() => localStorage.getItem("theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("theme", dark ? "dark" : "light");
  }, [dark]);
  const [mode, setMode] = useState("login");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({ usuario: "", password: "", nombre_negocio: "", tasa_cambio: 36 });

  function set(key, val) { setForm(f => ({ ...f, [key]: val })); setError(""); }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await login(form.usuario, form.password);
        navigate("/dashboard");
      } else {
        if (!form.nombre_negocio.trim()) { setError("El nombre del negocio es obligatorio"); setLoading(false); return; }
        await registro(form.usuario, form.password, form.nombre_negocio, Number(form.tasa_cambio));
        await login(form.usuario, form.password);
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const features = [
    { icon: Package,    title: "Inventario",  desc: "Control de stock en tiempo real con alertas de escasez automáticas." },
    { icon: BarChart3,  title: "Ventas",       desc: "Registra ventas, analiza métricas y proyecciones del negocio." },
    { icon: Users,      title: "Clientes",     desc: "Gestiona tu cartera, créditos e historial de compras." },
    { icon: Sparkles,   title: "Gesti IA", desc: "Consulta a Gesti sobre tu negocio y obtén análisis predictivos." },
  ];

  return (
    <div className="min-h-screen bg-surface flex relative">
      {/* Theme toggle */}
      <button onClick={() => setDark(v => !v)}
        className="fixed top-4 right-4 z-50 w-10 h-10 rounded-2xl bg-surface-card border border-border/60 flex items-center justify-center text-content-muted hover:text-content hover:border-content-subtle/30 hover:shadow-glow-sm transition-all duration-200"
        title={dark ? "Modo claro" : "Modo oscuro"}>
        {dark ? <Sun size={18} /> : <Moon size={18} />}
      </button>
      {/* Left panel */}
      <div className="hidden lg:flex flex-col flex-1 relative overflow-hidden px-16 py-14 justify-between">
        {/* Decorative gradient blobs */}
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-brand-500/5 blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-secondary-500/5 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-brand-500 to-secondary-500 flex items-center justify-center font-bold text-white shadow-glow-sm">BG</div>
            <span className="text-xl font-bold text-content">Bravo's Gest</span>
          </div>
          <h1 className="text-4xl font-bold text-content leading-tight mb-4">
            Gestiona tu negocio<br />de forma inteligente.
          </h1>
          <p className="text-content-muted text-lg leading-relaxed mb-14 max-w-lg">
            Inventario, ventas, clientes y análisis con Gesti — todo desde un solo lugar.
          </p>
          <div className="grid grid-cols-1 gap-5 max-w-md">
            {features.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-4 group">
                <div className="w-11 h-11 rounded-2xl bg-surface-card border border-border/60 flex items-center justify-center shrink-0 transition-all duration-200 group-hover:border-brand-500/30 group-hover:shadow-glow-sm">
                  <Icon size={18} className="text-brand-400 transition-colors duration-200" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-content">{title}</p>
                  <p className="text-sm text-content-muted">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs text-content-subtle relative">© 2026 Bravo's Gest. Todos los derechos reservados.</p>
      </div>

      {/* Right panel */}
      <div className="flex flex-col items-center justify-center w-full lg:w-[420px] shrink-0 px-8 py-12 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-brand-500/[0.03] to-transparent pointer-events-none" />

        <div className="flex items-center gap-3 mb-10 lg:hidden relative">
          <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-brand-500 to-secondary-500 flex items-center justify-center font-bold text-white text-sm">BG</div>
          <span className="text-lg font-bold text-content">Bravo's Gest</span>
        </div>

        <div className="w-full relative">
          <h2 className="text-2xl font-bold text-content mb-1">
            {mode === "login" ? "Bienvenido de vuelta" : "Crear una cuenta"}
          </h2>
          <p className="text-content-muted text-sm mb-8">
            {mode === "login" ? "Ingresa tus credenciales para continuar." : "Completa los datos para registrarte."}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <>
                <div>
                  <label className="label">Nombre del negocio</label>
                  <input className="input" placeholder="Ej: Tienda Los Andes"
                    value={form.nombre_negocio} onChange={e => set("nombre_negocio", e.target.value)} />
                </div>
                <div>
                  <label className="label">Tasa de cambio (C$ por USD $)</label>
                  <input className="input" type="number" min="1" step="0.01" placeholder="Ej: 36"
                    value={form.tasa_cambio} onChange={e => set("tasa_cambio", e.target.value)} />
                  <p className="text-xs text-content-subtle mt-1">Usada para convertir monedas a dólares automáticamente</p>
                </div>
              </>
            )}
            <div>
              <label className="label">Usuario</label>
              <input className="input" placeholder="tu_usuario" autoComplete="username"
                value={form.usuario} onChange={e => set("usuario", e.target.value)} />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <div className="relative">
                <input className="input pr-11" type={showPass ? "text" : "password"}
                  placeholder="••••••••" autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={form.password} onChange={e => set("password", e.target.value)} />
                <button type="button" onClick={() => setShowPass(v => !v)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-content-muted hover:text-content transition-colors">
                  {showPass ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-400 bg-red-900/15 border border-red-800/40 rounded-xl px-4 py-2.5">{error}</p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full py-3 text-base mt-3">
              {loading ? "Cargando..." : mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
            </button>
          </form>

          <p className="text-center text-sm text-content-muted mt-7">
            {mode === "login" ? "¿No tienes cuenta? " : "¿Ya tienes cuenta? "}
            <button onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); setForm({ usuario: "", password: "", nombre_negocio: "" }); }}
              className="text-brand-400 hover:text-brand-300 font-medium transition-colors">
              {mode === "login" ? "Regístrate" : "Inicia sesión"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
