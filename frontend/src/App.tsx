import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useParams } from 'react-router-dom';
import { AppShell } from './components/AppShell';
import { DemoBanner, EmptyState, LoadingBlock } from './components/ui';
import { demoApi } from './services/demoApi';
import type { EventRecord } from './types';
import { ToastProvider } from './hooks/useToast';

const LandingPage = lazy(() => import('./pages/LandingPage').then((module) => ({ default: module.LandingPage })));
const EventArchitect = lazy(() => import('./pages/EventArchitect').then((module) => ({ default: module.EventArchitect })));
const DashboardPage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.DashboardPage })));
const BudgetPage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.BudgetPage })));
const MomentMapPage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.MomentMapPage })));
const RipplePage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.RipplePage })));
const ScenariosPage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.ScenariosPage })));
const VendorsPage = lazy(() => import('./pages/WorkspacePages').then((module) => ({ default: module.VendorsPage })));

function WorkspaceRoutes() {
  const { eventId = '' } = useParams();
  const [event, setEvent] = useState<EventRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setLoading(true); setError('');
    demoApi.getEvent(eventId).then((response) => { if (active) setEvent(response.data); }).catch((caught) => { if (active) setError(caught instanceof Error ? caught.message : 'Could not load this event.'); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [eventId]);
  if (loading) return <div className="full-page-loading"><LoadingBlock label="Opening your celebration…" /></div>;
  if (!event || error) return <div className="missing-event-page"><DemoBanner /><EmptyState title={error ? 'This event could not be opened' : 'This event is not available'} detail={error || 'It may have been removed, or it may belong to another session.'} action={<a className="button button-primary" href="/">Back to MomentOS</a>} /></div>;
  return <AppShell event={event}>
    <Routes>
      <Route index element={<DashboardPage event={event} onEventUpdated={setEvent} />} />
      <Route path="budget" element={<BudgetPage event={event} onEventUpdated={setEvent} />} />
      <Route path="map" element={<MomentMapPage event={event} onEventUpdated={setEvent} />} />
      <Route path="vendors" element={<VendorsPage event={event} onEventUpdated={setEvent} />} />
      <Route path="ripple" element={<RipplePage event={event} onEventUpdated={setEvent} />} />
      <Route path="scenarios" element={<ScenariosPage event={event} onEventUpdated={setEvent} />} />
      <Route path="*" element={<Navigate to={`/events/${event.id}`} replace />} />
    </Routes>
  </AppShell>;
}

function AppRoutes() {
  return <Suspense fallback={<div className="full-page-loading"><LoadingBlock label="Opening MomentOS…" /></div>}><Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/events/new" element={<EventArchitect />} />
      <Route path="/events/:eventId/*" element={<WorkspaceRoutes />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></Suspense>;
}

export default function App() {
  return <BrowserRouter><ToastProvider><AppRoutes /></ToastProvider></BrowserRouter>;
}
