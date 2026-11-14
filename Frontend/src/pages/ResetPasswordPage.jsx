import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, Eye, EyeOff, KeyRound } from "lucide-react";

import { Button } from "../components/ui/Button";
import { Field, Input } from "../components/ui/Field";
import { useToast } from "../context/ToastContext";
import { api } from "../lib/api";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const navigate = useNavigate();
  const { toast } = useToast();

  const [password, setPassword] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [ver, setVer] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [listo, setListo] = useState(false);

  async function alEnviar(e) {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres");
      return;
    }
    if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) {
      setError("La contraseña debe combinar letras y números");
      return;
    }
    if (password !== confirmar) {
      setError("Las contraseñas no coinciden");
      return;
    }

    setEnviando(true);
    try {
      await api.post("/auth/reset", { token, password_nuevo: password });
      setListo(true);
      toast("Contraseña actualizada");
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-3 mb-9">
          <div
            className="w-10 h-10 rounded-xl bg-brand-600 flex items-center justify-center"
            style={{ color: "rgb(var(--brand-contrast, 255 255 255))" }}
            aria-hidden="true"
          >
            <KeyRound size={18} />
          </div>
          <span className="text-lg font-bold text-content">Bravo's Gest</span>
        </div>

        {!token ? (
          <div className="space-y-4">
            <h1 className="text-2xl font-bold text-content">Enlace inválido</h1>
            <p className="text-sm text-content-muted">
              Falta el token de recuperación. Solicita un enlace nuevo desde la pantalla
              de inicio de sesión.
            </p>
            <Button onClick={() => navigate("/", { replace: true })}>
              Volver al inicio
            </Button>
          </div>
        ) : listo ? (
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-secondary-500/10 flex items-center justify-center">
              <CheckCircle2 size={22} className="text-secondary-600 dark:text-secondary-400" />
            </div>
            <h1 className="text-2xl font-bold text-content">Contraseña actualizada</h1>
            <p className="text-sm text-content-muted">
              Cerramos todas tus sesiones por seguridad. Inicia sesión con la contraseña
              nueva.
            </p>
            <Button className="w-full py-3" onClick={() => navigate("/", { replace: true })}>
              Iniciar sesión
            </Button>
          </div>
        ) : (
          <form onSubmit={alEnviar} className="space-y-4" noValidate>
            <div>
              <h1 className="text-2xl font-bold text-content">Nueva contraseña</h1>
              <p className="text-sm text-content-muted mt-1.5">
                Elige una contraseña de al menos 8 caracteres, con letras y números.
              </p>
            </div>

            <Field label="Contraseña nueva" required>
              <div className="relative">
                <Input
                  type={ver ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  className="pr-11"
                  autoFocus
                />
                <button
                  type="button"
                  onClick={() => setVer((v) => !v)}
                  aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 btn-icon"
                >
                  {ver ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </Field>

            <Field label="Repite la contraseña" required>
              <Input
                type={ver ? "text" : "password"}
                value={confirmar}
                onChange={(e) => setConfirmar(e.target.value)}
                placeholder="••••••••"
                autoComplete="new-password"
              />
            </Field>

            {error && (
              <p
                role="alert"
                className="text-sm text-red-600 dark:text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3.5 py-2.5"
              >
                {error}
              </p>
            )}

            <Button type="submit" loading={enviando} className="w-full py-3 text-sm">
              Cambiar contraseña
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
