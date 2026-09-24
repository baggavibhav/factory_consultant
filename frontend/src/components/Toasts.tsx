import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AlertTriangle, Check } from "lucide-react";

type Toast = { id: number; text: string; bad?: boolean };
const Ctx = createContext<(text: string, bad?: boolean) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, bad = false) => {
    const id = Date.now() + Math.random();
    setItems((t) => [...t, { id, text, bad }]);
    setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), bad ? 7000 : 3500);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast${t.bad ? " bad" : ""}`}>
            {t.bad ? <AlertTriangle size={16} /> : <Check size={16} />}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export const useToast = () => useContext(Ctx);
