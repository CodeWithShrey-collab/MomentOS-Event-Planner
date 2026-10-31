import type { BudgetCategory, EventRecord, EventTask, EventType, Vendor } from '../types';

const weddingCategories: BudgetCategory[] = [
  { id: 'venue', name: 'Venue & stay', plannedMinor: 10_000_000, actualMinor: 9_600_000, color: '#74536f', provenance: 'illustrative_assumption' },
  { id: 'food', name: 'Food & catering', plannedMinor: 15_000_000, actualMinor: 7_500_000, color: '#c28062', provenance: 'illustrative_assumption', ratePerGuestMinor: 100_000 },
  { id: 'decor', name: 'Flowers & decor', plannedMinor: 7_500_000, actualMinor: null, color: '#bd9e57', provenance: 'illustrative_assumption' },
  { id: 'photo', name: 'Photography', plannedMinor: 8_500_000, actualMinor: null, color: '#84927e', provenance: 'illustrative_assumption' },
  { id: 'music', name: 'Music & sound', plannedMinor: 5_000_000, actualMinor: 2_500_000, color: '#8c748a', provenance: 'illustrative_assumption' },
  { id: 'attire', name: 'Attire & details', plannedMinor: 6_500_000, actualMinor: null, color: '#d29a74', provenance: 'illustrative_assumption' },
  { id: 'travel', name: 'Travel', plannedMinor: 2_000_000, actualMinor: null, color: '#a0a99a', provenance: 'illustrative_assumption' },
  { id: 'reserve', name: 'A little in reserve', plannedMinor: 3_500_000, actualMinor: null, color: '#b9a7a0', provenance: 'illustrative_assumption' },
];

const tasks: EventTask[] = [
  { id: 'venue-confirm', title: 'Confirm the venue and guest limit', phase: 'The foundations', dueLabel: 'This week', dueDays: 3, status: 'completed', priority: 'high', owner: 'Maya', dependencies: [] },
  { id: 'catering-tasting', title: 'Choose the menu after the tasting', phase: 'The foundations', dueLabel: 'In 5 days', dueDays: 5, status: 'in_progress', priority: 'high', owner: 'Maya', dependencies: ['venue-confirm'], categoryId: 'food' },
  { id: 'guest-list', title: 'Bring the guest list into one place', phase: 'The details', dueLabel: 'In 9 days', dueDays: 9, status: 'not_started', priority: 'high', owner: 'Maya', dependencies: [] },
  { id: 'photo-brief', title: 'Share a photography brief', phase: 'The details', dueLabel: 'In 12 days', dueDays: 12, status: 'not_started', priority: 'medium', owner: 'Sam', dependencies: ['venue-confirm'], categoryId: 'photo' },
  { id: 'invite-proof', title: 'Review the invitation proof', phase: 'Just before', dueLabel: 'In 18 days', dueDays: 18, status: 'not_started', priority: 'medium', owner: null, dependencies: ['guest-list'] },
  { id: 'sound-check', title: 'Run through the sound plan', phase: 'Event week', dueLabel: 'In 42 days', dueDays: 42, status: 'not_started', priority: 'low', owner: 'Sam', dependencies: ['venue-confirm'], categoryId: 'music' },
];

const vendors: Vendor[] = [
  { id: 'venue-vendor', category: 'Venue', name: 'The old garden house', contact: 'Rhea · user entry', status: 'selected', estimateMinor: 10_000_000, quoteMinor: 9_600_000, provenance: 'user_entered', note: 'Quote entered by you · valid through 12 Oct' },
  { id: 'caterer', category: 'Catering', name: 'Menu tasting to arrange', contact: null, status: 'contacted', estimateMinor: 15_000_000, quoteMinor: null, provenance: 'illustrative_assumption', note: 'Planning assumption · ₹1,000 per guest' },
  { id: 'photo-vendor', category: 'Photography', name: null, contact: null, status: 'shortlisted', estimateMinor: 8_500_000, quoteMinor: null, provenance: 'illustrative_assumption', note: 'Illustrative allowance · add your own contact' },
  { id: 'music-vendor', category: 'Music & sound', name: null, contact: null, status: 'to_find', estimateMinor: 5_000_000, quoteMinor: null, provenance: 'illustrative_assumption', note: 'A checklist category, not a real supplier' },
];

