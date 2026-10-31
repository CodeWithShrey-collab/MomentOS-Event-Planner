/** Typed adapter from the Flask API contract to the frontend's event models. */
import type {
  ApiEnvelope,
  EventDraftInput,
  EventRecord,
  EventTask,
  EventType,
  PlanDraft,
  Provenance,
  RipplePreview,
  ScenarioResult,
  TaskStatus,
  Vendor,
  VendorStatus,
} from '../types';
import { eventHeaders, request, setEventEtag } from './apiClient';

type ApiRecord = Record<string, unknown>;
type TaskPriority = EventTask['priority'];
type ApiVendorStatus = 'to_find' | 'contacted_by_user' | 'shortlisted_by_user' | 'selected_by_user';
type MessageDto = string | { message?: string; code?: string };

interface EventCategoryDto {
  logical_id: string;
  name: string;
  planned_minor?: number | null;
  source?: unknown;
}

interface EventTaskDto {
  logical_id: string;
  title: string;
  phase?: string | null;
  due_local_date?: string | null;
  status: string;
  priority?: string | null;
  owner_label?: string | null;
  dependencies?: string[];
}

interface EventBudgetItemDto {
  logical_id: string;
  category_id: string;
}

interface VendorQuoteDto {
  amount_minor?: number | null;
}

interface EventVendorDto {
  logical_id: string;
  category: string;
  display_name?: string | null;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  status: string;
  information_source?: string | null;
  notes?: string | null;
  quotes?: VendorQuoteDto[];
}

interface EventSummaryDto {
  version_no?: number | null;
  revision?: number;
  budget_limit_minor?: number | null;
  event_date?: string | null;
  location_label?: string | null;
  guest_count?: number | null;
  venue_capacity?: number | null;
  seats_per_table?: number | null;
  invitation_unit?: EventRecord['invitationUnit'];
  preferences?: unknown;
  budget_items?: EventBudgetItemDto[];
  concept?: { description?: string | null } | null;
  budget_categories?: EventCategoryDto[];
  tasks?: EventTaskDto[];
  vendors?: EventVendorDto[];
}

interface EventResponseDto {
  id: string;
  event_type: EventType;
  title: string;
  currency: string;
  budget_limit_minor?: number | null;
  event_date?: string | null;
  location_label?: string | null;
  draft_fields?: { guest_count?: number | null; preferences?: unknown } | null;
  current_version_no?: number | null;
  revision?: number;
  created_at?: string | null;
  summary?: EventSummaryDto | null;
}

interface EventListResponseDto {
  items: EventResponseDto[];
  next_cursor?: string | null;
}

interface DraftCategoryDto {
  key: string;
  name: string;
  planned_minor?: number | null;
  source?: unknown;
}

interface DraftBudgetItemDto {
  category_key?: string | null;
  label?: string | null;
  quantity?: number | string | null;
  quantity_basis?: 'guest_count' | 'fixed' | null;
  unit_rate_minor?: number | null;
  planned_minor?: number | null;
  source_note?: string | null;
}

interface DraftTaskDto {
  key: string;
  title: string;
  phase?: string | null;
  status?: string | null;
  priority?: string | null;
  depends_on_keys?: string[];
}

interface DraftVendorDto {
  key: string;
  category: string;
  why?: string | null;
}

interface EventPlanDraftDto {
  concept?: { description?: string | null; title?: string | null } | null;
  assumptions?: string[];
  unknowns?: string[];
  budget_categories?: DraftCategoryDto[];
  budget_items?: DraftBudgetItemDto[];
  tasks?: DraftTaskDto[];
  vendor_categories?: DraftVendorDto[];
  ideas?: Array<string | { idea?: string | null }>;
  ai_status?: { mode?: string | null };
}

interface RippleChangeDto {
  entity?: string | null;
  field: string;
  before?: unknown;
  after?: unknown;
  unit?: string | null;
}

