/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ApiEnvelope, EventDraftInput, EventRecord, PlanDraft, RipplePreview, ScenarioResult } from '../types';
import { eventHeaders, request, setEventEtag } from './apiClient';

type Json = Record<string, any>;
const pendingPlans = new Map<string, Json>();
const previews = new Map<string, Json>();
const env = <T,>(data: T): ApiEnvelope<T> => ({ data, request_id: 'server' });
const eventPath = (id: string) => `/events/${encodeURIComponent(id)}`;

function preferenceList(value: unknown): string[] {
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
  if (!value || typeof value !== 'object') return [];
  const record = value as Json;
  const items = Array.isArray(record.priorities) ? record.priorities : record.items;
  return Array.isArray(items) ? items.filter((item): item is string => typeof item === 'string') : [];
}

function mapEvent(raw: Json): EventRecord {
  const summary = raw.summary ?? {};
  const categories = (summary.budget_categories ?? []).map((c: Json) => ({ id: c.logical_id, name: c.name, plannedMinor: c.planned_minor ?? 0, actualMinor: null, color: '#806080', provenance: c.source === 'accepted_ai_suggestion' ? 'suggested' : 'illustrative_assumption' }));
  const tasks = (summary.tasks ?? []).map((t: Json) => ({ id: t.logical_id, title: t.title, phase: t.phase ?? 'before_event', dueLabel: t.due_local_date ?? 'Date to decide', dueDays: null, status: t.status, priority: t.priority, owner: t.owner_label, dependencies: t.dependencies ?? [] }));
  const vendors = (summary.vendors ?? []).map((v: Json) => ({ id: v.logical_id, category: v.category, name: v.display_name, contact: v.contact_name ?? v.email ?? v.phone, status: ({ contacted_by_user: 'contacted', shortlisted_by_user: 'shortlisted', selected_by_user: 'selected' } as Record<string,string>)[v.status] ?? 'to_find', estimateMinor: null, quoteMinor: v.quotes?.[0]?.amount_minor ?? null, provenance: v.information_source === 'user_entered' ? 'user_entered' : 'suggested', note: v.notes ?? '' }));
  return { id: raw.id, eventType: raw.event_type, title: raw.title, currency: raw.currency, budgetLimitMinor: summary.budget_limit_minor ?? raw.budget_limit_minor ?? 0, eventDate: summary.event_date ?? raw.event_date ?? '', city: summary.location_label ?? raw.location_label ?? '', guestCount: summary.guest_count ?? raw.draft_fields?.guest_count ?? 0, venueCapacity: summary.venue_capacity ?? null, seatsPerTable: summary.seats_per_table ?? null, invitationUnit: summary.invitation_unit ?? 'unknown', revision: raw.revision ?? summary.revision ?? 0, versionNumber: raw.current_version_no ?? summary.version_no ?? 0, createdAt: raw.created_at ?? '', categories, tasks, vendors, concept: summary.concept?.description ?? '', priorities: preferenceList(summary.preferences ?? raw.draft_fields?.preferences), theme: '', notes: '', accepted: Boolean(raw.current_version_no) };
}

function mapDraft(eventId: string, raw: Json): PlanDraft {
  pendingPlans.set(eventId, raw);
  const aiMode = raw.ai_status?.mode;
  return { eventId, concept: raw.concept?.description ?? raw.concept?.title ?? '', assumptions: raw.assumptions ?? [], unknowns: raw.unknowns ?? [], categories: (raw.budget_categories ?? []).map((c: Json) => ({ id: c.key, name: c.name, plannedMinor: c.planned_minor ?? 0, actualMinor: null, color: '#806080', provenance: c.source === 'accepted_ai_suggestion' ? 'suggested' : 'illustrative_assumption' })), budgetItems: (raw.budget_items ?? []).map((item: Json, index: number) => ({ id: `${String(item.category_key ?? 'item')}-${index}`, label: String(item.label ?? 'Budget item'), quantity: typeof item.quantity === 'number' && Number.isFinite(item.quantity) ? item.quantity : null, quantityBasis: item.quantity_basis === 'guest_count' || item.quantity_basis === 'fixed' ? item.quantity_basis : null, unitRateMinor: typeof item.unit_rate_minor === 'number' && Number.isFinite(item.unit_rate_minor) ? item.unit_rate_minor : null, plannedMinor: typeof item.planned_minor === 'number' && Number.isFinite(item.planned_minor) ? item.planned_minor : 0, sourceNote: String(item.source_note ?? 'Editable estimate') })), tasks: (raw.tasks ?? []).map((t: Json) => ({ id: t.key, title: t.title, phase: t.phase ?? 'before_event', dueLabel: 'Date to decide', dueDays: null, status: t.status ?? 'not_started', priority: t.priority ?? 'medium', owner: null, dependencies: t.depends_on_keys ?? [] })), vendors: (raw.vendor_categories ?? []).map((v: Json) => ({ id: v.key, category: v.category, name: null, contact: null, status: 'to_find', estimateMinor: null, quoteMinor: null, provenance: 'suggested', note: v.why ?? '' })), ideas: (raw.ideas ?? []).map((i: Json) => typeof i === 'string' ? i : i.idea), aiStatus: aiMode === 'live' ? 'live' : aiMode === 'mock' ? 'mock' : 'offline_demo' };
}

