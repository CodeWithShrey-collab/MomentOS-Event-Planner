import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, ArrowRight, ArrowUpRight, CalendarDays, Check, ChevronDown, CircleDot, Clock3, Compass, GitCompareArrows, HeartHandshake, Info, Plus, Sparkles, Users, WalletCards } from 'lucide-react';
import { demoApi, formatRupees, parseRupeesToMinor, sumCategories } from '../services/demoApi';
import { totalActual } from '../data/demoData';
import type { EventRecord, EventTask, RipplePreview, ScenarioResult, Vendor, VendorStatus } from '../types';
import { useToast } from '../hooks/useToast';
import { Button, ConfirmationDialog, EmptyState, LoadingBlock, PageTitle, SectionHeader, StatusBadge } from '../components/ui';

type PageProps = { event: EventRecord; onEventUpdated: (event: EventRecord) => void };

function BudgetDonut({ event }: { event: EventRecord }) {
  const data = event.categories.map((category) => ({ name: category.name, value: category.plannedMinor, color: category.color }));
  return <div className="budget-donut-wrap"><div className="budget-donut-chart" aria-label="Budget allocation chart"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={data} dataKey="value" nameKey="name" innerRadius="72%" outerRadius="96%" paddingAngle={2} stroke="none">{data.map((item) => <Cell key={item.name} fill={item.color} />)}</Pie><Tooltip formatter={(value) => formatRupees(Number(value))} contentStyle={{ borderRadius: 12, border: '1px solid #e9e3da', fontFamily: 'Satoshi, sans-serif' }} /></PieChart></ResponsiveContainer><div className="donut-center"><span>PLANNED</span><strong>{formatRupees(sumCategories(event.categories))}</strong></div></div><div className="chart-legend">{data.slice(0, 5).map((item) => <div key={item.name}><span style={{ background: item.color }} /><span>{item.name}</span><strong>{formatRupees(item.value)}</strong></div>)}</div></div>;
}

function nextTask(event: EventRecord): EventTask | undefined {
  return event.tasks.find((task) => task.status !== 'completed');
}

