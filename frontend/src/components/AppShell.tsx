import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { CalendarDays, ChartNoAxesCombined, CircleHelp, Compass, GitCompareArrows, HeartHandshake, House, Map, Menu, Sparkles, WalletCards, X } from 'lucide-react';
import type { EventRecord } from '../types';
import { DemoBanner } from './ui';
import { CopilotPanel } from '../pages/CopilotPanel';
import { demoApi } from '../services/demoApi';

export function Brand({ light = false }: { light?: boolean }) {
  return <Link to="/" className={`brand${light ? ' brand-light' : ''}`} aria-label="MomentOS home"><span className="brand-symbol"><span /><span /><span /></span><span>moment<span className="brand-strong">OS</span></span></Link>;
}

const navItems = [
  { to: '', label: 'Command center', icon: House, end: true },
  { to: '/budget', label: 'Budget studio', icon: WalletCards },
  { to: '/map', label: 'Moment map', icon: Map },
  { to: '/vendors', label: 'Vendors', icon: HeartHandshake },
  { to: '/ripple', label: 'Ripple engine', icon: ChartNoAxesCombined, featured: true },
  { to: '/scenarios', label: 'Compare plans', icon: GitCompareArrows },
];

export function AppShell({ event, children }: { event: EventRecord; children: ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [copilotOpen, setCopilotOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const menuWasOpenRef = useRef(false);
  const eventPath = `/events/${event.id}`;
  useEffect(() => {
    if (!menuOpen) {
      if (menuWasOpenRef.current) mobileMenuButtonRef.current?.focus();
      menuWasOpenRef.current = false;
      return;
    }
    menuWasOpenRef.current = true;
    const focusTimer = window.setTimeout(() => sidebarRef.current?.querySelector<HTMLElement>('.mobile-menu-close')?.focus(), 0);
    const handleKey = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === 'Escape') { keyboardEvent.preventDefault(); setMenuOpen(false); return; }
      if (keyboardEvent.key !== 'Tab') return;
      const items = sidebarRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
      if (!items?.length) return;
      const first = items[0]!;
      const last = items[items.length - 1]!;
      if (keyboardEvent.shiftKey && document.activeElement === first) { keyboardEvent.preventDefault(); last.focus(); }
      else if (!keyboardEvent.shiftKey && document.activeElement === last) { keyboardEvent.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handleKey);
    return () => { window.clearTimeout(focusTimer); document.removeEventListener('keydown', handleKey); };
  }, [menuOpen]);
  return (
    <div className="app-shell">
      <aside ref={sidebarRef} id="workspace-sidebar" aria-label="Event workspace navigation" className={`sidebar${menuOpen ? ' sidebar-open' : ''}`}>
        <div className="sidebar-top"><Brand /><button className="icon-button mobile-menu-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20} /></button></div>
        <DemoBanner compact />
        <div className="sidebar-event-label">YOUR EVENT</div>
        <Link className="sidebar-event" to={eventPath}><span className={`event-kind-mark kind-${event.eventType}`}><CalendarDays size={18} /></span><span className="sidebar-event-copy"><strong>{event.title}</strong><small>{event.city} · {event.guestCount} guests</small></span></Link>
        <nav className="side-nav" aria-label="Event workspace">
          {navItems.map(({ to, label, icon: Icon, end, featured }) => (
            <NavLink key={to} to={`${eventPath}${to}`} end={end} className={({ isActive }) => `side-link${isActive ? ' side-link-active' : ''}${featured ? ' side-link-featured' : ''}`} onClick={() => setMenuOpen(false)}>
              <Icon size={18} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span>{featured && <span className="nav-spark"><Sparkles size={13} /></span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-progress"><div className="progress-head"><span>Getting closer</span><strong>{Math.round(event.tasks.filter((task) => task.status === 'completed').length / Math.max(event.tasks.length, 1) * 100)}%</strong></div><div className="progress-track"><span style={{ width: `${event.tasks.filter((task) => task.status === 'completed').length / Math.max(event.tasks.length, 1) * 100}%` }} /></div><small>Based on tasks you have completed</small></div>
          <button className="copilot-launch" onClick={() => setCopilotOpen(true)}><span className="copilot-icon"><Sparkles size={17} /></span><span><strong>Ask MomentOS</strong><small>Grounded in this plan</small></span><span className="copilot-arrow">↗</span></button>
          <Link className="sidebar-home" to="/"><Compass size={16} /> All celebrations</Link>
        </div>
      </aside>

      {menuOpen && <button className="mobile-scrim" aria-label="Close navigation menu" onClick={() => setMenuOpen(false)} />}
      <main className="workspace-main">
        <header className="topbar">
          <button ref={mobileMenuButtonRef} className="icon-button mobile-menu-open" aria-label="Open navigation" aria-expanded={menuOpen} aria-controls="workspace-sidebar" onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
          <div className="topbar-crumb"><span>Workspace</span><span className="crumb-slash">/</span><strong>{event.title}</strong></div>
          <div className="topbar-right"><span className="saved-indicator"><span /> {demoApi.mode === 'offline_demo' ? 'Saved in this browser' : 'Saved to your workspace'}</span><button className="help-button" aria-label="Need a hand? Ask MomentOS for help" onClick={() => setCopilotOpen(true)}><CircleHelp size={17} /><span>Need a hand?</span></button><span className="avatar-button" aria-label="Guest planner">M</span></div>
        </header>
        <div className="workspace-content">{children}</div>
      </main>
      <CopilotPanel open={copilotOpen} onClose={() => setCopilotOpen(false)} event={event} />
    </div>
  );
}