function rippleShape(event: EventRecord, raw: Json, type: RipplePreview['inputType'], value: number): RipplePreview {
  const eventId = event.id;
  previews.set(raw.simulation_id, raw);
  const changes = raw.changes ?? [];
  const budget = raw.budget_summary ?? {};
  const names = new Map(event.tasks.map(t=>[t.id,t.title])); const vendorNames = new Map(event.vendors.map(v=>[v.id,v.category]));
  const before = budget.before?.planned_minor ?? 0; const after = budget.after?.planned_minor ?? before;
  const cap = raw.capacity_summary?.after; const tables = cap?.required_tables;
  const diff = changes.map((c: Json) => { const money=c.unit==='minor_currency_unit'; const format=(v:unknown)=>money&&v!==null&&v!==undefined?new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:0}).format(Number(v)/100):String(v??''); return { label: `${c.entity ?? 'Event'} ${c.field}`, before: format(c.before), after: format(c.after), detail: money?'Calculated amount · INR':(c.unit ?? 'Calculated by the deterministic planning engine') }; });
  if (tables !== undefined && tables !== null) diff.push({ label:'Tables to arrange', before:String(raw.capacity_summary?.before?.required_tables ?? ''), after:String(tables), detail:'Calculated from saved seats per table assumption' });
  return { id: raw.simulation_id, baseRevision: raw.base_revision, createdAt: Date.now(), eventId, inputType: type, proposedValue: value, changes: diff, affectedTasks: (raw.affected_task_ids ?? []).map((id:string)=>names.get(id) ?? id), affectedVendors: (raw.affected_vendor_ids ?? []).map((id:string)=>vendorNames.get(id) ?? id), warnings: (raw.warnings ?? []).map((w: any) => w.message ?? String(w)), blockers: (raw.blockers ?? []).map((w: any) => w.message ?? String(w)), unknowns: (raw.unknowns ?? []).map((w: any) => w.message ?? String(w)), beforeTotalMinor: before, afterTotalMinor: after, deltaMinor: after-before, commitAllowed: Boolean(raw.commit_allowed) };
}