interface BudgetTotalDto {
  planned_minor?: number | null;
}

interface RippleResponseDto {
  simulation_id: string;
  base_revision: number;
  changes?: RippleChangeDto[];
  budget_summary?: {
    before?: BudgetTotalDto;
    after?: BudgetTotalDto;
  };
  capacity_summary?: {
    before?: { required_tables?: number | null };
    after?: { required_tables?: number | null; state?: string | null };
  };
  affected_task_ids?: string[];
  affected_vendor_ids?: string[];
  warnings?: MessageDto[];
  blockers?: MessageDto[];
  unknowns?: MessageDto[];
  commit_allowed?: boolean;
}

interface ScenarioDto {
  name: string;
  budget_summary?: {
    after?: BudgetTotalDto;
    planned_delta_minor?: number | null;
  };
  capacity_summary?: {
    after?: { required_tables?: number | null; state?: string | null };
  };
  warnings?: MessageDto[];
  blockers?: MessageDto[];
}

interface ScenarioComparisonResponseDto {
  scenarios?: ScenarioDto[];
}

interface CopilotResponseDto {
  answer: string;
  known_references?: string[];
}

type VendorUpdates = Partial<Pick<Vendor, 'status' | 'name' | 'contact' | 'quoteMinor' | 'note'>>;

const pendingPlans = new Map<string, EventPlanDraftDto>();
const previews = new Map<string, RippleResponseDto>();
const env = <T,>(data: T): ApiEnvelope<T> => ({ data, request_id: 'server' });
const eventPath = (id: string) => `/events/${encodeURIComponent(id)}`;

function isRecord(value: unknown): value is ApiRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function preferenceList(value: unknown): string[] {
  if (Array.isArray(value)) return stringList(value);
  if (!isRecord(value)) return [];
  return stringList(value.priorities ?? value.items);
}

function provenance(source: unknown): Provenance {
  const sourceName = isRecord(source) ? source.mode ?? source.source : source;
  if (sourceName === 'accepted_ai_suggestion' || sourceName === 'suggested') return 'suggested';
  if (sourceName === 'user' || sourceName === 'user_input' || sourceName === 'user_supplied') return 'user_entered';
  return 'illustrative_assumption';
}

function taskStatus(status: string): TaskStatus {
  switch (status) {
    case 'in_progress':
    case 'blocked':
    case 'completed':
      return status;
    default:
      return 'not_started';
  }
}

function taskPriority(priority: string | null | undefined): TaskPriority {
  if (priority === 'high' || priority === 'low') return priority;
  return 'medium';
}

function vendorStatus(status: string): VendorStatus {
  switch (status) {
    case 'contacted_by_user': return 'contacted';
    case 'shortlisted_by_user': return 'shortlisted';
    case 'selected_by_user': return 'selected';
    default: return 'to_find';
  }
}

function mapVendor(raw: EventVendorDto): Vendor {
  return {
    id: raw.logical_id,
    category: raw.category,
    name: raw.display_name ?? null,
    contact: raw.contact_name ?? raw.email ?? raw.phone ?? null,
    status: vendorStatus(raw.status),
    estimateMinor: null,
    quoteMinor: raw.quotes?.[0]?.amount_minor ?? null,
    provenance: raw.information_source === 'user_entered' ? 'user_entered' : 'suggested',
    note: raw.notes ?? '',
  };
}

