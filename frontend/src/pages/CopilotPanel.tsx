import { useEffect, useRef, useState, type FormEvent } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ArrowUp, Check, CircleHelp, LoaderCircle, Sparkles, X } from 'lucide-react';
import { demoApi } from '../services/demoApi';
import type { EventRecord } from '../types';
import { DemoBanner } from '../components/ui';

type Message = { role: 'user' | 'assistant'; content: string; references?: string[] };
const suggestions = ['What is still open?', 'How much budget remains?', 'What changes if guests increase?'];

export function CopilotPanel({ open, onClose, event }: { open: boolean; onClose: () => void; event: EventRecord }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    if (!open) { setMessages([]); setError(''); return; }
    previousFocusRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 80);
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); onCloseRef.current(); return; }
      if (event.key !== 'Tab') return;
      const items = panelRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])');
      if (!items?.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (event.shiftKey && (document.activeElement === first || !panelRef.current?.contains(document.activeElement))) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || !panelRef.current?.contains(document.activeElement))) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKey);
      previousFocusRef.current?.focus();
    };
  }, [open]);
  useEffect(() => { bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' }); }, [messages, loading]);

  async function ask(value: string) {
    const clean = value.trim();
    if (!clean || loading) return;
    setQuestion('');
    setError('');
    setMessages((current) => [...current, { role: 'user', content: clean }]);
    setLoading(true);
    try {
      const result = await demoApi.answerCopilot(event.id, clean);
      setMessages((current) => [...current, { role: 'assistant', content: result.data.answer, references: result.data.references }]);
    } catch {
      setError('That answer did not come through. Your event plan is unchanged; please try again.');
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(eventObject: FormEvent<HTMLFormElement>) {
    eventObject.preventDefault();
    void ask(question);
  }

  return (
    <AnimatePresence>
      {open && <>
        <motion.button className="copilot-scrim" aria-label="Close MomentOS assistant" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
        <motion.aside ref={panelRef} className="copilot-panel" role="dialog" aria-modal="true" aria-labelledby="copilot-title" aria-describedby="copilot-description" initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 28, stiffness: 250 }}>
          <header className="copilot-header"><div className="copilot-heading-icon"><Sparkles size={19} /></div><div><h2 id="copilot-title">A little more clarity</h2><p id="copilot-description">MomentOS copilot · {event.title}</p></div><button className="icon-button" onClick={onClose} aria-label="Close assistant"><X size={19} /></button></header>
          <div className="copilot-demo-state"><DemoBanner compact /></div>
          <div className="copilot-message-list" ref={bodyRef} aria-live="polite" aria-relevant="additions">
            {messages.length === 0 && <div className="copilot-welcome"><span className="welcome-spark"><Sparkles size={21} /></span><h3>Here with the details.</h3><p>Ask about this event. The copilot uses only its authorized saved planning context.</p><div className="suggested-questions"><span>Try asking</span>{suggestions.map((suggestion) => <button key={suggestion} onClick={() => void ask(suggestion)}>{suggestion}<ArrowUp size={13} /></button>)}</div></div>}
            {messages.map((message, index) => <div key={`${message.role}-${index}`} className={`chat-message chat-${message.role}`}><div className="chat-avatar">{message.role === 'assistant' ? <Sparkles size={14} /> : 'M'}</div><div><p>{message.content}</p>{message.references?.length ? <div className="answer-references"><Check size={12} /> Grounded in your saved plan</div> : null}</div></div>)}
            {loading && <div className="chat-message chat-assistant"><div className="chat-avatar"><Sparkles size={14} /></div><div className="typing-state"><LoaderCircle size={15} className="spin" /> Looking through your plan…</div></div>}
            {error && <div className="copilot-error" role="alert"><CircleHelp size={15} />{error}<button onClick={() => { const lastQuestion = [...messages].reverse().find((message) => message.role === 'user')?.content; if (lastQuestion) void ask(lastQuestion); }}>Try again</button></div>}
          </div>
          <form className="copilot-composer" onSubmit={handleSubmit}><label className="sr-only" htmlFor="copilot-question">Ask a question about your event</label><input id="copilot-question" ref={inputRef} value={question} onChange={(eventObject) => setQuestion(eventObject.target.value)} placeholder="Ask about your event…" maxLength={4000} disabled={loading} /><button className="send-button" type="submit" aria-label="Send question" disabled={!question.trim() || loading}><ArrowUp size={18} /></button><small>Read-only answers · never saves changes</small></form>
        </motion.aside>
      </>}
    </AnimatePresence>
  );
}