export const liveApi = {
  mode: 'live' as const,
  async listEvents() { const { body } = await request<{items: Json[]}>('/events'); return env(body.data.items.map(mapEvent)); },
  async getEvent(id: string) { const { body } = await request<Json>(`${eventPath(id)}?include=summary`); return env(mapEvent(body.data)); },
  async createEvent(input: EventDraftInput) {
    const { body, etag } = await request<Json>('/events', { method: 'POST', body: JSON.stringify({ event_type: input.eventType, title: input.title, currency: 'INR', budget_limit_minor: input.budgetLimitMinor, event_date: input.eventDate || null, location_label: input.city, guest_count: input.guestCount, preferences: { priorities: input.priorities, theme: input.theme, notes: input.notes } }) });
    setEventEtag(body.data.id, etag); return env(mapEvent(body.data));
  },
  async generatePlanDraft(id: string, input?: EventDraftInput) {
    const event = (await this.getEvent(id)).data;
    const brief = { title: input?.title ?? event.title, guest_count: input?.guestCount ?? event.guestCount, budget_limit_minor: input?.budgetLimitMinor ?? event.budgetLimitMinor, event_date: input?.eventDate || event.eventDate || null, location_label: input?.city ?? event.city, preferences: input?.priorities ?? event.priorities, constraints: [input?.theme, input?.notes].filter(Boolean) };
    const { body } = await request<Json>(`${eventPath(id)}/plan-drafts`, { method: 'POST', body: JSON.stringify({ brief, include: ['concept','budget','tasks','vendors','ideas'] }) });
    return env(mapDraft(id, body.data));
  },
  async commitPlanDraft(draft: PlanDraft, confirmed: boolean) {
    if (!confirmed) throw new Error('Plan confirmation is required.');
    const plan = pendingPlans.get(draft.eventId); if (!plan) throw new Error('Plan draft expired. Generate it again before saving.');
    const headers = new Headers(eventHeaders(draft.eventId));
    const { etag } = await request<Json>(`${eventPath(draft.eventId)}/plan-commits`, { method: 'POST', headers, body: JSON.stringify({ confirmed: true, base_version_no: null, plan }) });
    setEventEtag(draft.eventId, etag); pendingPlans.delete(draft.eventId);
    return this.getEvent(draft.eventId);
  },
  async updateCategory(eventId: string, id: string, amount: number) { const {body}=await request<Json>(`${eventPath(eventId)}?include=summary`); const items=(body.data.summary?.budget_items??[]).filter((item:Json)=>item.category_id===id); const payload=items.length?{item_changes:items.map((item:Json,index:number)=>({logical_id:item.logical_id,planned_minor:index===0?amount:0}))}:{category_changes:[{logical_id:id,planned_minor:amount}]}; await request(`${eventPath(eventId)}/budget`, { method: 'PATCH', headers: eventHeaders(eventId), body: JSON.stringify(payload) }); return this.getEvent(eventId); },
  async toggleTask(eventId: string, taskId: string) { const event = (await this.getEvent(eventId)).data; const task = event.tasks.find(t => t.id === taskId); if (!task) throw new Error('Task not found.'); await request<Json>(`${eventPath(eventId)}/tasks/${taskId}`, { method: 'PATCH', headers: eventHeaders(eventId), body: JSON.stringify({ status: task.status === 'completed' ? 'not_started' : 'completed' }) }); return env(task); },
  async updateVendor(eventId: string, vendorId: string, updates: any) { const bodyMap: Json = {}; if (updates.status) bodyMap.status = ({ contacted:'contacted_by_user', shortlisted:'shortlisted_by_user', selected:'selected_by_user', to_find:'to_find' } as Json)[updates.status]; if (updates.name !== undefined) bodyMap.display_name = updates.name; if (updates.contact !== undefined) bodyMap.contact_name = updates.contact; if (updates.note !== undefined) bodyMap.notes = updates.note; await request<Json>(`${eventPath(eventId)}/vendors/${vendorId}`, { method:'PATCH', headers:eventHeaders(eventId), body:JSON.stringify(bodyMap) }); const event=(await this.getEvent(eventId)).data; return env(event.vendors.find(v=>v.id===vendorId)!); },
  async addVendor(eventId: string, category: string, name = '') { const safeCategory=category.trim().toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,60); if(safeCategory.length<2) throw new Error('Enter a vendor category with at least two letters.'); await request<Json>(`${eventPath(eventId)}/vendors`, { method:'POST', headers:eventHeaders(eventId), body:JSON.stringify({ category:safeCategory, display_name:name || null, status:'to_find' }) }); const event=(await this.getEvent(eventId)).data; return env(event.vendors.at(-1)!); },
  async previewRipple(eventId: string, type: RipplePreview['inputType'], value: number) { const event = (await this.getEvent(eventId)).data; const field = type === 'guest_count' ? 'guest_count' : 'budget_limit_minor'; const { body } = await request<Json>(`${eventPath(eventId)}/ripple-previews`, { method:'POST', headers:eventHeaders(eventId), body:JSON.stringify({ base_version_no:event.versionNumber, changes:[{target:'event',field,value}], acknowledge_unknowns:true }) }); return env(rippleShape(event, body.data, type, value)); },
  async commitRipple(preview: RipplePreview, confirmed: boolean) { const raw=previews.get(preview.id); if (!raw) throw new Error('Ripple preview expired; run a new simulation.'); const suffix = confirmed ? 'commit' : 'cancel'; const payload = confirmed ? {confirmed:true,acknowledged_warning_codes:(raw.warnings ?? []).map((w:any)=>w.code).filter(Boolean)} : {confirmed:false}; await request<Json>(`${eventPath(preview.eventId)}/ripple-previews/${preview.id}/${suffix}`, { method:'POST', headers:eventHeaders(preview.eventId), body:JSON.stringify(payload) }); previews.delete(preview.id); return this.getEvent(preview.eventId); },
  async cancelRipple(preview: RipplePreview) { await this.commitRipple(preview, false); },
  async compareScenarios(eventId: string, counts: number[]) { const event=(await this.getEvent(eventId)).data; const { body }=await request<Json>(`${eventPath(eventId)}/scenario-comparisons`,{method:'POST',body:JSON.stringify({base_version_no:event.versionNumber,scenarios:counts.slice(0,3).map((n,i)=>({name:`Option ${i+1} · ${n} guests`,changes:[{target:'event',field:'guest_count',value:n}]}))})}); return env((body.data.scenarios ?? []).map((s:Json,i:number)=>({name:s.name,guestCount:counts[i] ?? event.guestCount,totalMinor:s.budget_summary?.after?.planned_minor ?? 0,deltaMinor:s.budget_summary?.planned_delta_minor ?? 0,tables:s.capacity_summary?.after?.required_tables ?? null,capacityState:s.capacity_summary?.after?.state==='exceeded'?'exceeded':s.capacity_summary?.after?.state==='within'?'within':'unknown',warnings:(s.warnings??[]).map((w:any)=>w.message??String(w)),blockers:(s.blockers??[]).map((w:any)=>w.message??String(w))} as ScenarioResult))); },
  async answerCopilot(eventId: string, question: string) { const { body }=await request<Json>(`${eventPath(eventId)}/copilot`,{method:'POST',body:JSON.stringify({question,context_sections:['budget','tasks','vendors','preferences']})}); return env({answer:body.data.answer, references:body.data.known_references ?? []} as any); },
};
