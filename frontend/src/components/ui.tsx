import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Sparkles, X } from 'lucide-react';

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'text' | 'light'; size?: 'small' | 'large' };
export function Button({ variant = 'primary', size, className = '', ...props }: ButtonProps) {
  return <button {...props} className={`button button-${variant}${size ? ` button-${size}` : ''} ${className}`} />;
}

export function DemoBanner({ compact = false }: { compact?: boolean }) {
  if (import.meta.env.VITE_MOMENTOS_MODE !== 'demo') return null;
  return <div className={`demo-banner${compact ? ' demo-banner-compact' : ''}`}><span className="demo-dot" /> Offline demo <span className="demo-divider">·</span> sample plan & illustrative assumptions</div>;
}

export function StatusBadge({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'good' | 'warning' | 'plum' | 'coral' }) {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
}

export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-title-row"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{action && <div className="page-title-action">{action}</div>}</div>;
}

export function SectionHeader({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="section-header"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{action}</div>;
}

export function IconButton({ label, children, onClick }: { label: string; children: ReactNode; onClick?: () => void }) {
  return <button type="button" className="icon-button" aria-label={label} onClick={onClick}>{children}</button>;
}

export function ConfirmationDialog({ open, title, children, confirmLabel, onConfirm, onCancel, busy = false, disabled = false }: {
  open: boolean; title: string; children: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean; disabled?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const firstButton = dialogRef.current?.querySelector<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex="0"]');
    firstButton?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !busy) onCancel();
      if (event.key !== 'Tab') return;
      const items = dialogRef.current?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [tabindex="0"]');
      if (!items?.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('keydown', handleKey);
      previousFocus.current?.focus();
    };
  }, [open, busy, onCancel]);

  return (
    <AnimatePresence>
      {open && <motion.div className="dialog-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
        <motion.div ref={dialogRef} className="dialog-panel" role="alertdialog" aria-modal="true" aria-labelledby="dialog-title" initial={{ opacity: 0, y: 18, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 12, scale: 0.98 }}>
          <div className="dialog-heading"><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onCancel} disabled={busy}><X size={18} /></button></div>
          <div className="dialog-content">{children}</div>
          <div className="dialog-actions"><Button variant="secondary" onClick={onCancel} disabled={busy}>Keep planning</Button><Button onClick={onConfirm} disabled={busy || disabled}>{busy ? 'Saving…' : confirmLabel}</Button></div>
        </motion.div>
      </motion.div>}
    </AnimatePresence>
  );
}

export function LoadingBlock({ label }: { label: string }) {
  return <div className="loading-block" role="status"><span className="spinner" aria-hidden="true" /><span>{label}</span></div>;
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-mark" aria-hidden="true"><Sparkles size={22} /></span><h3>{title}</h3><p>{detail}</p>{action}</div>;
}
