import { beforeEach, describe, expect, it, vi } from 'vitest';
import { eventHeaders, request, setEventEtag } from './apiClient';
import { liveApi } from './liveApi';

vi.mock('./apiClient', () => ({
  eventHeaders: vi.fn(() => ({ 'If-Match': '"event-v1"' })),
  request: vi.fn(),
  setEventEtag: vi.fn(),
}));

const requestMock = vi.mocked(request);

function respondWith(...responses: unknown[]): void {
  let responseIndex = 0;
  requestMock.mockImplementation(async <T,>() => ({
    body: { data: responses[responseIndex++] as T, request_id: 'test-request' },
    etag: null,
  }));
}

const eventResponse = {
  id: 'event-1',
  event_type: 'wedding',
  title: 'Nagpur wedding',
  currency: 'INR',
  budget_limit_minor: 60_000_000,
  event_date: '2027-04-10',
  location_label: 'Nagpur',
  current_version_no: 1,
  revision: 2,
  created_at: '2026-10-01T00:00:00Z',
  summary: {
    version_no: 1,
    guest_count: 150,
    venue_capacity: 180,
    seats_per_table: 10,
    preferences: { priorities: ['good food', 'live music'] },
    budget_categories: [
      { logical_id: 'food', name: 'Catering', planned_minor: 15_000_000, source: 'user' },
    ],
    tasks: [
      { logical_id: 'venue', title: 'Confirm venue', status: 'blocked', priority: 'high', dependencies: ['date'] },
    ],
    vendors: [
      {
        logical_id: 'venue-vendor', category: 'venue', display_name: 'Garden venue',
        contact_name: 'Asha', status: 'shortlisted_by_user', information_source: 'user_entered',
        quotes: [{ amount_minor: 12_000_000 }],
      },
    ],
  },
};

describe('typed live API adapter', () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.mocked(eventHeaders).mockClear();
    vi.mocked(setEventEtag).mockClear();
  });

  it('maps event summaries without losing backend task and vendor states', async () => {
    respondWith(eventResponse);

    const result = await liveApi.getEvent('event-1');

    expect(result.data).toMatchObject({
      id: 'event-1',
      guestCount: 150,
      priorities: ['good food', 'live music'],
      categories: [{ id: 'food', plannedMinor: 15_000_000, provenance: 'user_entered' }],
      tasks: [{ id: 'venue', status: 'blocked', priority: 'high', dependencies: ['date'] }],
      vendors: [{ id: 'venue-vendor', status: 'shortlisted', quoteMinor: 12_000_000 }],
    });
    expect(requestMock).toHaveBeenCalledWith('/events/event-1?include=summary');
  });

  it('maps a plan draft and retains its validated payload for explicit save', async () => {
    respondWith(eventResponse, {
      concept: { title: 'A garden wedding', description: 'An intimate garden celebration.' },
      assumptions: ['Costs are illustrative.'],
      unknowns: ['Venue capacity'],
      budget_categories: [{ key: 'food', name: 'Catering', planned_minor: 15_000_000, source: 'accepted_ai_suggestion' }],
      budget_items: [{ category_key: 'food', label: 'Dinner', quantity: 150, quantity_basis: 'guest_count', planned_minor: 15_000_000 }],
      tasks: [{ key: 'book-venue', title: 'Book a venue', status: 'not_started', priority: 'medium', depends_on_keys: [] }],
      vendor_categories: [{ key: 'caterer', category: 'catering', why: 'Meal service' }],
      ideas: ['Use seasonal flowers.'],
      ai_status: { mode: 'live' },
    });

    const result = await liveApi.generatePlanDraft('event-1');

    expect(result.data).toMatchObject({
      eventId: 'event-1',
      concept: 'An intimate garden celebration.',
      aiStatus: 'live',
      budgetItems: [{ label: 'Dinner', quantity: 150, plannedMinor: 15_000_000 }],
      tasks: [{ id: 'book-venue', status: 'not_started' }],
      ideas: ['Use seasonal flowers.'],
    });
    expect(requestMock.mock.calls.map(([path]) => path)).toEqual([
      '/events/event-1?include=summary',
      '/events/event-1/plan-drafts',
    ]);
  });

  it('maps scenario warnings and capacity states through typed DTOs', async () => {
    respondWith(eventResponse, {
      scenarios: [{
        name: '200 guests',
        budget_summary: { after: { planned_minor: 63_000_000 }, planned_delta_minor: 5_000_000 },
        capacity_summary: { after: { required_tables: 20, state: 'exceeded' } },
        warnings: [{ message: 'Venue capacity would be exceeded.' }],
        blockers: [],
      }],
    });

    const result = await liveApi.compareScenarios('event-1', [200]);

    expect(result.data).toEqual([{
      name: '200 guests', guestCount: 200, totalMinor: 63_000_000, deltaMinor: 5_000_000,
      tables: 20, capacityState: 'exceeded', warnings: ['Venue capacity would be exceeded.'], blockers: [],
    }]);
  });

  it('uses the updated vendor returned by Flask without a follow-up read', async () => {
    respondWith({
      logical_id: 'vendor-1', category: 'venue', display_name: 'Garden venue',
      contact_name: 'Asha', status: 'contacted_by_user', information_source: 'user_entered',
      notes: 'Called on Monday.', quotes: [],
    });

    const result = await liveApi.updateVendor('event-1', 'vendor-1', {
      status: 'contacted', note: 'Called on Monday.',
    });

    expect(result.data).toMatchObject({
      id: 'vendor-1', name: 'Garden venue', contact: 'Asha', status: 'contacted', note: 'Called on Monday.',
    });
    expect(requestMock).toHaveBeenCalledTimes(1);
    expect(requestMock.mock.calls[0]?.[1]).toMatchObject({ method: 'PATCH' });
    expect(JSON.parse(String(requestMock.mock.calls[0]?.[1]?.body))).toEqual({
      status: 'contacted_by_user', notes: 'Called on Monday.',
    });
  });

  it('returns the created vendor from Flask instead of guessing from event ordering', async () => {
    respondWith({
      logical_id: 'vendor-2', category: 'catering', display_name: 'New supplier',
      status: 'to_find', information_source: 'user_entered', notes: '', quotes: [],
    });

    const result = await liveApi.addVendor('event-1', 'Catering', 'New supplier');

    expect(result.data).toMatchObject({ id: 'vendor-2', category: 'catering', name: 'New supplier' });
    expect(requestMock).toHaveBeenCalledTimes(1);
    expect(requestMock.mock.calls[0]?.[1]).toMatchObject({ method: 'POST' });
  });

  it('returns typed Copilot references without an unchecked response cast', async () => {
    respondWith({ answer: 'Catering is the largest planned category.', known_references: ['budget.categories.catering'] });

    const result = await liveApi.answerCopilot('event-1', 'What is the largest category?');

    expect(result.data).toEqual({
      answer: 'Catering is the largest planned category.',
      references: ['budget.categories.catering'],
    });
  });
});
