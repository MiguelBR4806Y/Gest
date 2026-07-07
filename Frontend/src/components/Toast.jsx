import { useToast } from "../context/ToastContext";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const STYLES = {
  success: "bg-emerald-500/10 border-emerald-500/25 text-emerald-400",
  error: "bg-red-500/10 border-red-500/25 text-red-400",
  info: "bg-accent-500/10 border-accent-500/25 text-accent-400",
};

export default function Toast() {
  const { toasts, dismissToast } = useToast();

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-5 right-5 z-[9999] flex flex-col gap-2 max-w-sm">
      {toasts.map(t => {
        const Icon = ICONS[t.type] || Info;
        return (
          <div key={t.id}
            className={`flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-md bg-surface-card shadow-lg animate-slide-up ${STYLES[t.type] || STYLES.info}`}>
            <Icon size={18} className="shrink-0 mt-0.5" />
            <p className="text-sm flex-1">{t.message}</p>
            <button onClick={() => dismissToast(t.id)}
              className="shrink-0 opacity-60 hover:opacity-100 transition-opacity">
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
