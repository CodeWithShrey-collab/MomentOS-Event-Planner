export type EventType = 'wedding' | 'birthday' | 'community';
export type Provenance = 'illustrative_assumption' | 'user_entered' | 'suggested';
export type TaskStatus = 'not_started' | 'in_progress' | 'blocked' | 'completed';
export type VendorStatus = 'to_find' | 'contacted' | 'shortlisted' | 'selected';

export interface BudgetCategory {
  id: string;
  name: string;
  plannedMinor: number;
  actualMinor: number | null;
  color: string;
  provenance: Provenance;
  ratePerGuestMinor?: number;
}

export interface EventTask {
  id: string;
  title: string;
  phase: string;
  dueLabel: string;
  dueDays: number | null;
  status: TaskStatus;
  priority: 'high' | 'medium' | 'low';
  owner: string | null;
  dependencies: string[];
  categoryId?: string;
}

export interface Vendor {
  id: string;
  category: string;
  name: string | null;
  contact: string | null;
  status: VendorStatus;
  estimateMinor: number | null;
  quoteMinor: number | null;
  provenance: Provenance;
  note: string;
}

export interface EventRecord {
  id: string;
  eventType: EventType;
  title: string;
  currency: string;
  budgetLimitMinor: number;
  eventDate: string;
  city: string;
  guestCount: number;
  venueCapacity: number | null;
  seatsPerTable: number | null;
  invitationUnit: 'unknown' | 'person' | 'household';
  revision: number;
  versionNumber: number;
  createdAt: string;
  categories: BudgetCategory[];
  tasks: EventTask[];
  vendors: Vendor[];
  concept: string;
  priorities: string[];
  theme: string;
  notes: string;
  accepted: boolean;
}

export interface EventDraftInput {
  eventType: EventType;
  title: string;
  eventDate: string;
  city: string;
  guestCount: number;
  budgetLimitMinor: number;
  priorities: string[];
  theme: string;
  notes: string;
}

export interface PlanDraft {
  eventId: string;
  concept: string;
  assumptions: string[];
  unknowns: string[];
  categories: BudgetCategory[];
  budgetItems?: Array<{
    id: string;
    label: string;
    quantity: number | null;
    quantityBasis: 'guest_count' | 'fixed' | null;
    unitRateMinor: number | null;
    plannedMinor: number;
    sourceNote: string;
  }>;
  tasks: EventTask[];
  vendors: Vendor[];
  ideas: string[];
  aiStatus: 'offline_demo' | 'live' | 'mock';
}

export interface RippleChange {
  label: string;
  before: string;
  after: string;
  detail: string;
  category?: string;
}

export interface RipplePreview {
  id: string;
  baseRevision: number;
  createdAt: number;
  eventId: string;
  inputType: 'guest_count' | 'budget_limit';
  proposedValue: number;
  changes: RippleChange[];
  affectedTasks: string[];
  affectedVendors: string[];
  warnings: string[];
  blockers: string[];
  unknowns: string[];
  beforeTotalMinor: number;
  afterTotalMinor: number;
  deltaMinor: number;
  commitAllowed: boolean;
}

export interface ScenarioResult {
  name: string;
  guestCount: number;
  totalMinor: number;
  deltaMinor: number;
  tables: number | null;
  capacityState: 'within' | 'exceeded' | 'unknown';
  warnings?: string[];
  blockers?: string[];
}

export interface ApiEnvelope<T> {
  data: T;
  request_id: string;
}

export interface ApiFailure {
  error: {
    code: string;
    message: string;
    fields?: Array<{ path: string; code: string; message: string }>;
  };
  request_id: string;
}
