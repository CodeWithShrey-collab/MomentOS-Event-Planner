import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../hooks/useToast';
import { demoApi } from '../services/demoApi';
import type { EventRecord } from '../types';
import { VendorsPage } from './WorkspacePages';

const event: EventRecord = {
  id: 'event-1', eventType: 'wedding', title: 'Garden wedding', currency: 'INR',
  budgetLimitMinor: 6_000_000, eventDate: '', city: 'Nagpur', guestCount: 150,
  venueCapacity: null, seatsPerTable: null, invitationUnit: 'unknown', revision: 1,
  versionNumber: 1, createdAt: '', categories: [], tasks: [], vendors: [{
    id: 'vendor-1', category: 'catering', name: null, contact: null, status: 'to_find',
    estimateMinor: null, quoteMinor: null, provenance: 'suggested', note: '',
    followUpChecklist: ['Ask about dietary options'],
  }], concept: '', priorities: [], theme: '', notes: '', accepted: true,
};

afterEach(() => vi.restoreAllMocks());

describe('VendorsPage', () => {
  it('shows an error and never a success message when quote persistence fails', async () => {
    const updateEvent = vi.fn();
    vi.spyOn(demoApi, 'saveVendorQuote').mockRejectedValue(new Error('The service rejected the quote.'));

    render(
      <MemoryRouter>
        <ToastProvider>
          <VendorsPage event={event} onEventUpdated={updateEvent} />
        </ToastProvider>
      </MemoryRouter>,
    );

    const input = screen.getByPlaceholderText('Add quote');
    fireEvent.change(input, { target: { value: '12,500.50' } });
    fireEvent.blur(input);

    expect(await screen.findByText('Could not verify or save vendor quote')).toBeInTheDocument();
    expect(screen.getByText('The service rejected the quote.')).toBeInTheDocument();
    expect(screen.queryByText('Vendor quote saved')).not.toBeInTheDocument();
    expect(demoApi.saveVendorQuote).toHaveBeenCalledWith('event-1', 'vendor-1', 1_250_050, 'INR');
    await waitFor(() => expect(updateEvent).not.toHaveBeenCalled());
  });

  it('renders generated vendor follow-up guidance in the existing checklist row', () => {
    render(
      <MemoryRouter>
        <ToastProvider>
          <VendorsPage event={event} onEventUpdated={vi.fn()} />
        </ToastProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText('Suggested follow-up')).toBeInTheDocument();
    expect(screen.getByText('Ask about dietary options')).toBeInTheDocument();
  });
});