function mapEvent(raw: EventResponseDto): EventRecord {
  const summary = raw.summary ?? {};
  const draft = raw.draft_fields ?? {};
  const categories = (summary.budget_categories ?? []).map((category) => ({
    id: category.logical_id,
    name: category.name,
    plannedMinor: category.planned_minor ?? 0,
    actualMinor: null,
    color: '#806080',
    provenance: provenance(category.source),
  }));
  const tasks = (summary.tasks ?? []).map((task) => ({
    id: task.logical_id,
    title: task.title,
    phase: task.phase ?? 'before_event',
    dueLabel: task.due_local_date ?? 'Date to decide',
    dueDays: null,
    status: taskStatus(task.status),
    priority: taskPriority(task.priority),
    owner: task.owner_label ?? null,
    dependencies: task.dependencies ?? [],
  }));

  return {
    id: raw.id,
    eventType: raw.event_type,
    title: raw.title,
    currency: raw.currency,
    budgetLimitMinor: summary.budget_limit_minor ?? raw.budget_limit_minor ?? 0,
    eventDate: summary.event_date ?? raw.event_date ?? '',
    city: summary.location_label ?? raw.location_label ?? '',
    guestCount: summary.guest_count ?? draft.guest_count ?? 0,
    venueCapacity: summary.venue_capacity ?? null,
    seatsPerTable: summary.seats_per_table ?? null,
    invitationUnit: summary.invitation_unit ?? 'unknown',
    revision: raw.revision ?? summary.revision ?? 0,
    versionNumber: raw.current_version_no ?? summary.version_no ?? 0,
    createdAt: raw.created_at ?? '',
    categories,
    tasks,
    vendors: (summary.vendors ?? []).map(mapVendor),
    concept: summary.concept?.description ?? '',
    priorities: preferenceList(summary.preferences ?? draft.preferences),
    theme: '',
    notes: '',
    accepted: Boolean(raw.current_version_no),
  };
}

function mapDraft(eventId: string, raw: EventPlanDraftDto): PlanDraft {
  pendingPlans.set(eventId, raw);
  const mode = raw.ai_status?.mode;
  const ideas = (raw.ideas ?? []).flatMap((idea) => {
    if (typeof idea === 'string') return [idea];
    return typeof idea.idea === 'string' ? [idea.idea] : [];
  });

  return {
    eventId,
    concept: raw.concept?.description ?? raw.concept?.title ?? '',
    assumptions: raw.assumptions ?? [],
    unknowns: raw.unknowns ?? [],
    categories: (raw.budget_categories ?? []).map((category) => ({
      id: category.key,
      name: category.name,
      plannedMinor: category.planned_minor ?? 0,
      actualMinor: null,
      color: '#806080',
      provenance: provenance(category.source),
    })),
    budgetItems: (raw.budget_items ?? []).map((item, index) => ({
      id: `${item.category_key ?? 'item'}-${index}`,
      label: item.label ?? 'Budget item',
      quantity: typeof item.quantity === 'number' && Number.isFinite(item.quantity) ? item.quantity : null,
      quantityBasis: item.quantity_basis ?? null,
      unitRateMinor: item.unit_rate_minor ?? null,
      plannedMinor: item.planned_minor ?? 0,
      sourceNote: item.source_note ?? 'Editable estimate',
    })),
    tasks: (raw.tasks ?? []).map((task) => ({
      id: task.key,
      title: task.title,
      phase: task.phase ?? 'before_event',
      dueLabel: 'Date to decide',
      dueDays: null,
      status: taskStatus(task.status ?? 'not_started'),
      priority: taskPriority(task.priority),
      owner: null,
      dependencies: task.depends_on_keys ?? [],
    })),
    vendors: (raw.vendor_categories ?? []).map((vendor) => ({
      id: vendor.key,
      category: vendor.category,
      name: null,
      contact: null,
      status: 'to_find',
      estimateMinor: null,
      quoteMinor: null,
      provenance: 'suggested',
      note: vendor.why ?? '',
    })),
    ideas,
    aiStatus: mode === 'live' ? 'live' : mode === 'mock' ? 'mock' : 'offline_demo',
  };
}

function messageText(message: MessageDto): string {
  return typeof message === 'string' ? message : message.message ?? String(message);
}

function rippleValue(value: unknown, isMoney: boolean): string {
  if (isMoney && value !== null && value !== undefined) {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 })
      .format(Number(value) / 100);
  }
  return String(value ?? '');
}

