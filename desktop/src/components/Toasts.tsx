import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useApp } from "../state/store";

const ICONS = {
  info: Info,
  success: CheckCircle2,
  error: AlertCircle,
};

export function Toasts() {
  const toasts = useApp((state) => state.toasts);
  const dismiss = useApp((state) => state.dismissToast);

  return (
    <div className="toasts" aria-live="polite">
      {toasts.map((toast) => {
        const Icon = ICONS[toast.tone];
        return (
          <div key={toast.id} className={`toast toast--${toast.tone}`}>
            <Icon size={16} />
            <span>{toast.message}</span>
            <button aria-label="Dismiss" onClick={() => dismiss(toast.id)}>
              <X size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
}
