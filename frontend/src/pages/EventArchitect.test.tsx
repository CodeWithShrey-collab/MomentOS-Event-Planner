import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../hooks/useToast';
import { demoApi } from '../services/demoApi';
import type { EventRecord, PlanDraft } from '../types';
import { EventArchitect } from './EventArchitect';

describe('EventArchitect', () => {
  it('keeps required details clear and gives field-level validation on submit', () => {
    render(<MemoryRouter initialEntries={['/events/new']}><ToastProvider><EventArchitect /></ToastProvider></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: /prepare my plan/i }));
    expect(screen.getByText('Give your event a name of at least two characters.')).toBeInTheDocument();
    expect(screen.getByLabelText(/guests or attendees/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/tell us a little more/i)).toBeInTheDocument();
  });

  it('labels live blueprint generation and server persistence accurately', async () => {
    const event: EventRecord = {
      id: 'live-event-1', eventType: 'wedding', title: 'Nagpur Wedding', currency: 'INR',
      budgetLimitMinor: 60_000_000, eventDate: '', city: 'Nagpur', guestCount: 150,
      venueCapacity: null, seatsPerTable: null, invitationUnit: 'unknown', revision: 0,
      versionNumber: 0, createdAt: '', categories: [], tasks: [], vendors: [], concept: '',
      priorities: [], theme: '', notes: '', accepted: false,
    };
    const draft: PlanDraft = {
      eventId: event.id, concept: 'An elegant gathering with thoughtful details.', assumptions: [],
      unknowns: [], categories: [], tasks: [], vendors: [], ideas: [], aiStatus: 'live',
    };
    vi.spyOn(demoApi, 'createEvent').mockResolvedValue({ data: event, request_id: 'test' });
    vi.spyOn(demoApi, 'generatePlanDraft').mockResolvedValue({ data: draft, request_id: 'test' });

    render(<MemoryRouter initialEntries={['/events/new']}><ToastProvider><EventArchitect /></ToastProvider></MemoryRouter>);
    fireEvent.change(screen.getByLabelText(/give it a name/i), { target: { value: 'Nagpur Wedding' } });
    fireEvent.click(screen.getByRole('button', { name: /prepare my plan/i }));

    expect(await screen.findByText('GPT-6 Luna · live blueprint')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /save this plan/i }));
    expect(screen.getByText(/saved to your event workspace/i)).toBeInTheDocument();
    expect(screen.getByText(/becomes your saved plan only after you confirm/i)).toBeInTheDocument();
  });
});