function rippleShape(
  event: EventRecord,
  raw: RippleResponseDto,
  inputType: RipplePreview['inputType'],
  proposedValue: number,
): RipplePreview {
  previews.set(raw.simulation_id, raw);
  const budget = raw.budget_summary;
  const beforeTotalMinor = budget?.before?.planned_minor ?? 0;
  const afterTotalMinor = budget?.after?.planned_minor ?? beforeTotalMinor;
  const taskNames = new Map(event.tasks.map((task) => [task.id, task.title]));
  const vendorNames = new Map(event.vendors.map((vendor) => [vendor.id, vendor.category]));
  const changes = (raw.changes ?? []).map((change) => {
    const isMoney = change.unit === 'minor_currency_unit';
    return {
      label: `${change.entity ?? 'Event'} ${change.field}`,
      before: rippleValue(change.before, isMoney),
      after: rippleValue(change.after, isMoney),
      detail: isMoney ? 'Calculated amount · INR' : change.unit ?? 'Calculated by the deterministic planning engine',
    };
  });
  const tablesBefore = raw.capacity_summary?.before?.required_tables;
  const tablesAfter = raw.capacity_summary?.after?.required_tables;
  if (tablesAfter !== undefined && tablesAfter !== null) {
    changes.push({
      label: 'Tables to arrange',
      before: String(tablesBefore ?? ''),
      after: String(tablesAfter),
      detail: 'Calculated from saved seats per table assumption',
    });
  }

  return {
    id: raw.simulation_id,
    baseRevision: raw.base_revision,
    createdAt: Date.now(),
    eventId: event.id,
    inputType,
    proposedValue,
    changes,
    affectedTasks: (raw.affected_task_ids ?? []).map((id) => taskNames.get(id) ?? id),
    affectedVendors: (raw.affected_vendor_ids ?? []).map((id) => vendorNames.get(id) ?? id),
    warnings: (raw.warnings ?? []).map(messageText),
    blockers: (raw.blockers ?? []).map(messageText),
    unknowns: (raw.unknowns ?? []).map(messageText),
    beforeTotalMinor,
    afterTotalMinor,
    deltaMinor: afterTotalMinor - beforeTotalMinor,
    commitAllowed: Boolean(raw.commit_allowed),
  };
}

function scenarioCapacityState(state: string | null | undefined): ScenarioResult['capacityState'] {
  if (state === 'within' || state === 'exceeded') return state;
  return 'unknown';
}

const vendorApiStatus: Record<VendorStatus, ApiVendorStatus> = {
  contacted: 'contacted_by_user',
  shortlisted: 'shortlisted_by_user',
  selected: 'selected_by_user',
  to_find: 'to_find',
};