export const DEMO_EVENTS: EventRecord[] = [
  {
    id: 'moment-wedding-01', eventType: 'wedding', title: 'A garden wedding', currency: 'INR', budgetLimitMinor: 60_000_000,
    eventDate: '2026-12-12', city: 'Nagpur', guestCount: 150, venueCapacity: 180, seatsPerTable: 10,
    invitationUnit: 'unknown', revision: 4, versionNumber: 4, createdAt: '2026-09-02', categories: weddingCategories,
    tasks, vendors, concept: 'A warm garden celebration, with room for everyone and a little breathing space in the plan.',
    priorities: ['Good food', 'Time with family', 'A relaxed pace'], theme: 'Garden at dusk', notes: 'An intimate outdoor celebration with a thoughtful vegetarian menu.', accepted: true,
  },
  {
    id: 'moment-birthday-01', eventType: 'birthday', title: 'A little wonder, a lot of joy', currency: 'INR', budgetLimitMinor: 8_000_000,
    eventDate: '2026-11-08', city: 'Nagpur', guestCount: 60, venueCapacity: 80, seatsPerTable: 8,
    invitationUnit: 'unknown', revision: 2, versionNumber: 2, createdAt: '2026-09-11',
    categories: [
      { id: 'venue', name: 'Venue', plannedMinor: 1_500_000, actualMinor: null, color: '#74536f', provenance: 'illustrative_assumption' },
      { id: 'food', name: 'Good food', plannedMinor: 2_700_000, actualMinor: null, color: '#c28062', provenance: 'illustrative_assumption', ratePerGuestMinor: 45_000 },
      { id: 'cake', name: 'Cake & sweet things', plannedMinor: 600_000, actualMinor: null, color: '#bd9e57', provenance: 'illustrative_assumption' },
      { id: 'decor', name: 'Decor', plannedMinor: 1_000_000, actualMinor: null, color: '#84927e', provenance: 'illustrative_assumption' },
      { id: 'music', name: 'Games & music', plannedMinor: 800_000, actualMinor: null, color: '#8c748a', provenance: 'illustrative_assumption' },
      { id: 'favors', name: 'Little favors', plannedMinor: 600_000, actualMinor: null, color: '#d29a74', provenance: 'illustrative_assumption', ratePerGuestMinor: 10_000 },
      { id: 'reserve', name: 'In reserve', plannedMinor: 800_000, actualMinor: null, color: '#b9a7a0', provenance: 'illustrative_assumption' },
    ],
    tasks: tasks.slice(0, 5).map((task, i) => ({ ...task, id: `birthday-${i}`, status: i === 0 ? 'in_progress' : 'not_started' })),
    vendors: vendors.slice(0, 3).map((vendor, i) => ({ ...vendor, id: `birthday-v-${i}` })),
    concept: 'An easy-going afternoon with a little magic for the guest of honor.', priorities: ['Good food', 'Kids can play'], theme: 'Sun-washed afternoon', notes: 'Location, age and dietary needs are still open.', accepted: true,
  },
  {
    id: 'moment-community-01', eventType: 'community', title: 'The neighborhood table', currency: 'INR', budgetLimitMinor: 15_000_000,
    eventDate: '2026-12-06', city: 'Nagpur', guestCount: 300, venueCapacity: null, seatsPerTable: null,
    invitationUnit: 'unknown', revision: 1, versionNumber: 1, createdAt: '2026-09-19',
    categories: [
      { id: 'venue', name: 'Space & setup', plannedMinor: 2_000_000, actualMinor: null, color: '#74536f', provenance: 'illustrative_assumption' },
      { id: 'food', name: 'Food & water', plannedMinor: 7_500_000, actualMinor: null, color: '#c28062', provenance: 'illustrative_assumption', ratePerGuestMinor: 25_000 },
      { id: 'music', name: 'Sound & access', plannedMinor: 1_500_000, actualMinor: null, color: '#bd9e57', provenance: 'illustrative_assumption' },
      { id: 'safety', name: 'Safety planning allowance', plannedMinor: 1_000_000, actualMinor: null, color: '#84927e', provenance: 'illustrative_assumption' },
      { id: 'materials', name: 'Signs & materials', plannedMinor: 800_000, actualMinor: null, color: '#8c748a', provenance: 'illustrative_assumption' },
      { id: 'volunteers', name: 'Volunteer logistics', plannedMinor: 700_000, actualMinor: null, color: '#d29a74', provenance: 'illustrative_assumption' },
      { id: 'reserve', name: 'In reserve', plannedMinor: 1_500_000, actualMinor: null, color: '#b9a7a0', provenance: 'illustrative_assumption' },
    ],
    tasks: tasks.slice(0, 5).map((task, i) => ({ ...task, id: `community-${i}`, status: 'not_started', owner: i % 2 ? 'A volunteer' : null })),
    vendors: vendors.slice(0, 4).map((vendor, i) => ({ ...vendor, id: `community-v-${i}`, status: 'to_find', name: null, contact: null })),
    concept: 'A welcoming neighborhood gathering where the practical details help everyone feel included.', priorities: ['Accessibility', 'Keep essentials covered'], theme: 'Together outdoors', notes: 'Venue capacity, access needs and volunteers need confirmation.', accepted: true,
  },
];

export const TYPE_COPY: Record<EventType, { label: string; verb: string; description: string; accent: string }> = {
  wedding: { label: 'Wedding', verb: 'Bring everyone together', description: 'A thoughtful plan for all the little things that make it yours.', accent: 'plum' },
  birthday: { label: 'Birthday', verb: 'Make it feel like them', description: 'Ideas and details shaped around the person you are celebrating.', accent: 'coral' },
  community: { label: 'Community gathering', verb: 'Make room for everyone', description: 'Keep people, practicalities and the shared budget in view.', accent: 'sage' },
};

export function totalPlanned(categories: BudgetCategory[]): number {
  return categories.reduce((sum, category) => sum + category.plannedMinor, 0);
}

export function totalActual(categories: BudgetCategory[]): number {
  return categories.reduce((sum, category) => sum + (category.actualMinor ?? 0), 0);
}
