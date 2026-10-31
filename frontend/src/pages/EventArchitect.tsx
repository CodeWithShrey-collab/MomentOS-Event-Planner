import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, CalendarDays, Check, CircleHelp, Compass, Leaf, Sparkles, Users, Wallet } from 'lucide-react';
import { demoApi, parseRupeesToMinor, formatRupees } from '../services/demoApi';
import { TYPE_COPY } from '../data/demoData';
import type { EventDraftInput, EventType, PlanDraft } from '../types';
import { Brand } from '../components/AppShell';
import { Button, ConfirmationDialog, DemoBanner, LoadingBlock, StatusBadge } from '../components/ui';
import { useToast } from '../hooks/useToast';
import { categoryColorToken } from '../theme';
import { ApiError } from '../services/apiClient';

const priorities = ['Good food', 'Time with family', 'A relaxed pace', 'Keep to budget', 'Accessibility', 'A little unexpected magic'];

export function EventArchitect() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const initialType = (['wedding', 'birthday', 'community'].includes(searchParams.get('type') ?? '') ? searchParams.get('type') : 'wedding') as EventType;
  const [step, setStep] = useState<'form' | 'generating' | 'review' | 'saving'>('form');
  const [type, setType] = useState<EventType>(initialType);
  const [title, setTitle] = useState('');
  const [date, setDate] = useState('');
  const [city, setCity] = useState('Nagpur');
  const [guests, setGuests] = useState('150');
  const [budget, setBudget] = useState('600000');
  const [theme, setTheme] = useState('');
  const [notes, setNotes] = useState('');
  const [selectedPriorities, setSelectedPriorities] = useState<string[]>(['Good food', 'A relaxed pace']);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<PlanDraft | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const copy = TYPE_COPY[type];
  const nextDateMin = useMemo(() => new Date().toISOString().slice(0, 10), []);

  function validate(): EventDraftInput | null {
    const nextErrors: Record<string, string> = {};
    const guestsValue = Number(guests);
    const budgetMinor = parseRupeesToMinor(budget);
    if (title.trim().length < 2) nextErrors.title = 'Give your event a name of at least two characters.';
    if (!city.trim()) nextErrors.city = 'Add a city or leave it open as “To be decided”.';
    if (!Number.isInteger(guestsValue) || guestsValue < 1 || guestsValue > 10000) nextErrors.guests = 'Enter a guest count between 1 and 10,000.';
    if (budgetMinor === null || budgetMinor <= 0) nextErrors.budget = 'Enter a positive budget, for example 80000.';
    if (date && date < nextDateMin) nextErrors.date = 'Choose today or a future date.';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return null;
    return { eventType: type, title: title.trim(), eventDate: date, city: city.trim(), guestCount: guestsValue, budgetLimitMinor: budgetMinor!, priorities: selectedPriorities, theme: theme.trim(), notes: notes.trim() };
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const input = validate();
    if (!input) return;
    setStep('generating');
    try {
      const created = await demoApi.createEvent(input);
      setEventId(created.data.id);
      const result = await demoApi.generatePlanDraft(created.data.id, input);
      setDraft(result.data);
      setStep('review');
    } catch (error) {
      setStep('form');
      if (error instanceof ApiError && error.code === 'ai_daily_limit' && error.retryAfterSeconds) {
        const resumesAt = new Date(Date.now() + error.retryAfterSeconds * 1000);
        const localTime = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }).format(resumesAt);
        showToast('Daily AI limit reached', `Planning can resume at ${localTime}.`, 'error');
      } else {
        showToast('We could not prepare that plan', error instanceof Error ? error.message : 'Try again in a moment.', 'error');
      }
    }
  }

  async function handleConfirm() {
    if (!draft || !eventId) return;
    setStep('saving');
    try {
      const saved = await demoApi.commitPlanDraft(draft, true);
      setConfirmOpen(false);
      showToast('Your plan is saved', 'You can change any detail as you go.');
      navigate(`/events/${saved.data.id}`);
    } catch (error) {
      setStep('review');
      setConfirmOpen(false);
      showToast('The plan was not saved', error instanceof Error ? error.message : 'Please try again.', 'error');
    }
  }

  function togglePriority(value: string) {
    setSelectedPriorities((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  }

  return (
    <div className="architect-page">
      <header className="architect-nav"><Brand /><div className="architect-nav-right"><DemoBanner compact /><span className="architect-step-label">{step === 'review' || step === 'saving' ? 'Your plan is ready to review' : 'A few details to begin'}</span></div></header>
      <main className="architect-main">
        <Link className="back-link" to="/"><ArrowLeft size={16} /> Back to MomentOS</Link>
        {step === 'generating' ? <div className="architect-loading"><div className="architect-loading-mark"><Sparkles size={27} /></div><p className="eyebrow">Preparing your plan</p><h1>Gathering your<br /><em>first thoughts.</em></h1><p className="page-description">We’re shaping an editable starting point from your details and keeping the assumptions visible.</p><div className="loading-plan-lines"><span /><span /><span /></div><LoadingBlock label="Building your blueprint…" /><Button variant="text" onClick={() => { setStep('form'); }}>Cancel</Button></div> : null}

        {step === 'form' ? <div className="architect-grid">
          <div className="architect-heading"><p className="eyebrow">A thoughtful beginning</p><h1>Let’s make this<br /><em>feel like yours.</em></h1><p>Start with what you know. The plan can hold the open questions while you decide.</p><div className="architect-side-note"><span><Compass size={18} /></span><p><strong>Nothing is set in stone.</strong><br />Every suggestion is editable before it becomes part of your plan.</p></div></div>
          <form className="architect-form form-surface" onSubmit={handleGenerate} noValidate>
            <DemoBanner compact />
            <fieldset className="event-type-select"><legend>What are we celebrating?</legend><div className="event-type-options">{(['wedding', 'birthday', 'community'] as EventType[]).map((option) => <button key={option} type="button" className={`event-type-option${type === option ? ' selected' : ''}`} aria-pressed={type === option} onClick={() => setType(option)}><span className={`event-type-icon kind-${option}`}>{option === 'wedding' ? <Sparkles size={17} /> : option === 'birthday' ? <CalendarDays size={17} /> : <Users size={17} />}</span><strong>{TYPE_COPY[option].label}</strong>{type === option && <Check size={14} className="type-check" />}</button>)}</div></fieldset>
            <div className="form-field"><label htmlFor="event-title">Give it a name</label><input id="event-title" value={title} onChange={(event) => setTitle(event.target.value)} placeholder={type === 'wedding' ? 'A garden wedding' : type === 'birthday' ? 'A little wonder, a lot of joy' : 'The neighborhood table'} aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? 'title-error' : undefined} />{errors.title && <span className="field-error" id="title-error">{errors.title}</span>}</div>
            <div className="form-row"><div className="form-field"><label htmlFor="event-date">Date <span>if you know it</span></label><input id="event-date" type="date" min={nextDateMin} value={date} onChange={(event) => setDate(event.target.value)} aria-invalid={Boolean(errors.date)} aria-describedby={errors.date ? 'date-error' : undefined} />{errors.date && <span className="field-error" id="date-error" role="alert">{errors.date}</span>}</div><div className="form-field"><label htmlFor="event-city">City</label><input id="event-city" value={city} onChange={(event) => setCity(event.target.value)} placeholder="Nagpur" aria-invalid={Boolean(errors.city)} aria-describedby={errors.city ? 'city-error' : undefined} />{errors.city && <span className="field-error" id="city-error" role="alert">{errors.city}</span>}</div></div>
            <div className="form-row"><div className="form-field"><label htmlFor="event-guests">Guests or attendees</label><div className="input-with-icon"><Users size={16} aria-hidden="true" /><input id="event-guests" inputMode="numeric" value={guests} onChange={(event) => setGuests(event.target.value)} aria-invalid={Boolean(errors.guests)} aria-describedby={errors.guests ? 'guests-error' : undefined} /></div>{errors.guests && <span className="field-error" id="guests-error" role="alert">{errors.guests}</span>}</div><div className="form-field"><label htmlFor="event-budget">Budget <span>in rupees</span></label><div className="input-with-icon"><Wallet size={16} aria-hidden="true" /><input id="event-budget" inputMode="decimal" value={budget} onChange={(event) => setBudget(event.target.value)} aria-invalid={Boolean(errors.budget)} aria-describedby={errors.budget ? 'budget-error' : undefined} /></div>{errors.budget && <span className="field-error" id="budget-error" role="alert">{errors.budget}</span>}</div></div>
            <fieldset className="priority-fieldset"><legend>What matters most? <span>Choose a few</span></legend><div className="priority-options">{priorities.map((priority) => <label key={priority} className={`priority-option${selectedPriorities.includes(priority) ? ' priority-selected' : ''}`}><input type="checkbox" checked={selectedPriorities.includes(priority)} onChange={() => togglePriority(priority)} /><span>{priority}</span></label>)}</div></fieldset>
            <div className="form-field"><label htmlFor="event-theme">A feeling or theme <span>optional</span></label><div className="input-with-icon"><Leaf size={16} /><input id="event-theme" value={theme} onChange={(event) => setTheme(event.target.value)} placeholder="Garden at dusk, a little vintage…" /></div></div>
            <div className="form-field"><label htmlFor="event-notes">Tell us a little more <span>anything on your mind</span></label><textarea id="event-notes" rows={4} maxLength={1000} value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="What would make the day feel special? What is still undecided?" /><div className="textarea-foot"><span><CircleHelp size={13} />{import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? 'Saved only in this browser demo.' : 'Used only to prepare your event plan.'}</span><small>{notes.length}/1000</small></div></div>
            <Button type="submit" size="large" className="form-submit">Prepare my plan <ArrowRight size={17} /></Button>
            <p className="form-disclaimer">A clear first draft, not a commitment. All amounts are editable illustrative assumptions.</p>
          </form>
        </div> : null}

        {(step === 'review' || step === 'saving') && draft ? <div className="review-layout">
          <div className="review-intro"><p className="eyebrow">A first plan for {title || copy.label.toLowerCase()}</p><h1>Here’s a place<br />to <em>begin.</em></h1><p>Take a look through the assumptions and open questions. Nothing is saved as your plan until you confirm.</p><div className="review-ai-status"><span><Sparkles size={16} /></span><div><strong>{draft.aiStatus === 'live' ? 'GPT-6 Luna · live blueprint' : draft.aiStatus === 'mock' ? 'Mock provider · no live request' : 'Offline demo · sample blueprint'}</strong><small>{draft.aiStatus === 'live' ? 'Generated from your event brief. Review every suggestion before saving.' : draft.aiStatus === 'mock' ? 'A structured test response passed through Flask. OpenAI was not called.' : 'No live AI request was made. Review the illustrative assumptions before saving.'}</small></div></div><button className="back-link review-edit-link" onClick={() => setStep('form')}><ArrowLeft size={15} /> Edit event details</button></div>
          <div className="review-board">
            <div className="review-board-head"><div><span className="board-overline">YOUR EVENT BRIEF</span><h2>{title}</h2><p>{city || 'City to be decided'}{date ? ` · ${new Date(`${date}T12:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })}` : ' · Date to be decided'} · {guests} guests</p></div><StatusBadge tone="plum">Editable draft</StatusBadge></div>
            <div className="review-concept"><span className="bento-kicker">A starting thought</span><textarea aria-label="Edit plan concept" value={draft.concept} onChange={(event) => setDraft({ ...draft, concept: event.target.value })} rows={3} /></div>
            <div className="review-assumptions"><strong>Keep these in view</strong>{draft.assumptions.map((item) => <p key={item}><span><Check size={13} /></span>{item}</p>)}</div>
            <div className="review-budget"><div className="section-header"><div><h2>Suggested budget shape</h2><p>Illustrative amounts · edit before saving</p></div><Wallet size={17} /></div>{draft.categories.slice(0, 5).map((category, index) => <div className="review-budget-row" key={category.id}><span className="budget-color" style={{ background: categoryColorToken(category.id, index) }} /><span>{category.name}</span><strong>{formatRupees(category.plannedMinor)}</strong></div>)}{draft.budgetItems?.length ? <div className="review-budget-items"><span className="review-budget-items-title">ITEM ASSUMPTIONS</span>{draft.budgetItems.map((item) => <div className="review-budget-item" key={item.id}><div><strong>{item.label}</strong><small>{item.quantityBasis === 'guest_count' && item.quantity !== null && item.unitRateMinor !== null ? `${item.quantity.toLocaleString('en-IN')} guests × ${formatRupees(item.unitRateMinor)} per guest` : item.quantity !== null && item.unitRateMinor !== null ? `${item.quantity.toLocaleString('en-IN')} × ${formatRupees(item.unitRateMinor)} each` : 'Editable planning estimate'}</small></div><strong>{formatRupees(item.plannedMinor)}</strong></div>)}</div> : null}</div>
            <div className="review-tasks"><div className="section-header"><div><h2>A few next steps</h2><p>Suggestions · none are marked complete</p></div><CalendarDays size={17} /></div>{draft.tasks.slice(0, 3).map((task) => <div className="review-task-row" key={task.id}><span className="task-circle" /><span>{task.title}</span><small>{task.phase}</small></div>)}</div>
            <div className="review-unknowns"><strong>Still to decide</strong><div>{draft.unknowns.map((item) => <StatusBadge key={item}>{item}</StatusBadge>)}</div></div>
            <div className="review-board-actions"><Button variant="secondary" onClick={() => setStep('form')}><ArrowLeft size={15} /> Keep editing</Button><Button size="large" onClick={() => setConfirmOpen(true)}>Save this plan <ArrowRight size={17} /></Button></div>
          </div>
          <section className="review-ideas"><span className="bento-kicker">A few personal touches</span><div>{draft.ideas.map((idea) => <p key={idea}><Sparkles size={15} />{idea}</p>)}</div></section>
        </div> : null}
      </main>
      <footer className="architect-footer"><span>momentOS</span><span>Make room for the moment.</span></footer>
      <ConfirmationDialog open={confirmOpen} title="Save this as your plan?" confirmLabel="Confirm and save" onCancel={() => setConfirmOpen(false)} onConfirm={handleConfirm} busy={step === 'saving'}>
        <p>{demoApi.mode === 'offline_demo' ? 'Your editable plan will be saved only in this browser demo.' : 'Your editable plan will be saved to your event workspace.'} You can change it later.</p><p className="dialog-note"><Sparkles size={15} /> {draft?.aiStatus === 'live' ? 'GPT-6 Luna prepared this blueprint. It becomes your saved plan only after you confirm.' : draft?.aiStatus === 'mock' ? 'This is a structured mock response for testing; no live OpenAI request was made.' : 'This blueprint is an offline demo result; no live OpenAI response was generated.'}</p>
      </ConfirmationDialog>
    </div>
  );
}
