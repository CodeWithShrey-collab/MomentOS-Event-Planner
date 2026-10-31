import { beforeEach, describe, expect, it } from 'vitest';
import { DEMO_EVENTS, totalPlanned } from '../data/demoData';
import { offlineDemoApi as demoApi, formatRupees, parseRupeesToMinor, resetDemoDataForTests } from './demoApi';

describe('offline demo planning services', () => {
  beforeEach(() => resetDemoDataForTests());

  it('parses rupees into paise without accepting malformed amounts', () => {
    expect(parseRupeesToMinor('6,00,000')).toBe(60_000_000);
    expect(parseRupeesToMinor('₹80,000.50')).toBe(8_000_050);
    expect(parseRupeesToMinor('80,000.555')).toBeNull();
    expect(formatRupees(60_000_000)).toContain('6,00,000');
  });

  it('reconciles the wedding demo baseline exactly', () => {
    const wedding = DEMO_EVENTS[0]!;
    expect(totalPlanned(wedding.categories)).toBe(58_000_000);
    expect(wedding.categories.find((category) => category.id === 'food')?.ratePerGuestMinor).toBe(100_000);
  });

  it('returns a read-only Ripple preview with the guest-count impact trail', async () => {
    const event = DEMO_EVENTS[0]!;
    const response = await demoApi.previewRipple(event.id, 'guest_count', 200);
    const preview = response.data;
    expect(preview.deltaMinor).toBe(5_000_000);
    expect(preview.afterTotalMinor).toBe(63_000_000);
    expect(preview.changes.find((change) => change.label === 'Food & catering')?.after).toContain('2,00,000');
    expect(preview.changes.find((change) => change.label === 'Tables to arrange')?.after).toBe('20');
    expect(preview.blockers).toHaveLength(2);
    expect(preview.unknowns).toContain('Invitation count needs a per-person or per-household rule.');
    const unchanged = await demoApi.getEvent(event.id);
    expect(unchanged.data.guestCount).toBe(150);
    expect(unchanged.data.revision).toBe(event.revision);
  });

  it('requires confirmation and a fresh valid preview before saving', async () => {
    const event = DEMO_EVENTS[0]!;
    const preview = (await demoApi.previewRipple(event.id, 'guest_count', 160)).data;
    await expect(demoApi.commitRipple(preview, false)).rejects.toMatchObject({ code: 'confirmation_required' });
    const unchanged = await demoApi.getEvent(event.id);
    expect(unchanged.data.guestCount).toBe(150);
    const committed = await demoApi.commitRipple(preview, true);
    expect(committed.data.guestCount).toBe(160);
    expect(committed.data.revision).toBe(event.revision + 1);
    expect(totalPlanned(committed.data.categories)).toBe(59_000_000);
  });

  it('rejects a stale preview after another update changes the event revision', async () => {
    const event = DEMO_EVENTS[0]!;
    const preview = (await demoApi.previewRipple(event.id, 'guest_count', 160)).data;
    await demoApi.updateCategory(event.id, 'decor', 7_600_000);
    await expect(demoApi.commitRipple(preview, true)).rejects.toMatchObject({ code: 'stale_simulation', status: 412 });
  });
});