export function DashboardPage({ event }: PageProps) {
  const total = sumCategories(event.categories);
  const actual = totalActual(event.categories);
  const progress = Math.round(event.tasks.filter((task) => task.status === 'completed').length / Math.max(event.tasks.length, 1) * 100);
  const remaining = event.budgetLimitMinor - total;
  const upcoming = event.tasks.filter((task) => task.status !== 'completed').slice(0, 3);
  const task = nextTask(event);
  const daysToGo = event.eventDate ? Math.max(0, Math.ceil((new Date(`${event.eventDate}T12:00:00`).getTime() - new Date().setHours(12, 0, 0, 0)) / 86_400_000)) : null;
  return <div className="page-wrap dashboard-page">
    <PageTitle eyebrow="YOUR CELEBRATION, AT A GLANCE" title={event.title} description={`${event.city || 'Location to be decided'}${event.eventDate ? ` · ${new Date(`${event.eventDate}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}` : ''} · ${event.guestCount} guests`} action={<Link className="button button-secondary" to={`/events/${event.id}/ripple`}><Sparkles size={16} /> Explore a change</Link>} />
    <div className="dashboard-lead"><div className="lead-copy"><div className="lead-copy-icon"><Sparkles size={18} /></div><p className="eyebrow">A moment worth making room for</p><h2>{event.concept || 'A good plan starts with a little clarity.'}</h2><p className="lead-foot">{demoApi.mode === 'offline_demo' ? 'Your plan is saved in this browser demo.' : 'Your plan is saved to your event workspace.'} Every detail remains editable.</p></div><div className="lead-image"><img src="/images/dashboard-table.webp" alt="A decorated wedding table with candles and flowers" /><div className="lead-image-caption"><span>{event.theme || 'Your event, taking shape'}</span><ArrowUpRight size={16} /></div></div></div>
    <div className="dashboard-stats"><article className="stat-tile"><div className="stat-label"><WalletCards size={16} /> Budget health</div><strong className={remaining < 0 ? 'text-danger' : ''}>{remaining < 0 ? `${formatRupees(Math.abs(remaining))} over` : formatRupees(remaining)}</strong><span>{remaining < 0 ? 'Over the current planning limit' : 'Room within the illustrative limit'}</span><div className="stat-progress"><span style={{ width: `${Math.min(100, Math.max(0, total / event.budgetLimitMinor * 100))}%` }} /></div></article><article className="stat-tile"><div className="stat-label"><Check size={16} /> Planning progress</div><strong>{progress}%</strong><span>{event.tasks.filter((item) => item.status === 'completed').length} of {event.tasks.length} tasks completed by you</span><div className="stat-progress progress-green"><span style={{ width: `${progress}%` }} /></div></article><article className="stat-tile"><div className="stat-label"><CalendarDays size={16} /> The day is in</div><strong>{daysToGo === null ? 'Not set' : `${daysToGo} days`}</strong><span>{event.eventDate ? 'Keep the next milestone in sight' : 'Add a date when you know it'}</span><div className="stat-foot-line"><span className="stat-line" /><span className="stat-line short" /><span className="stat-line" /></div></article><article className="stat-tile stat-task-tile"><div className="stat-label"><Clock3 size={16} /> Coming up</div>{task ? <><strong className="stat-task-title">{task.title}</strong><span>{task.dueLabel} · {task.owner || 'No owner yet'}</span><Link to={`/events/${event.id}/map`} className="stat-link">Open Moment Map <ArrowRight size={14} /></Link></> : <><strong>All caught up</strong><span>Everything is checked off for now.</span></>}</article></div>

    <div className="dashboard-lower"><section className="dashboard-panel budget-overview-panel"><SectionHeader title="A clear view of the budget" detail="Illustrative amounts · user-entered actuals" action={<Link to={`/events/${event.id}/budget`} className="text-link">Open studio <ArrowRight size={15} /></Link>} /><BudgetDonut event={event} /><div className="budget-overview-footer"><span><i className="actual-dot" /> Actual entered</span><strong>{formatRupees(actual)}</strong><span className="budget-divider" /><span>Limit</span><strong>{formatRupees(event.budgetLimitMinor)}</strong></div></section>
      <section className="dashboard-panel next-steps-panel"><SectionHeader title="A few things in motion" detail="Based on tasks in your plan" action={<Link to={`/events/${event.id}/map`} className="text-link">See the map <ArrowRight size={15} /></Link>} /><div className="upcoming-list">{upcoming.map((item, index) => <div className="upcoming-item" key={item.id}><span className={`upcoming-step ${item.status === 'in_progress' ? 'step-current' : ''}`}>{item.status === 'in_progress' ? <CircleDot size={14} /> : `0${index + 1}`}</span><div><strong>{item.title}</strong><small>{item.dueLabel} · {item.phase}</small></div><span className="upcoming-priority">{item.priority === 'high' ? 'Soon' : 'In view'}</span></div>)}</div><div className="soft-insight"><span><Sparkles size={15} /></span><p><strong>A helpful next thought</strong><br />{remaining < 0 ? 'Your current plan is above its limit. Open Budget Studio to review the editable assumptions.' : 'Your plan has room to adjust. You can try a guest-count change in Ripple before saving anything.'}</p><Link to={`/events/${event.id}/ripple`} aria-label="Open Ripple Engine"><ArrowUpRight size={15} /></Link></div></section></div>
    <div className="dashboard-bottom"><section className="vendor-snapshot"><div><p className="eyebrow">PEOPLE WHO HELP MAKE IT HAPPEN</p><h3>Vendor checklist</h3><p>Suggested categories and details you entered.</p></div><div className="vendor-snapshot-list">{event.vendors.slice(0, 3).map((vendor) => <div key={vendor.id}><span className={`vendor-status-dot vendor-dot-${vendor.status}`} /><span>{vendor.category}</span><small>{vendor.status.replaceAll('_', ' ')}</small></div>)}</div><Link className="text-link" to={`/events/${event.id}/vendors`}>Open vendor workspace <ArrowRight size={15} /></Link></section><section className="dashboard-note"><span className="note-sun"><Sparkles size={18} /></span><div><strong>Leave space for the unexpected.</strong><p>Good plans hold the details gently, so the day still has room to become its own.</p></div><span className="note-signature">MomentOS</span></section></div>
  </div>;
}

export function BudgetPage({ event, onEventUpdated }: PageProps) {
  const { showToast } = useToast();
  const [draftValues, setDraftValues] = useState<Record<string, string>>(() => Object.fromEntries(event.categories.map((category) => [category.id, String(category.plannedMinor / 100)])));
  const [savingId, setSavingId] = useState<string | null>(null);
  const total = sumCategories(event.categories);
  const actual = totalActual(event.categories);
  const chartData = event.categories.map((category) => ({ name: category.name, Planned: category.plannedMinor / 100, Actual: (category.actualMinor ?? 0) / 100, fill: category.color }));
  const spentPercent = event.budgetLimitMinor ? Math.round(total / event.budgetLimitMinor * 100) : 0;

  async function saveCategory(categoryId: string) {
    const amount = parseRupeesToMinor(draftValues[categoryId] ?? '');
    if (amount === null) { showToast('Check that amount', 'Use rupees with up to two decimal places.'); return; }
    setSavingId(categoryId);
    try {
      const result = await demoApi.updateCategory(event.id, categoryId, amount);
      onEventUpdated(result.data);
      showToast('Budget updated', demoApi.mode === 'offline_demo' ? 'This change is saved in your browser demo.' : 'This change is saved to your event workspace.');
    } catch (error) { showToast('Could not update this category', error instanceof Error ? error.message : 'Try again.'); }
    finally { setSavingId(null); }
  }

  return <div className="page-wrap budget-page">
    <PageTitle eyebrow="MAKE THE NUMBERS FEEL CLEARER" title="Budget studio" description="Keep every estimate in context. Edit an amount, see the balance move, and know what is still open." action={<StatusBadge tone="warning">Illustrative assumptions</StatusBadge>} />
    <section className="budget-summary-row"><article className="budget-summary-card summary-limit"><span>Your planning limit</span><strong>{formatRupees(event.budgetLimitMinor)}</strong><small>Set by you · INR</small></article><article className="budget-summary-card summary-planned"><span>Planned so far</span><strong>{formatRupees(total)}</strong><small>{spentPercent}% of the current limit</small><div className="summary-track"><span style={{ width: `${Math.min(spentPercent, 100)}%` }} /></div></article><article className="budget-summary-card summary-actual"><span>Actual entered</span><strong>{formatRupees(actual)}</strong><small>User-entered amounts only</small></article><article className={`budget-summary-card summary-remaining${event.budgetLimitMinor - total < 0 ? ' summary-over' : ''}`}><span>{event.budgetLimitMinor - total < 0 ? 'Over the limit' : 'Still available'}</span><strong>{formatRupees(Math.abs(event.budgetLimitMinor - total))}</strong><small>Calculated from planned line items</small></article></section>
    <section className="budget-chart-panel"><div className="chart-panel-head"><div><p className="eyebrow">WHERE THE PLAN SITS</p><h2>Planned alongside actual</h2><p>Actuals appear only when you enter them.</p></div><div className="chart-legend-inline"><span><i className="legend-planned" /> Planned</span><span><i className="legend-actual" /> Actual entered</span></div></div><div className="budget-bar-chart" role="img" aria-label="Grouped bar chart comparing planned and actual event spending by category"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} margin={{ top: 8, right: 18, left: 0, bottom: 5 }} barGap={5}><CartesianGrid vertical={false} stroke="#e9e3da" strokeDasharray="3 5" /><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#77716d', fontSize: 11 }} interval={0} angle={-13} textAnchor="end" height={54} /><YAxis axisLine={false} tickLine={false} tick={{ fill: '#77716d', fontSize: 11 }} tickFormatter={(value: number) => `₹${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => formatRupees(Number(value) * 100)} contentStyle={{ borderRadius: 12, border: '1px solid #e9e3da', fontFamily: 'Satoshi, sans-serif' }} /><Bar dataKey="Planned" fill="#74536f" radius={[5, 5, 0, 0]} maxBarSize={20} /><Bar dataKey="Actual" fill="#c7a86a" radius={[5, 5, 0, 0]} maxBarSize={20} /></BarChart></ResponsiveContainer></div><div className="chart-text-alternative"><strong>Exact values</strong>{chartData.map((category) => <span key={category.name}>{category.name}: {formatRupees(category.Planned)} planned · {category.Actual ? formatRupees(category.Actual) : 'no actual entered'}</span>)}</div></section>
    <section className="budget-edit-panel"><SectionHeader title="Your categories" detail="Edit the planned amount. Values marked illustrative are planning assumptions." action={<StatusBadge tone="neutral">INR · rupees</StatusBadge>} /><div className="budget-category-table"><div className="budget-table-head"><span>Category</span><span>Source</span><span>Planned</span><span>Actual</span><span>Update</span></div>{event.categories.map((category) => <div className="budget-table-row" key={category.id}><div className="budget-category-name"><span className="budget-color" style={{ background: category.color }} /><div><strong>{category.name}</strong>{category.ratePerGuestMinor && <small>{formatRupees(category.ratePerGuestMinor)} per guest assumption</small>}</div></div><div><StatusBadge tone={category.provenance === 'user_entered' ? 'good' : 'neutral'}>{category.provenance === 'user_entered' ? 'You entered' : 'Illustrative'}</StatusBadge></div><label className="budget-edit-input"><span className="sr-only">Planned amount for {category.name}</span><span>₹</span><input inputMode="decimal" value={draftValues[category.id] ?? ''} onChange={(inputEvent) => setDraftValues((current) => ({ ...current, [category.id]: inputEvent.target.value }))} /></label><div className="budget-actual-value">{category.actualMinor === null ? <span>—</span> : <strong>{formatRupees(category.actualMinor)}</strong>}</div><Button size="small" variant="secondary" disabled={savingId === category.id || String(category.plannedMinor / 100) === draftValues[category.id]} onClick={() => void saveCategory(category.id)}>{savingId === category.id ? 'Saving…' : 'Save'}</Button></div>)}</div><div className="budget-table-foot"><span>Planned total updates when each amount is saved.</span><strong>{formatRupees(total)}</strong></div></section>
    <div className="budget-tip"><span><Info size={17} /></span><p><strong>Assumptions stay editable.</strong> These numbers are examples for planning, not current market rates or vendor quotations.</p><Link to={`/events/${event.id}/ripple`}>Try a change <ArrowRight size={15} /></Link></div>
  </div>;
}

export function RipplePage({ event, onEventUpdated }: PageProps) {
  const { showToast } = useToast();
  const [field, setField] = useState<RipplePreview['inputType']>('guest_count');
  const [value, setValue] = useState(String(event.guestCount + 10));
  const [preview, setPreview] = useState<RipplePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [previewError, setPreviewError] = useState('');

  async function simulate(eventObject?: FormEvent<HTMLFormElement>) {
    eventObject?.preventDefault();
    const parsed = field === 'guest_count' ? Number(value) : parseRupeesToMinor(value);
    if (parsed === null || !Number.isSafeInteger(parsed) || parsed < 0) { setPreviewError('Enter a valid whole guest count or budget amount.'); return; }
    if (field === 'guest_count' && parsed < 1) { setPreviewError('Guest count must be at least one.'); return; }
    setPreviewError(''); setBusy(true); setPreview(null);
    try { const response = await demoApi.previewRipple(event.id, field, parsed); setPreview(response.data); }
    catch (error) { setPreviewError(error instanceof Error ? error.message : 'Could not simulate that change.'); }
    finally { setBusy(false); }
  }

  async function confirm() {
    if (!preview) return;
    setSaving(true);
    try {
      const result = await demoApi.commitRipple(preview, true);
      onEventUpdated(result.data); setDialogOpen(false); setPreview(null); setValue(field === 'guest_count' ? String(result.data.guestCount + 10) : String(result.data.budgetLimitMinor / 100));
      showToast('Change saved', 'Your plan has a new saved version.');
    } catch (error) { setDialogOpen(false); setPreviewError(error instanceof Error ? error.message : 'The change was not saved.'); showToast('Preview not saved', 'Review the current plan and run a fresh simulation.'); }
    finally { setSaving(false); }
  }

  const guestChange = field === 'guest_count';
  const proposedLabel = guestChange ? `${preview?.proposedValue ?? value} guests` : formatRupees(preview?.proposedValue ?? parseRupeesToMinor(value) ?? 0);
  return <div className="page-wrap ripple-page">
    <PageTitle eyebrow="THE CHANGE BEFORE THE CHANGE" title="Ripple engine" description="Try a what-if. See the consequences before they become your plan." action={<StatusBadge tone="plum"><Sparkles size={13} /> Deterministic preview</StatusBadge>} />
    <div className="ripple-intro-banner"><div className="ripple-orbit-mark"><span /><span /><span /><i /></div><div><strong>A plan is connected.</strong><p>Changing one detail can reach into budgets, seats, tasks and vendor follow-ups. This preview shows the path from cause to consequence.</p></div></div>
    <div className="ripple-workspace-grid">
      <section className="ripple-control-panel"><p className="eyebrow">START WITH A CHANGE</p><h2>What would you like to try?</h2><form onSubmit={(formEvent) => void simulate(formEvent)}>
        <label htmlFor="ripple-field">Choose a parameter</label><div className="select-wrap"><select id="ripple-field" value={field} onChange={(eventObject) => { const next = eventObject.target.value as RipplePreview['inputType']; setField(next); setValue(next === 'guest_count' ? String(event.guestCount + 10) : String(event.budgetLimitMinor / 100)); setPreview(null); }}><option value="guest_count">Guest count</option><option value="budget_limit">Budget limit</option></select><ChevronDown size={16} /></div>
        <label htmlFor="ripple-value">Try a new {guestChange ? 'number of guests' : 'budget limit'}</label><div className="ripple-number-input">{guestChange ? <Users size={17} /> : <span className="rupee-symbol">₹</span>}<input id="ripple-value" inputMode={guestChange ? 'numeric' : 'decimal'} value={value} onChange={(eventObject) => { setValue(eventObject.target.value); setPreview(null); }} aria-describedby="ripple-input-help" /></div><small id="ripple-input-help">{guestChange ? `Current plan: ${event.guestCount} guests` : `Current limit: ${formatRupees(event.budgetLimitMinor)}`}</small>
        <Button type="submit" size="large" className="simulate-button" disabled={busy}>{busy ? <><span className="button-spinner" /> Simulating…</> : <><Sparkles size={16} /> Show me what changes</>}</Button>
        {previewError && <p className="field-error ripple-error" role="alert">{previewError} <button type="button" onClick={() => void simulate()}>Try again</button></p>}
      </form>
      <div className="ripple-context"><span><Info size={15} /></span><p>The preview is temporary. Nothing changes in your saved plan until you confirm.</p></div>
      <div className="ripple-current-facts"><span>Current assumptions</span><div><small>Guests</small><strong>{event.guestCount}</strong></div><div><small>Venue limit</small><strong>{event.venueCapacity ?? 'Not entered'}</strong></div><div><small>Seats per table</small><strong>{event.seatsPerTable ?? 'Not entered'}</strong></div></div>
      </section>

      <section className={`ripple-result-panel${preview ? ' has-preview' : ''}`} aria-live="polite">
        {!preview && !busy && <div className="ripple-empty"><div className="empty-ripple"><span /><span /><span /><i /></div><p className="eyebrow">YOUR IMPACT TRAIL</p><h2>One change.<br /><em>A clearer picture.</em></h2><p>Choose what to change and run a preview. The saved plan will stay as it is while you explore.</p><div className="ripple-empty-steps"><span><i>1</i> Your change</span><ArrowRight size={14} /><span><i>2</i> The effects</span><ArrowRight size={14} /><span><i>3</i> Your choice</span></div></div>}
        {busy && <div className="ripple-loading"><div className="loading-orbit"><span /><span /><span /><i /></div><LoadingBlock label="Following the connections…" /><div className="loading-plan-lines"><span /><span /><span /></div></div>}
        {preview && <motion.div className="ripple-preview-content" key={preview.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <div className="preview-heading"><div><p className="eyebrow">YOUR IMPACT TRAIL</p><h2>{guestChange ? `At ${preview.proposedValue} guests` : `With a ${formatRupees(preview.proposedValue)} limit`}</h2></div><StatusBadge tone={preview.commitAllowed ? 'good' : 'warning'}>{preview.commitAllowed ? 'Ready to review' : 'Needs a change'}</StatusBadge></div>
          <div className="ripple-total-shift"><div><span>PLANNED BEFORE</span><strong>{formatRupees(preview.beforeTotalMinor)}</strong><small>{guestChange ? `${event.guestCount} guests` : 'Current plan'}</small></div><span className="shift-arrow"><ArrowRight size={18} /></span><div><span>PLANNED AFTER</span><strong>{formatRupees(preview.afterTotalMinor)}</strong><small>{preview.deltaMinor > 0 ? `+ ${formatRupees(preview.deltaMinor)}` : preview.deltaMinor < 0 ? `− ${formatRupees(Math.abs(preview.deltaMinor))}` : 'No total change'}</small></div></div>
          <div className="impact-list"><h3>What moves with it</h3>{preview.changes.map((change) => <div className="impact-row" key={change.label}><span className="impact-marker"><span /></span><div className="impact-copy"><strong>{change.label}</strong><small>{change.detail}</small></div><div className="impact-values"><span>{change.before}</span><ArrowRight size={13} /><strong>{change.after}</strong></div></div>)}</div>
          <div className="impact-links"><div><span><CalendarDays size={14} /></span><strong>Tasks to revisit</strong><div>{preview.affectedTasks.length ? preview.affectedTasks.map((item) => <small key={item}>{item}</small>) : <small>No linked tasks were found in this plan.</small>}</div></div><div><span><HeartHandshake size={14} /></span><strong>Vendor follow-ups</strong><div>{preview.affectedVendors.length ? preview.affectedVendors.map((item) => <small key={item}>{item}</small>) : <small>No vendor details need updating yet.</small>}</div></div></div>
          {preview.unknowns.length > 0 && <div className="impact-message impact-unknown"><Info size={15} /><div><strong>Still to find out</strong>{preview.unknowns.map((item) => <p key={item}>{item}</p>)}</div></div>}
          {preview.warnings.map((warning) => <div className="impact-message impact-warning" key={warning}><Check size={15} /><p>{warning}</p></div>)}
          {preview.blockers.map((blocker) => <div className="impact-message impact-blocker" key={blocker}><AlertTriangle size={16} /><div><strong>This change needs another look</strong><p>{blocker}</p></div></div>)}
          {preview.blockers.length > 0 && <div className="impact-recommendation"><span><Sparkles size={14} /></span><p><strong>Ideas to explore</strong><br />Try a lower guest count, adjust the venue capacity after confirming it, or revisit the editable budget assumptions. Run a fresh preview after each change.</p></div>}
          <div className="preview-footer"><span><Clock3 size={13} /> Preview only · not saved</span><div><Button variant="text" onClick={() => { void demoApi.cancelRipple(preview).finally(() => setPreview(null)); }}>Discard preview</Button><Button disabled={!preview.commitAllowed} onClick={() => setDialogOpen(true)}>Review and confirm <ArrowRight size={15} /></Button></div></div>
        </motion.div>}
      </section>
    </div>
    <ConfirmationDialog open={dialogOpen} title="Confirm this change?" confirmLabel="Save this change" onCancel={() => setDialogOpen(false)} onConfirm={() => void confirm()} busy={saving} disabled={!preview?.commitAllowed}>
      {preview && <><p>You’re changing {preview.inputType === 'guest_count' ? 'your guest count' : 'your budget limit'} to <strong>{proposedLabel}</strong>.</p><div className="confirm-impact-line"><span>Planned total</span><strong>{formatRupees(preview.beforeTotalMinor)} <ArrowRight size={13} /> {formatRupees(preview.afterTotalMinor)}</strong></div><p className="dialog-note"><Info size={15} /> This preview will be saved only after you confirm. Your plan is currently at version {event.versionNumber}.</p></>}
    </ConfirmationDialog>
  </div>;
}

export function MomentMapPage({ event, onEventUpdated }: PageProps) {
  const { showToast } = useToast();
  const [filter, setFilter] = useState<'all' | 'open' | 'completed'>('all');
  const [updating, setUpdating] = useState<string | null>(null);
  const phases = [...new Set(event.tasks.map((task) => task.phase))];
  const tasks = event.tasks.filter((task) => filter === 'all' || (filter === 'open' ? task.status !== 'completed' : task.status === 'completed'));
  async function toggle(taskId: string) {
    setUpdating(taskId);
    try { await demoApi.toggleTask(event.id, taskId); const latest = await demoApi.getEvent(event.id); onEventUpdated(latest.data); showToast('Task status updated', 'Saved to your event plan.'); }
    catch (error) { showToast('Could not update task', error instanceof Error ? error.message : 'Try again.'); }
    finally { setUpdating(null); }
  }
  return <div className="page-wrap map-page">
    <PageTitle eyebrow="THE WORK, IN A GENTLER ORDER" title="Moment Map" description="Milestones, next steps and the connections between them — all in one view." action={<StatusBadge tone="good">{event.tasks.filter((task) => task.status === 'completed').length} of {event.tasks.length} done</StatusBadge>} />
    <div className="map-banner"><div className="map-banner-icon"><CalendarDays size={20} /></div><div><strong>{event.eventDate ? new Date(`${event.eventDate}T12:00:00`).toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' }) : 'Date still to be decided'}</strong><p>{event.city} · Dates are suggestions until you choose them.</p></div><span className="map-date-rule"><Info size={14} /> No dates are invented</span></div>
    <div className="map-controls"><div className="map-filter-tabs" role="group" aria-label="Filter tasks">{(['all', 'open', 'completed'] as const).map((value) => <button key={value} className={filter === value ? 'active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{value === 'all' ? 'All tasks' : value === 'open' ? 'Still open' : 'Completed'}</button>)}</div><span><span className="task-legend-open" /> Open <span className="task-legend-done" /> Complete</span></div>
    <div className="timeline-layout"><div className="timeline-track-panel"><p className="eyebrow">A path through the planning</p><h2>One step at a time.</h2><div className="timeline-rail">{phases.map((phase, phaseIndex) => <div className="timeline-phase" key={phase}><div className="timeline-phase-marker"><span>{phaseIndex + 1}</span></div><div className="timeline-phase-copy"><strong>{phase}</strong><small>{event.tasks.filter((task) => task.phase === phase).length} steps</small></div><div className="timeline-phase-progress"><span style={{ width: `${event.tasks.filter((task) => task.phase === phase && task.status === 'completed').length / Math.max(event.tasks.filter((task) => task.phase === phase).length, 1) * 100}%` }} /></div></div>)}</div><div className="timeline-small-note"><span><Compass size={15} /></span><p>Suggested order follows the dependencies you have in your plan. Dates stay open when you have not added them.</p></div></div>
      <div className="task-list-panel">{phases.map((phase) => { const phaseTasks = tasks.filter((task) => task.phase === phase); if (!phaseTasks.length) return null; return <section className="task-phase-list" key={phase}><div className="task-phase-header"><h3>{phase}</h3><span>{phaseTasks.filter((task) => task.status === 'completed').length}/{phaseTasks.length}</span></div>{phaseTasks.map((task) => <article className={`task-card${task.status === 'completed' ? ' task-complete' : ''}`} key={task.id}><button type="button" className={`task-check${task.status === 'completed' ? ' checked' : ''}`} aria-label={`${task.status === 'completed' ? 'Mark incomplete' : 'Mark complete'}: ${task.title}`} disabled={updating === task.id} onClick={() => void toggle(task.id)}>{task.status === 'completed' && <Check size={14} />}</button><div className="task-card-main"><strong>{task.title}</strong><p>{task.dueLabel}{task.owner ? ` · ${task.owner}` : ' · Owner to decide'}</p>{task.dependencies.length > 0 && <div className="task-dependency"><GitCompareArrows size={12} /> Depends on {event.tasks.find((item) => item.id === task.dependencies[0])?.title ?? 'another task'}</div>}</div><StatusBadge tone={task.priority === 'high' ? 'warning' : task.status === 'completed' ? 'good' : 'neutral'}>{task.status === 'completed' ? 'You completed' : task.priority === 'high' ? 'Soon' : 'In view'}</StatusBadge><span className="task-card-date">{task.dueLabel}</span></article>)}</section>})}{tasks.length === 0 && <EmptyState title="Nothing in this view" detail="Try another filter to find tasks in your plan." />}</div></div>
  </div>;
}

export function VendorsPage({ event, onEventUpdated }: PageProps) {
  const { showToast } = useToast();
  const [category, setCategory] = useState('');
  const [name, setName] = useState('');
  const [savingVendor, setSavingVendor] = useState<string | null>(null);
  const [savingNew, setSavingNew] = useState(false);
  const [quotes, setQuotes] = useState<Record<string, string>>(() => Object.fromEntries(event.vendors.map((vendor) => [vendor.id, vendor.quoteMinor ? String(vendor.quoteMinor / 100) : ''])));
  const statuses: VendorStatus[] = ['to_find', 'contacted', 'shortlisted', 'selected'];
  async function saveVendor(vendor: Vendor, updates: Partial<Pick<Vendor, 'status' | 'name' | 'contact' | 'quoteMinor'>>) {
    setSavingVendor(vendor.id);
    try { await demoApi.updateVendor(event.id, vendor.id, updates); const updated = await demoApi.getEvent(event.id); onEventUpdated(updated.data); showToast('Vendor details saved', 'This entry is user-managed.'); }
    catch (error) { showToast('Could not save vendor details', error instanceof Error ? error.message : 'Try again.'); }
    finally { setSavingVendor(null); }
  }
  async function addVendor(eventObject: FormEvent<HTMLFormElement>) {
    eventObject.preventDefault(); if (category.trim().length < 2) return;
    setSavingNew(true);
    try { await demoApi.addVendor(event.id, category, name); const updated = await demoApi.getEvent(event.id); onEventUpdated(updated.data); setCategory(''); setName(''); showToast('Checklist category added', 'Supplier details are still yours to enter.'); }
    catch (error) { showToast('Could not add category', error instanceof Error ? error.message : 'Try again.'); }
    finally { setSavingNew(false); }
  }
  return <div className="page-wrap vendor-page">
    <PageTitle eyebrow="THE PEOPLE BEHIND THE DAY" title="Vendor workspace" description="Keep categories, contacts and quotations together. You decide what is confirmed." action={<StatusBadge tone="warning">No vendor data is verified</StatusBadge>} />
    <div className="vendor-disclosure"><span><Info size={17} /></span><p><strong>Sample assumptions are not supplier quotes.</strong> Suggested categories are a checklist only. Contact details and quotations below are entered by you.</p></div>
    <div className="vendor-overview-strip"><div><span>Checklist progress</span><strong>{event.vendors.filter((vendor) => vendor.status === 'selected').length} <small>of {event.vendors.length} selected by you</small></strong></div><div><span>Quotations entered</span><strong>{event.vendors.filter((vendor) => vendor.quoteMinor !== null).length} <small>user-entered only</small></strong></div><div><span>Still to find</span><strong>{event.vendors.filter((vendor) => vendor.status === 'to_find').length} <small>categories to review</small></strong></div><div className="vendor-overview-art"><HeartHandshake size={31} /><span>Good work is a team effort.</span></div></div>
    <section className="vendor-list-panel"><SectionHeader title="Your vendor checklist" detail="Change status as you reach out. “Selected” records your choice, not an external booking." /><div className="vendor-table-head"><span>Category & details</span><span>Planning estimate</span><span>Quote you entered</span><span>Status</span></div>{event.vendors.map((vendor) => <article className="vendor-row" key={vendor.id}><div className="vendor-identity"><span className="vendor-avatar"><HeartHandshake size={17} /></span><div><strong>{vendor.category}</strong><label className="sr-only" htmlFor={'vendor-name-' + vendor.id}>Supplier name for {vendor.category}</label><input id={'vendor-name-' + vendor.id} className="vendor-detail-input" defaultValue={vendor.name ?? ''} placeholder="Supplier name" maxLength={100} disabled={savingVendor === vendor.id} onBlur={(inputEvent) => { const value = inputEvent.currentTarget.value.trim() || null; if (value !== vendor.name) void saveVendor(vendor, { name: value }); }} /><label className="sr-only" htmlFor={'vendor-contact-' + vendor.id}>Contact details for {vendor.category}</label><input id={'vendor-contact-' + vendor.id} className="vendor-detail-input" defaultValue={vendor.contact ?? ''} placeholder="Contact name, phone or email" maxLength={160} disabled={savingVendor === vendor.id} onBlur={(inputEvent) => { const value = inputEvent.currentTarget.value.trim() || null; if (value !== vendor.contact) void saveVendor(vendor, { contact: value }); }} /><em className={vendor.provenance === 'user_entered' ? 'provenance-user' : ''}>{vendor.provenance === 'user_entered' ? 'User-entered detail' : 'Illustrative checklist item'}</em></div></div><div className="vendor-estimate">{vendor.estimateMinor === null ? <span>Not estimated</span> : <><strong>{formatRupees(vendor.estimateMinor)}</strong><small>Planning assumption</small></>}</div><label className="vendor-quote-input"><span className="sr-only">Quote entered by you for {vendor.category}</span><span>₹</span><input inputMode="decimal" placeholder="Add quote" value={quotes[vendor.id] ?? ''} onChange={(inputEvent) => setQuotes((current) => ({ ...current, [vendor.id]: inputEvent.target.value }))} onBlur={() => { const amount = parseRupeesToMinor(quotes[vendor.id] ?? ''); if (amount !== null && amount !== vendor.quoteMinor) void saveVendor(vendor, { quoteMinor: amount }); }} /><small>{vendor.quoteMinor === null ? 'Not entered' : 'Entered by you'}</small></label><div className="vendor-status-cell"><label className="sr-only" htmlFor={`vendor-status-${vendor.id}`}>Status for {vendor.category}</label><select id={`vendor-status-${vendor.id}`} value={vendor.status} disabled={savingVendor === vendor.id} onChange={(changeEvent) => void saveVendor(vendor, { status: changeEvent.target.value as VendorStatus })}>{statuses.map((status) => <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>)}</select>{savingVendor === vendor.id && <small>Saving…</small>}</div></article>)}{event.vendors.length === 0 && <EmptyState title="Your checklist starts here" detail="Add a category to keep follow-ups and your own contact details together." />}</section>
    <form className="add-vendor-form" onSubmit={(eventObject) => void addVendor(eventObject)}><div><span className="add-vendor-icon"><Plus size={18} /></span><div><strong>Add a checklist category</strong><p>Keep it simple. Add a supplier name later when you have one.</p></div></div><label><span className="sr-only">New vendor category</span><input value={category} onChange={(eventObject) => setCategory(eventObject.target.value)} placeholder="e.g. Flowers, transport, lighting" minLength={2} maxLength={80} required /></label><label><span className="sr-only">Supplier name, optional</span><input value={name} onChange={(eventObject) => setName(eventObject.target.value)} placeholder="Supplier name (optional)" maxLength={100} /></label><Button type="submit" variant="secondary" disabled={savingNew || category.trim().length < 2}>{savingNew ? 'Adding…' : 'Add to checklist'} <ArrowRight size={15} /></Button></form>
  </div>;
}

export function ScenariosPage({ event }: PageProps) {
  const { showToast } = useToast();
  const [inputs, setInputs] = useState([String(Math.max(1, event.guestCount - 20)), String(event.guestCount + 50)]);
  const [results, setResults] = useState<ScenarioResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  async function compare() {
    const values = inputs.map(Number);
    if (values.some((value) => !Number.isInteger(value) || value < 1 || value > 10000)) { showToast('Check both guest counts', 'Enter a whole number between 1 and 10,000.'); return; }
    setLoading(true);
    try { const response = await demoApi.compareScenarios(event.id, [values[0]!, values[1]!, event.guestCount]); setResults(response.data); }
    catch (error) { showToast('Could not compare scenarios', error instanceof Error ? error.message : 'Try again.'); }
    finally { setLoading(false); }
  }
  const maxTotal = Math.max(...(results ?? []).map((result) => result.totalMinor), 1);
  return <div className="page-wrap scenarios-page">
    <PageTitle eyebrow="A FEW WAYS IT COULD GO" title="Compare plans" description="Explore up to two alternatives against the plan you have now. These projections do not save changes." action={<StatusBadge tone="neutral">Read-only comparison</StatusBadge>} />
    <div className="scenario-disclosure"><Info size={17} /><p>Each option runs against the same saved version. Choose one to open Ripple Engine and review it before confirming.</p></div>
    <div className="scenario-input-panel"><div><p className="eyebrow">TRY TWO GUEST COUNTS</p><h2>How might the day feel?</h2><p>We’ll compare budget, seating and capacity using the current illustrative assumptions.</p></div><div className="scenario-controls"><label>Option one<input value={inputs[0]} inputMode="numeric" onChange={(event) => setInputs((current) => [event.target.value, current[1]])} /><small>guests</small></label><label>Option two<input value={inputs[1]} inputMode="numeric" onChange={(event) => setInputs((current) => [current[0], event.target.value])} /><small>guests</small></label><Button onClick={() => void compare()} disabled={loading}>{loading ? 'Comparing…' : 'Compare options'} <GitCompareArrows size={16} /></Button></div></div>
    {loading && <LoadingBlock label="Comparing the options…" />}
    {results && !loading && <section className="scenario-results"><div className="scenario-results-head"><div><p className="eyebrow">SIDE BY SIDE</p><h2>Same celebration, different shape.</h2></div><StatusBadge tone="warning">Illustrative projection</StatusBadge></div><div className="scenario-chart-area" role="img" aria-label="Bar chart comparing projected plan totals for event scenarios"><div className="scenario-y-labels"><span>{formatRupees(maxTotal)}</span><span>{formatRupees(maxTotal / 2)}</span><span>₹0</span></div><div className="scenario-chart-grid"><span /><span /><span /><div className="scenario-bars">{results.map((result, index) => <div className="scenario-bar-column" key={`${result.name}-${index}`}><div className="scenario-bar-value">{formatRupees(result.totalMinor)}</div><div className={`scenario-bar scenario-bar-${index}`} style={{ height: `${Math.max(8, result.totalMinor / maxTotal * 100)}%` }} /><strong>{result.name}</strong><small>{result.guestCount} guests</small></div>)}</div></div></div><div className="scenario-table-wrap"><table className="scenario-table"><caption className="sr-only">Projected event scenario comparison</caption><thead><tr><th scope="col">Projection</th>{results.map((result, index) => <th scope="col" key={`${result.name}-heading-${index}`}>{result.name}</th>)}</tr></thead><tbody><tr><th scope="row">Projected plan</th>{results.map((result, index) => <td key={`total-${index}`}>{formatRupees(result.totalMinor)}</td>)}</tr><tr><th scope="row">Change vs current</th>{results.map((result, index) => <td key={`delta-${index}`} className={result.deltaMinor > 0 ? 'delta-up' : 'delta-down'}>{result.deltaMinor > 0 ? '+' : ''}{formatRupees(result.deltaMinor)}</td>)}</tr><tr><th scope="row">Tables to arrange</th>{results.map((result, index) => <td key={`tables-${index}`}>{result.tables === null ? 'Needs input' : result.tables}</td>)}</tr><tr><th scope="row">Venue capacity</th>{results.map((result, index) => <td key={`capacity-${index}`}><StatusBadge tone={result.capacityState === 'exceeded' ? 'warning' : result.capacityState === 'unknown' ? 'neutral' : 'good'}>{result.capacityState}</StatusBadge></td>)}</tr></tbody></table></div><div className="scenario-actions"><p>These are projections only. A saved change needs a fresh Ripple preview and your confirmation.</p><Link className="button button-primary" to={`/events/${event.id}/ripple`}>Review a change <ArrowRight size={15} /></Link></div></section>}
    {!results && !loading && <div className="scenario-empty"><div className="scenario-empty-mark"><GitCompareArrows size={23} /></div><h2>Explore a little before deciding.</h2><p>Choose two attendance options above. Your current plan stays untouched while you compare.</p></div>}
  </div>;
}
