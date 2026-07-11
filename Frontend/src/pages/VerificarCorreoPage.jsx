import { useState, useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { CheckCircle, XCircle, Loader2 } from "lucide-react";

export default function VerificarCorreoPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token");
  const [status, setStatus] = useState("loading");

  useEffect(() => {
    if (!token) { setStatus("invalid"); return; }
    api.get(`/auth/verificar-correo?token=${token}`)
      .then(() => setStatus("success"))
      .catch(() => setStatus("error"));
  }, [token]);

  return (
    <div className="min-h-screen bg-surface flex items-center justify-center px-4">
      <div className="w-full max-w-sm text-center">
        {status === "loading" && (
          <div className="flex flex-col items-center gap-4">
            <Loader2 size={40} className="text-brand-400 animate-spin" />
            <p className="text-content-muted">Verificando correo...</p>
          </div>
        )}
        {status === "success" && (
          <div className="flex flex-col items-center gap-4">
            <CheckCircle size={48} className="text-emerald-400" />
            <h2 className="text-xl font-bold text-content">Correo verificado</h2>
            <p className="text-content-muted text-sm">Tu correo ha sido verificado exitosamente.</p>
            <button onClick={() => navigate("/dashboard")}
              className="btn-primary mt-4">
              Ir al dashboard
            </button>
          </div>
        )}
        {status === "invalid" && (
          <div className="flex flex-col items-center gap-4">
            <XCircle size={48} className="text-red-400" />
            <h2 className="text-xl font-bold text-content">Enlace inválido</h2>
            <p className="text-content-muted text-sm">El enlace de verificación no es válido o ha expirado.</p>
            <button onClick={() => navigate("/")}
              className="btn-primary mt-4">
              Volver al inicio
            </button>
          </div>
        )}
        {status === "error" && (
          <div className="flex flex-col items-center gap-4">
            <XCircle size={48} className="text-red-400" />
            <h2 className="text-xl font-bold text-content">Error</h2>
            <p className="text-content-muted text-sm">No se pudo verificar el correo. El token podría ser inválido.</p>
            <button onClick={() => navigate("/")}
              className="btn-primary mt-4">
              Volver al inicio
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
