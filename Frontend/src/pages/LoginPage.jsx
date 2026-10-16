import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Eye, EyeOff, Loader2, Moon, Package, ShoppingCart, Sparkles, Sun, Users,
} from "lucide-react";

import { Button } from "../components/ui/Button";
import { Field, Input } from "../components/ui/Field";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useTheme } from "../hooks/useTheme";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

const CARACTERISTICAS = [
  { icon: Package, titulo: "Inventario", texto: "Control de stock con alertas automáticas de escasez." },
  { icon: ShoppingCart, titulo: "Ventas", texto: "Registra ventas y consulta métricas y proyecciones." },
  { icon: Users, titulo: "Clientes", texto: "Cartera, créditos e historial de compras." },
  { icon: Sparkles, titulo: "Gesti IA", texto: "Pregúntale a Gesti sobre tu negocio en lenguaje natural." },
];

const FORM_INICIAL = {
  usuario: "",
  password: "",
  email: "",
  nombre_negocio: "",
  tasa_cambio: 36,
};

export default function LoginPage() {
  const { login, registro, googleLogin, user, loading: cargandoSesion } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [esOscuro, , ciclarTema] = useTheme();

  const [modo, setModo] = useState("login");
  const [form, setForm] = useState(FORM_INICIAL);
  const [verPassword, setVerPassword] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [googleListo, setGoogleListo] = useState(false);
  const refGoogle = useRef(null);

  useEffect(() => {
    if (!cargandoSesion && user) navigate("/dashboard", { replace: true });
  }, [user, cargandoSesion, navigate]);

  // Espera a que cargue el script de Google Identity Services.
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelado = false;
    (function esperar() {
      if (cancelado) return;
      if (window.google?.accounts?.id) setGoogleListo(true);
      else setTimeout(esperar, 200);
    })();
    return () => {
      cancelado = true;
    };
  }, []);

  useEffect(() => {
    if (!googleListo || !refGoogle.current) return;
    const contenedor = refGoogle.current;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async (respuesta) => {
        setEnviando(true);
        setError("");
        try {
          await googleLogin(respuesta.credential);
          navigate("/dashboard", { replace: true });
        } catch (e) {
          setError(e.message || "No se pudo iniciar sesión con Google");
        } finally {
          setEnviando(false);
        }
      },
    });

    window.google.accounts.id.renderButton(contenedor, {
      theme: esOscuro ? "filled_black" : "outline",
      size: "large",
      text: "continue_with",
      shape: "rectangular",
      width: Math.min(contenedor.offsetWidth || 320, 400),
    });
  }, [googleListo, esOscuro, googleLogin, navigate]);

  function set(campo, valor) {
    setForm((f) => ({ ...f, [campo]: valor }));
    if (error) setError("");
  }

  function cambiarModo() {
    setModo((m) => (m === "login" ? "register" : "login"));
    setError("");
    setForm(FORM_INICIAL);
  }

  async function alEnviar(e) {
    e.preventDefault();
    setError("");

    if (!form.usuario.trim() || !form.password) {
      setError("Completa usuario y contraseña");
      return;
    }
    if (modo === "register" && !form.nombre_negocio.trim()) {
      setError("El nombre del negocio es obligatorio");
      return;
    }

    setEnviando(true);
    try {
      if (modo === "login") {
        await login(form.usuario.trim(), form.password);
      } else {
        await registro(
          form.usuario.trim(),
          form.password,
          form.nombre_negocio.trim(),
          Number(form.tasa_cambio) || 36,
          form.email.trim()
        );
        await login(form.usuario.trim(), form.password);
      }
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex">
      <button
        type="button"
        onClick={ciclarTema}
        aria-label={esOscuro ? "Cambiar a modo claro" : "Cambiar a modo oscuro"}
        className="fixed top-4 right-4 z-50 btn-icon w-10 h-10 rounded-xl bg-surface-card
                   border border-border shadow-soft hover:shadow-md"
      >
        {esOscuro ? <Sun size={17} aria-hidden="true" /> : <Moon size={17} aria-hidden="true" />}
      </button>

      {/* Panel de presentación (solo escritorio) */}
      <aside className="hidden lg:flex flex-col flex-1 px-14 xl:px-20 py-14 justify-between border-r border-border">
        <div>
          <div className="flex items-center gap-3 mb-14">
            <div
              className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center font-bold shadow-glow-sm"
              style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
              aria-hidden="true"
            >
              BG
            </div>
            <span className="text-lg font-bold text-content">Bravo's Gest</span>
          </div>

          <h1 className="text-4xl xl:text-5xl font-bold text-content leading-[1.15] tracking-tight mb-4">
            Gestiona tu negocio
            <br />
            sin perder el control.
          </h1>
          <p className="text-content-muted text-base leading-relaxed mb-12 max-w-md">
            Inventario, ventas, clientes y facturación en un solo lugar, con Gesti analizando tus datos.
          </p>

          <ul className="grid gap-5 max-w-md">
            {CARACTERISTICAS.map(({ icon: Icon, titulo, texto }) => (
              <li key={titulo} className="flex items-start gap-3.5">
                <div className="w-9 h-9 rounded-lg bg-surface-elevated border border-border flex items-center justify-center shrink-0">
                  <Icon size={17} className="text-brand-600 dark:text-brand-300" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-content">{titulo}</p>
                  <p className="text-sm text-content-muted">{texto}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-xs text-content-subtle">
          © {new Date().getFullYear()} Bravo's Gest
        </p>
      </aside>

      {/* Formulario */}
      <div className="flex flex-col items-center justify-center w-full lg:w-[440px] shrink-0 px-6 sm:px-10 py-12">
        <div className="flex items-center gap-3 mb-9 lg:hidden">
          <div
            className="w-9 h-9 rounded-xl bg-brand-600 flex items-center justify-center font-bold text-sm"
            style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
            aria-hidden="true"
          >
            BG
          </div>
          <span className="text-lg font-bold text-content">Bravo's Gest</span>
        </div>

        <div className="w-full max-w-sm">
          <h2 className="text-2xl font-bold text-content tracking-tight">
            {modo === "login" ? "Bienvenido de vuelta" : "Crea tu cuenta"}
          </h2>
          <p className="text-sm text-content-muted mt-1.5 mb-7">
            {modo === "login"
              ? "Ingresa tus credenciales para continuar."
              : "Completa los datos para empezar."}
          </p>

          <form onSubmit={alEnviar} className="space-y-4" noValidate>
            {modo === "register" && (
              <>
                <Field label="Nombre del negocio" required>
                  <Input
                    value={form.nombre_negocio}
                    onChange={(e) => set("nombre_negocio", e.target.value)}
                    placeholder="Ej: Tienda Los Andes"
                    autoComplete="organization"
                    maxLength={120}
                  />
                </Field>

                <Field label="Correo electrónico" hint="Opcional, pero recomendado para recuperar el acceso.">
                  <Input
                    type="email"
                    value={form.email}
                    onChange={(e) => set("email", e.target.value)}
                    placeholder="ejemplo@correo.com"
                    autoComplete="email"
                  />
                </Field>

                <Field label="Tasa de cambio (C$ por US$)">
                  <Input
                    type="number"
                    min="1"
                    step="0.01"
                    inputMode="decimal"
                    value={form.tasa_cambio}
                    onChange={(e) => set("tasa_cambio", e.target.value)}
                  />
                </Field>
              </>
            )}

            <Field label="Usuario" required>
              <Input
                value={form.usuario}
                onChange={(e) => set("usuario", e.target.value)}
                placeholder="tu_usuario"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck="false"
                maxLength={64}
              />
            </Field>

            <Field
              label="Contraseña"
              required
              hint={modo === "register" ? "Mínimo 8 caracteres, con letras y números." : undefined}
            >
              <div className="relative">
                <Input
                  type={verPassword ? "text" : "password"}
                  value={form.password}
                  onChange={(e) => set("password", e.target.value)}
                  placeholder="••••••••"
                  autoComplete={modo === "login" ? "current-password" : "new-password"}
                  className="pr-11"
                />
                <button
                  type="button"
                  onClick={() => setVerPassword((v) => !v)}
                  aria-label={verPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 btn-icon"
                >
                  {verPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
                </button>
              </div>
            </Field>

            {error && (
              <p
                role="alert"
                className="text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3.5 py-2.5"
              >
                {error}
              </p>
            )}

            <Button type="submit" loading={enviando} className="w-full py-3 text-sm mt-1">
              {modo === "login" ? "Iniciar sesión" : "Crear cuenta"}
            </Button>

            {modo === "login" && (
              <button
                type="button"
                onClick={() =>
                  toast("Pide al administrador que restablezca tu contraseña.", "info")
                }
                className="text-xs text-content-muted hover:text-content transition-colors w-full text-center"
              >
                ¿Olvidaste tu contraseña?
              </button>
            )}
          </form>

          {GOOGLE_CLIENT_ID && (
            <>
              <div className="relative my-6" aria-hidden="true">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-border" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-surface px-3 text-xs text-content-subtle">o continúa con</span>
                </div>
              </div>
              <div className="flex flex-col items-center gap-2">
                <div ref={refGoogle} className="flex justify-center min-h-[40px] w-full" />
                {!googleListo && (
                  <p className="text-xs text-content-subtle flex items-center gap-1.5">
                    <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                    Cargando Google…
                  </p>
                )}
              </div>
            </>
          )}

          <p className="text-center text-sm text-content-muted mt-7">
            {modo === "login" ? "¿No tienes cuenta? " : "¿Ya tienes cuenta? "}
            <button
              type="button"
              onClick={cambiarModo}
              className="text-brand-600 dark:text-brand-300 font-medium hover:underline"
            >
              {modo === "login" ? "Regístrate" : "Inicia sesión"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
