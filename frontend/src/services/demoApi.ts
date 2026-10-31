import { DEMO_EVENTS, totalPlanned } from '../data/demoData';
import type {
  ApiEnvelope, BudgetCategory, EventDraftInput, EventRecord, EventTask, PlanDraft,
  RipplePreview, ScenarioResult, Vendor, VendorStatus,
} from '../types';

const STORAGE_KEY = 'momentos.offline-demo.events.v1';
const pause = (duration = 320) => new Promise<void>((resolve) => window.setTimeout(resolve, duration));
const uuid = () => globalThis.crypto?.randomUUID?.() ?? `demo-${Date.now()}-${Math.random().toString(16).slice(2)}`;
const clone = <T,>(value: T): T => structuredClone(value);

function readStore(): EventRecord[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as EventRecord[];
  } catch {
    // Browser storage can be disabled; use the in-memory fixtures for this tab.
  }
  return clone(DEMO_EVENTS);
}

let eventStore = readStore();
function persist(): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(eventStore));
  } catch {
    // The UI remains usable for this tab even when local persistence is unavailable.
  }
}

export class DemoApiError extends Error {
  constructor(public code: string, message: string, public status = 422) {
    super(message);
    this.name = 'DemoApiError';
  }
}

function envelope<T>(data: T): ApiEnvelope<T> {
  return { data, request_id: uuid() };
}

function findEvent(id: string): EventRecord {
  const event = eventStore.find((candidate) => candidate.id === id);
  if (!event) throw new DemoApiError('not_found', 'This event is no longer in the demo workspace.', 404);
  return event;
}

export function resetDemoDataForTests(): void {
  eventStore = clone(DEMO_EVENTS);
  try { localStorage.removeItem(STORAGE_KEY); } catch { /* Storage is optional in tests. */ }
}

