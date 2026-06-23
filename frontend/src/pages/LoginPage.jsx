import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Package, ChartBar as BarChart3, Users, Sparkles, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const { login, registro } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState("login"); // login | register
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({ usuario: "", password: "", nombre_negocio: "" });

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
        await registro(form.usuario, form.password, form.nombre_negocio);
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
    { icon: Sparkles,   title: "IA integrada", desc: "Consulta a la IA sobre tu negocio y obtén análisis predictivos." },
  ];

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Left panel - features */}
      <div className="hidden lg:flex flex-col flex-1 bg-gradient-to-br from-gray-900 via-gray-950 to-gray-900 px-12 py-16 justify-between border-r border-gray-800">
        <div>
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center font-bold text-white">BG</div>
            <span className="text-xl font-bold text-gray-100">Bravo's Gest</span>
          </div>
          <h1 className="text-4xl font-bold text-gray-100 leading-tight mb-4">
            Gestiona tu negocio<br />de forma inteligente.
          </h1>
          <p className="text-gray-400 text-lg leading-relaxed mb-12">
            Inventario, ventas, clientes y análisis con IA — todo desde un solo lugar.
          </p>
          <div className="grid grid-cols-1 gap-5">
            {features.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center shrink-0">
                  <Icon size={18} className="text-brand-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-gray-200">{title}</p>
                  <p className="text-sm text-gray-500">{desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <p className="text-xs text-gray-600">© 2026 Bravo's Gest. Todos los derechos reservados.</p>
      </div>

      {/* Right panel - form */}
      <div className="flex flex-col items-center justify-center w-full lg:w-[420px] shrink-0 px-8 py-12">
        {/* Mobile logo */}
        <div className="flex items-center gap-3 mb-10 lg:hidden">
          <div className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center font-bold text-white text-sm">BG</div>
          <span className="text-lg font-bold text-gray-100">Bravo's Gest</span>
        </div>

        <div className="w-full">
          <h2 className="text-2xl font-bold text-gray-100 mb-1">
            {mode === "login" ? "Bienvenido de vuelta" : "Crear una cuenta"}
          </h2>
          <p className="text-gray-500 text-sm mb-8">
            {mode === "login" ? "Ingresa tus credenciales para continuar." : "Completa los datos para registrarte."}
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="label">Nombre del negocio</label>
                <input className="input" placeholder="Ej: Tienda Los Andes"
                  value={form.nombre_negocio} onChange={e => set("nombre_negocio", e.target.value)} />
              </div>
            )}
            <div>
              <label className="label">Usuario</label>
              <input className="input" placeholder="tu_usuario" autoComplete="username"
                value={form.usuario} onChange={e => set("usuario", e.target.value)} />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <div className="relative">
                <input className="input pr-10" type={showPass ? "text" : "password"}
                  placeholder="••••••••" autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={form.password} onChange={e => set("password", e.target.value)} />
                <button type="button" onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300">
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <p className="text-sm text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg px-3 py-2">{error}</p>
            )}

            <button type="submit" disabled={loading} className="btn-primary w-full py-2.5 text-base mt-2">
              {loading ? "Cargando..." : mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
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
