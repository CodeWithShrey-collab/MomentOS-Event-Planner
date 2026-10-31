import { createContext, useCallback, useContext, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Check, CircleAlert, X } from 'lucide-react';

type ToastTone = 'success' | 'error';
type ToastMessage = { id: string; title: string; detail?: string; tone: ToastTone };
type ToastContextValue = { showToast: (title: string, detail?: string, tone?: ToastTone) => void };
const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<ToastMessage[]>([]);
  const showToast = useCallback((title: string, detail?: string, tone: ToastTone = 'success') => {
    const id = crypto.randomUUID();
    setMessages((current) => [...current, { id, title, detail, tone }]);
    window.setTimeout(() => setMessages((current) => current.filter((message) => message.id !== id)), tone === 'error' ? 8000 : 3600);
  }, []);
  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-region" aria-live="polite" aria-relevant="additions">
        <AnimatePresence>
          {messages.map((message) => (
            <motion.div key={message.id} className="toast" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }}>
              <span className={`toast-icon toast-icon-${message.tone}`} role="img" aria-label={message.tone === 'error' ? 'Error' : 'Success'}>{message.tone === 'error' ? <CircleAlert size={16} aria-hidden="true" /> : <Check size={16} aria-hidden="true" />}</span>
              <span><strong>{message.title}</strong>{message.detail && <small>{message.detail}</small>}</span>
              <button className="icon-button toast-close" aria-label="Dismiss notification" onClick={() => setMessages((current) => current.filter((item) => item.id !== message.id))}><X size={16} /></button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const value = useContext(ToastContext);
  if (!value) throw new Error('useToast must be used within ToastProvider');
  return value;
}