export const liveApi = {
  mode: 'live' as const,

  async listEvents(): Promise<ApiEnvelope<EventRecord[]>> {
    const { body } = await request<EventListResponseDto>('/events');
    return env(body.data.items.map(mapEvent));
  },

  async getEvent(id: string): Promise<ApiEnvelope<EventRecord>> {
    const { body } = await request<EventResponseDto>(`${eventPath(id)}?include=summary`);
    return env(mapEvent(body.data));
  },

  async createEvent(input: EventDraftInput): Promise<ApiEnvelope<EventRecord>> {
    const { body, etag } = await request<EventResponseDto>('/events', {
      method: 'POST',
      body: JSON.stringify({
        event_type: input.eventType,
        title: input.title,
        currency: 'INR',
        budget_limit_minor: input.budgetLimitMinor,
        event_date: input.eventDate || null,
        location_label: input.city,
        guest_count: input.guestCount,
        preferences: { priorities: input.priorities, theme: input.theme, notes: input.notes },
      }),
    });
    setEventEtag(body.data.id, etag);
    return env(mapEvent(body.data));
  },

  async generatePlanDraft(id: string, input?: EventDraftInput): Promise<ApiEnvelope<PlanDraft>> {
    const event = (await this.getEvent(id)).data;
    const brief = {
      title: input?.title ?? event.title,
      guest_count: input?.guestCount ?? event.guestCount,
      budget_limit_minor: input?.budgetLimitMinor ?? event.budgetLimitMinor,
      event_date: input?.eventDate || event.eventDate || null,
      location_label: input?.city ?? event.city,
      preferences: input?.priorities ?? event.priorities,
      constraints: [input?.theme, input?.notes].filter(Boolean),
    };
    const { body } = await request<EventPlanDraftDto>(`${eventPath(id)}/plan-drafts`, {
      method: 'POST',
      body: JSON.stringify({ brief, include: ['concept', 'budget', 'tasks', 'vendors', 'ideas'] }),
    });
    return env(mapDraft(id, body.data));
  },

  async commitPlanDraft(draft: PlanDraft, confirmed: boolean): Promise<ApiEnvelope<EventRecord>> {
    if (!confirmed) throw new Error('Plan confirmation is required.');
    const plan = pendingPlans.get(draft.eventId);
    if (!plan) throw new Error('Plan draft expired. Generate it again before saving.');
    const headers = new Headers(eventHeaders(draft.eventId));
    const { etag } = await request<{ event: EventResponseDto; version_no: number }>(`${eventPath(draft.eventId)}/plan-commits`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ confirmed: true, base_version_no: null, plan }),
    });
    setEventEtag(draft.eventId, etag);
    pendingPlans.delete(draft.eventId);
    return this.getEvent(draft.eventId);
  },

  async updateCategory(eventId: string, id: string, amount: number): Promise<ApiEnvelope<EventRecord>> {
    const { body } = await request<EventResponseDto>(`${eventPath(eventId)}?include=summary`);
    const items = (body.data.summary?.budget_items ?? []).filter((item) => item.category_id === id);
    const payload = items.length
      ? { item_changes: items.map((item, index) => ({ logical_id: item.logical_id, planned_minor: index === 0 ? amount : 0 })) }
      : { category_changes: [{ logical_id: id, planned_minor: amount }] };
    await request(`${eventPath(eventId)}/budget`, {
      method: 'PATCH',
      headers: eventHeaders(eventId),
      body: JSON.stringify(payload),
    });
    return this.getEvent(eventId);
  },

  async toggleTask(eventId: string, taskId: string): Promise<ApiEnvelope<EventTask>> {
    const event = (await this.getEvent(eventId)).data;
    const task = event.tasks.find((candidate) => candidate.id === taskId);
    if (!task) throw new Error('Task not found.');
    await request(`${eventPath(eventId)}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: eventHeaders(eventId),
      body: JSON.stringify({ status: task.status === 'completed' ? 'not_started' : 'completed' }),
    });
    return env(task);
  },

  async updateVendor(eventId: string, vendorId: string, updates: VendorUpdates): Promise<ApiEnvelope<Vendor>> {
    const bodyMap: ApiRecord = {};
    if (updates.status !== undefined) bodyMap.status = vendorApiStatus[updates.status];
    if (updates.name !== undefined) bodyMap.display_name = updates.name;
    if (updates.contact !== undefined) bodyMap.contact_name = updates.contact;
    if (updates.note !== undefined) bodyMap.notes = updates.note;
    const { body } = await request<EventVendorDto>(`${eventPath(eventId)}/vendors/${vendorId}`, {
      method: 'PATCH',
      headers: eventHeaders(eventId),
      body: JSON.stringify(bodyMap),
    });
    return env(mapVendor(body.data));
  },

  async addVendor(eventId: string, category: string, name = ''): Promise<ApiEnvelope<Vendor>> {
    const safeCategory = category.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 60);
    if (safeCategory.length < 2) throw new Error('Enter a vendor category with at least two letters.');
    const { body } = await request<EventVendorDto>(`${eventPath(eventId)}/vendors`, {
      method: 'POST',
      headers: eventHeaders(eventId),
      body: JSON.stringify({ category: safeCategory, display_name: name || null, status: 'to_find' }),
    });
    return env(mapVendor(body.data));
  },

  async previewRipple(
    eventId: string,
    inputType: RipplePreview['inputType'],
    proposedValue: number,
  ): Promise<ApiEnvelope<RipplePreview>> {
    const event = (await this.getEvent(eventId)).data;
    const field = inputType === 'guest_count' ? 'guest_count' : 'budget_limit_minor';
    const { body } = await request<RippleResponseDto>(`${eventPath(eventId)}/ripple-previews`, {
      method: 'POST',
      headers: eventHeaders(eventId),
      body: JSON.stringify({
        base_version_no: event.versionNumber,
        changes: [{ target: 'event', field, value: proposedValue }],
        acknowledge_unknowns: true,
      }),
    });
    return env(rippleShape(event, body.data, inputType, proposedValue));
  },

  async commitRipple(preview: RipplePreview, confirmed: boolean): Promise<ApiEnvelope<EventRecord>> {
    const raw = previews.get(preview.id);
    if (!raw) throw new Error('Ripple preview expired; run a new simulation.');
    const suffix = confirmed ? 'commit' : 'cancel';
    const payload = confirmed
      ? { confirmed: true, acknowledged_warning_codes: (raw.warnings ?? []).flatMap((warning) => typeof warning === 'string' ? [] : warning.code ? [warning.code] : []) }
      : { confirmed: false };
    await request(`${eventPath(preview.eventId)}/ripple-previews/${preview.id}/${suffix}`, {
      method: 'POST',
      headers: eventHeaders(preview.eventId),
      body: JSON.stringify(payload),
    });
    previews.delete(preview.id);
    return this.getEvent(preview.eventId);
  },

  async cancelRipple(preview: RipplePreview): Promise<void> {
    await this.commitRipple(preview, false);
  },

  async compareScenarios(eventId: string, counts: number[]): Promise<ApiEnvelope<ScenarioResult[]>> {
    const event = (await this.getEvent(eventId)).data;
    const requestedCounts = counts.slice(0, 3);
    const { body } = await request<ScenarioComparisonResponseDto>(`${eventPath(eventId)}/scenario-comparisons`, {
      method: 'POST',
      body: JSON.stringify({
        base_version_no: event.versionNumber,
        scenarios: requestedCounts.map((guestCount, index) => ({
          name: `Option ${index + 1} · ${guestCount} guests`,
          changes: [{ target: 'event', field: 'guest_count', value: guestCount }],
        })),
      }),
    });
    const results = (body.data.scenarios ?? []).map((scenario, index): ScenarioResult => ({
      name: scenario.name,
      guestCount: requestedCounts[index] ?? event.guestCount,
      totalMinor: scenario.budget_summary?.after?.planned_minor ?? 0,
      deltaMinor: scenario.budget_summary?.planned_delta_minor ?? 0,
      tables: scenario.capacity_summary?.after?.required_tables ?? null,
      capacityState: scenarioCapacityState(scenario.capacity_summary?.after?.state),
      warnings: (scenario.warnings ?? []).map(messageText),
      blockers: (scenario.blockers ?? []).map(messageText),
    }));
    return env(results);
  },

  async answerCopilot(eventId: string, question: string): Promise<ApiEnvelope<{ answer: string; references: string[] }>> {
    const { body } = await request<CopilotResponseDto>(`${eventPath(eventId)}/copilot`, {
      method: 'POST',
      body: JSON.stringify({ question, context_sections: ['budget', 'tasks', 'vendors', 'preferences'] }),
    });
    return env({ answer: body.data.answer, references: body.data.known_references ?? [] });
  },
};