export const offlineDemoApi = {
  mode: 'offline_demo' as const,

  async listEvents(): Promise<ApiEnvelope<EventRecord[]>> {
    await pause(160);
    return envelope(clone(eventStore));
  },

  async getEvent(eventId: string): Promise<ApiEnvelope<EventRecord>> {
    await pause(180);
    return envelope(clone(findEvent(eventId)));
  },

  async createEvent(input: EventDraftInput): Promise<ApiEnvelope<EventRecord>> {
    await pause(280);
    const event: EventRecord = {
      id: uuid(), eventType: input.eventType, title: input.title.trim(), currency: 'INR',
      budgetLimitMinor: input.budgetLimitMinor, eventDate: input.eventDate, city: input.city.trim(),
      guestCount: input.guestCount, venueCapacity: null, seatsPerTable: null, invitationUnit: 'unknown',
      revision: 0, versionNumber: 0, createdAt: new Date().toISOString().slice(0, 10), categories: [], tasks: [], vendors: [],
      concept: '', priorities: input.priorities, theme: input.theme.trim(), notes: input.notes.trim(), accepted: false,
    };
    eventStore = [event, ...eventStore];
    persist();
    return envelope(clone(event));
  },

  async generatePlanDraft(eventId: string, _input?: EventDraftInput): Promise<ApiEnvelope<PlanDraft>> {
    void _input;
    await pause(900);
    const event = findEvent(eventId);
    const example = DEMO_EVENTS.find((candidate) => candidate.eventType === event.eventType) ?? DEMO_EVENTS[0]!;
    const categories = clone(example.categories);
    const food = categories.find((category) => category.id === 'food');
    if (food?.ratePerGuestMinor) food.plannedMinor = food.ratePerGuestMinor * event.guestCount;
    const unscaledTotal = totalPlanned(categories);
    const scale = unscaledTotal > 0 ? event.budgetLimitMinor / unscaledTotal : 1;
    for (const category of categories) {
      if (!category.ratePerGuestMinor) category.plannedMinor = Math.round(category.plannedMinor * scale);
      category.actualMinor = null;
    }
    return envelope({
      eventId,
      concept: event.theme ? `${event.theme}: a celebration shaped around ${event.priorities.slice(0, 2).join(' and ') || 'what matters most'}.` : example.concept,
      assumptions: ['Category amounts are editable illustrative assumptions.', 'Venue capacity, task dates and vendor details remain open until you add them.'],
      unknowns: ['Venue capacity', 'Invitation quantity rule', 'Confirmed vendor quotations'],
      categories,
      tasks: clone(example.tasks).map((task) => ({ ...task, status: 'not_started', owner: null })),
      vendors: clone(example.vendors).map((vendor) => ({ ...vendor, name: null, contact: null, status: 'to_find', quoteMinor: null })),
      ideas: [
        `${event.priorities[0] ?? 'A relaxed welcome'} gets first attention in the plan.`,
        `Use “${event.theme || example.theme}” as a visual thread, then keep the details editable.`,
        'Leave a little room in the schedule for the moments that happen naturally.',
      ],
      aiStatus: 'offline_demo',
    });
  },

  async commitPlanDraft(draft: PlanDraft, confirmed: boolean): Promise<ApiEnvelope<EventRecord>> {
    await pause(360);
    if (!confirmed) throw new DemoApiError('confirmation_required', 'Review and confirm the plan before saving.', 409);
    const event = findEvent(draft.eventId);
    if (event.accepted) throw new DemoApiError('stale_event_version', 'This event already has a saved plan. Reload it before editing.', 412);
    event.concept = draft.concept;
    event.categories = clone(draft.categories);
    event.tasks = clone(draft.tasks);
    event.vendors = clone(draft.vendors);
    event.accepted = true;
    event.versionNumber = 1;
    event.revision += 1;
    persist();
    return envelope(clone(event));
  },

  async updateCategory(eventId: string, categoryId: string, plannedMinor: number): Promise<ApiEnvelope<EventRecord>> {
    await pause(240);
    const event = findEvent(eventId);
    const category = event.categories.find((item) => item.id === categoryId);
    if (!category) throw new DemoApiError('not_found', 'Budget category not found.', 404);
    if (!Number.isSafeInteger(plannedMinor) || plannedMinor < 0) throw new DemoApiError('validation_failed', 'Enter a valid non-negative amount.');
    category.plannedMinor = plannedMinor;
    category.provenance = 'user_entered';
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(event));
  },

  async toggleTask(eventId: string, taskId: string): Promise<ApiEnvelope<EventTask>> {
    await pause(220);
    const event = findEvent(eventId);
    const task = event.tasks.find((item) => item.id === taskId);
    if (!task) throw new DemoApiError('not_found', 'Task not found.', 404);
    task.status = task.status === 'completed' ? 'not_started' : 'completed';
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(task));
  },

  async updateVendor(eventId: string, vendorId: string, updates: Partial<Pick<Vendor, 'status' | 'name' | 'contact' | 'note'>>): Promise<ApiEnvelope<Vendor>> {
    await pause(220);
    const event = findEvent(eventId);
    const vendor = event.vendors.find((item) => item.id === vendorId);
    if (!vendor) throw new DemoApiError('not_found', 'Vendor checklist item not found.', 404);
    Object.assign(vendor, updates);
    vendor.provenance = 'user_entered';
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(vendor));
  },

  async saveVendorQuote(eventId: string, vendorId: string, amountMinor: number, currency: string): Promise<ApiEnvelope<EventRecord>> {
    await pause(220);
    const event = findEvent(eventId);
    const vendor = event.vendors.find((item) => item.id === vendorId);
    if (!vendor) throw new DemoApiError('not_found', 'Vendor checklist item not found.', 404);
    if (currency !== event.currency || !Number.isSafeInteger(amountMinor) || amountMinor < 0) {
      throw new DemoApiError('validation_failed', 'Enter a valid quote amount in the event currency.', 422);
    }
    vendor.quoteMinor = amountMinor;
    vendor.provenance = 'user_entered';
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(event));
  },

  async addVendor(eventId: string, category: string, name = ''): Promise<ApiEnvelope<Vendor>> {
    await pause(230);
    const event = findEvent(eventId);
    const vendor: Vendor = {
      id: uuid(), category: category.trim(), name: name.trim() || null, contact: null, status: 'to_find',
      estimateMinor: null, quoteMinor: null, provenance: name.trim() ? 'user_entered' : 'suggested', note: name.trim() ? 'Added by you.' : 'Checklist category · no supplier selected.',
    };
    event.vendors = [...event.vendors, vendor];
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(vendor));
  },

  async previewRipple(eventId: string, inputType: RipplePreview['inputType'], proposedValue: number): Promise<ApiEnvelope<RipplePreview>> {
    await pause(420);
    const event = findEvent(eventId);
    if (!Number.isSafeInteger(proposedValue) || proposedValue < 0) throw new DemoApiError('validation_failed', 'Choose a valid value.');
    const currentTotal = totalPlanned(event.categories);
    const catering = event.categories.find((category) => category.ratePerGuestMinor !== undefined);
    let afterTotal = currentTotal;
    const changes: RipplePreview['changes'] = [];
    const affectedTasks = new Set<string>();
    const affectedVendors = new Set<string>();
    const warnings: string[] = [];
    const blockers: string[] = [];
    const unknowns: string[] = [];
    let proposedBudget = event.budgetLimitMinor;

    if (inputType === 'guest_count') {
      changes.push({ label: 'Guest count', before: String(event.guestCount), after: String(proposedValue), detail: 'The change begins here.' });
      if (catering?.ratePerGuestMinor !== undefined) {
        const before = catering.ratePerGuestMinor * event.guestCount;
        const after = catering.ratePerGuestMinor * proposedValue;
        afterTotal += after - before;
        changes.push({ label: 'Food & catering', before: formatRupees(before), after: formatRupees(after), detail: `${formatRupees(catering.ratePerGuestMinor)} per guest · illustrative assumption`, category: catering.name });
        if (before !== after) {
          for (const task of event.tasks.filter((item) => item.categoryId === catering.id || item.title.toLowerCase().includes('menu'))) affectedTasks.add(task.title);
          for (const vendor of event.vendors.filter((item) => item.category.toLowerCase().includes('cater'))) affectedVendors.add(vendor.category);
        }
      } else {
        warnings.push('Catering cost needs a per-guest rate before it can be recalculated.');
      }
      if (event.seatsPerTable) {
        const before = Math.ceil(event.guestCount / event.seatsPerTable);
        const after = Math.ceil(proposedValue / event.seatsPerTable);
        changes.push({ label: 'Tables to arrange', before: String(before), after: String(after), detail: `${event.seatsPerTable} seats per table · editable assumption` });
      } else {
        unknowns.push('Seating needs a seats-per-table assumption.');
      }
      if (event.venueCapacity === null) unknowns.push('Venue capacity has not been entered.');
      else if (proposedValue > event.venueCapacity) blockers.push(`The proposed ${proposedValue} guests exceed the venue limit of ${event.venueCapacity}.`);
      else warnings.push(`The proposed ${proposedValue} guests are within the entered venue limit of ${event.venueCapacity}.`);
      if (event.invitationUnit === 'unknown') unknowns.push('Invitation count needs a per-person or per-household rule.');
    } else {
      proposedBudget = proposedValue;
      changes.push({ label: 'Budget limit', before: formatRupees(event.budgetLimitMinor), after: formatRupees(proposedValue), detail: 'The plan total is recalculated against this limit.' });
    }

    if (afterTotal > proposedBudget) blockers.push(`${formatRupees(afterTotal - proposedBudget)} above the proposed budget limit.`);
    else warnings.push(`${formatRupees(proposedBudget - afterTotal)} remains within the proposed budget limit.`);
    if (changes.length > 1) {
      for (const task of event.tasks.filter((item) => item.priority === 'high' && item.status !== 'completed')) affectedTasks.add(task.title);
    }
    if (changes.length > 1 && affectedVendors.size === 0 && inputType === 'guest_count') {
      const catererVendor = event.vendors.find((vendor) => vendor.category.toLowerCase().includes('cater'));
      if (catererVendor) affectedVendors.add(catererVendor.category);
    }

    const preview: RipplePreview = {
      id: uuid(), baseRevision: event.revision, createdAt: Date.now(), eventId, inputType, proposedValue,
      changes, affectedTasks: [...affectedTasks], affectedVendors: [...affectedVendors], warnings, blockers, unknowns,
      beforeTotalMinor: currentTotal, afterTotalMinor: afterTotal, deltaMinor: afterTotal - currentTotal,
      commitAllowed: blockers.length === 0,
    };
    return envelope(preview);
  },

  async commitRipple(preview: RipplePreview, confirmed: boolean): Promise<ApiEnvelope<EventRecord>> {
    await pause(360);
    if (!confirmed) throw new DemoApiError('confirmation_required', 'A preview is never saved without your confirmation.', 409);
    const event = findEvent(preview.eventId);
    if (preview.baseRevision !== event.revision) throw new DemoApiError('stale_simulation', 'This preview is out of date. Create a fresh one before saving.', 412);
    if (!preview.commitAllowed) throw new DemoApiError('hard_constraint_violation', 'Resolve the blockers and preview again before saving.', 409);
    if (Date.now() - preview.createdAt > 15 * 60 * 1000) throw new DemoApiError('stale_simulation', 'This preview has expired. Create a fresh one before saving.', 412);
    if (preview.inputType === 'guest_count') {
      const catering = event.categories.find((category) => category.ratePerGuestMinor !== undefined);
      if (catering?.ratePerGuestMinor !== undefined) catering.plannedMinor = catering.ratePerGuestMinor * preview.proposedValue;
      event.guestCount = preview.proposedValue;
    } else {
      event.budgetLimitMinor = preview.proposedValue;
    }
    event.revision += 1;
    event.versionNumber += 1;
    persist();
    return envelope(clone(event));
  },

  async cancelRipple(_preview: RipplePreview): Promise<void> { void _preview; await pause(120); },

  async compareScenarios(eventId: string, guestCounts: number[]): Promise<ApiEnvelope<ScenarioResult[]>> {
    await pause(300);
    const event = findEvent(eventId);
    const baseTotal = totalPlanned(event.categories);
    const rate = event.categories.find((category) => category.ratePerGuestMinor !== undefined)?.ratePerGuestMinor ?? null;
    return envelope(guestCounts.map((guestCount, index) => {
      const totalMinor = baseTotal + (rate === null ? 0 : rate * (guestCount - event.guestCount));
      return {
        name: ['A little room', 'A bigger table', 'Your current plan'][index] ?? `Option ${index + 1}`,
        guestCount, totalMinor, deltaMinor: totalMinor - baseTotal,
        tables: event.seatsPerTable ? Math.ceil(guestCount / event.seatsPerTable) : null,
        capacityState: event.venueCapacity === null ? 'unknown' : guestCount > event.venueCapacity ? 'exceeded' : 'within',
      };
    }));
  },

  async answerCopilot(eventId: string, question: string): Promise<ApiEnvelope<{ answer: string; references: string[] }>> {
    await pause(780);
    const event = findEvent(eventId);
    const normalized = question.toLowerCase();
    let answer: string;
    let references: string[];
    if (normalized.includes('budget') || normalized.includes('spend')) {
      const total = totalPlanned(event.categories);
      answer = `Your current illustrative plan is ${formatRupees(total)} against a ${formatRupees(event.budgetLimitMinor)} limit, leaving ${formatRupees(event.budgetLimitMinor - total)}. The largest editable category is ${[...event.categories].sort((a, b) => b.plannedMinor - a.plannedMinor)[0]?.name ?? 'not set'}.`;
      references = ['budget.total', 'budget.limit'];
    } else if (normalized.includes('guest') || normalized.includes('capacity')) {
      answer = `The plan currently has ${event.guestCount} guests. ${event.venueCapacity === null ? 'Venue capacity is still unknown.' : `The entered venue limit is ${event.venueCapacity}.`} I can show how a different guest count affects the plan in Ripple.`;
      references = ['event.guest_count', 'event.venue_capacity'];
    } else {
      const nextTask = event.tasks.find((task) => task.status !== 'completed');
      answer = nextTask ? `A useful next step is “${nextTask.title}” (${nextTask.dueLabel}). It is still open in your plan.` : 'Your current checklist is complete. You can add another milestone or revisit any planning assumption.';
      references = nextTask ? [`task.${nextTask.id}`] : ['event.tasks'];
    }
    return envelope({ answer, references });
  },
};

// Demo is an explicit build-time choice. A live API error never switches modes.
export { liveApi } from './liveApi';
import { liveApi } from './liveApi';
export const demoApi = import.meta.env.VITE_MOMENTOS_MODE === 'demo' ? offlineDemoApi : liveApi;

export function formatRupees(minor: number): string {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(minor / 100);
}

export function parseRupeesToMinor(value: string): number | null {
  const clean = value.replace(/[₹,\s]/g, '');
  if (!/^\d+(?:\.\d{1,2})?$/.test(clean)) return null;
  const [whole, fraction = ''] = clean.split('.');
  return Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
}

export function asVendorStatus(value: string): VendorStatus {
  return value as VendorStatus;
}

export function sumCategories(categories: BudgetCategory[]): number {
  return totalPlanned(categories);
}
