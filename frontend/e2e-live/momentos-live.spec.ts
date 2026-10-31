import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const screenshots = join(process.cwd(), 'test-artifacts', 'stage07');
const captureFailureState = (page: import('@playwright/test').Page) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  let expectedUnauthenticatedSessionProbe = false;
  page.on('response', (response) => {
    if (response.status() === 401 && new URL(response.url()).pathname === '/api/v1/session') expectedUnauthenticatedSessionProbe = true;
  });
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    if (expectedUnauthenticatedSessionProbe && message.text().includes('401 (UNAUTHORIZED)')) {
      expectedUnauthenticatedSessionProbe = false;
      return;
    }
    consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => consoleErrors.push(error.name));
  page.on('requestfailed', (request) => failedRequests.push(`${request.method()} ${new URL(request.url()).pathname}`));
  return { consoleErrors, failedRequests };
};

async function createWedding(page: import('@playwright/test').Page, note = 'User-approved editable catering assumption: 100000 minor units per guest. This is not a vendor quote.') {
  await page.goto('/events/new?type=wedding');
  await page.getByLabel(/give it a name/i).fill('Nagpur Garden Wedding');
  await page.getByLabel(/guests or attendees/i).fill('150');
  await page.getByLabel(/budget in rupees/i).fill('600000');
  await page.getByLabel(/tell us a little more/i).fill(note);
  await page.getByRole('button', { name: /prepare my plan/i }).click();
  await expect(page.getByText('Mock provider · no live request')).toBeVisible();
  await expect(page.getByText('Catering per guest')).toBeVisible();
  await expect(page.getByText('Confirm venue capacity')).toBeVisible();
  await page.getByRole('button', { name: /save this plan/i }).click();
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toContainText('structured mock response for testing');
  await dialog.getByRole('button', { name: 'Confirm and save' }).click();
  await expect(page).toHaveURL(/\/events\/[0-9a-f-]{36}$/);
  return page.url().match(/\/events\/([0-9a-f-]{36})$/)?.[1] ?? '';
}

test('real React-to-Flask wedding flow uses validated mocked provider output and isolates sessions', async ({ page, browser }) => {
  const diagnostics = captureFailureState(page);
  const planDraftRequests: string[] = [];
  const copilotRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/plan-drafts')) planDraftRequests.push(request.method());
    if (request.url().includes('/copilot')) copilotRequests.push(request.method());
  });

  const eventId = await createWedding(page);
  expect(eventId).not.toBe('');
  await expect(page.getByText('Saved to your workspace')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Nagpur Garden Wedding' })).toBeVisible();
  await expect(page.getByText(/150 guests/).first()).toBeVisible();
  const savedEventResponse = await page.evaluate(async (id) => {
    const response = await fetch(`/api/v1/events/${encodeURIComponent(id)}?include=summary`, { credentials: 'include' });
    return { status: response.status, body: await response.json() as { data: { summary: { budget_items: Array<{ label: string; quantity: string; quantity_basis: string; unit_rate_minor: number; planned_minor: number }> } } } };
  }, eventId);
  expect(savedEventResponse.status).toBe(200);
  const savedEvent = savedEventResponse.body.data;
  expect(savedEvent.summary.budget_items).toEqual(expect.arrayContaining([
    expect.objectContaining({ label: 'Catering per guest', quantity: '150.000', quantity_basis: 'guest_count', unit_rate_minor: 100_000, planned_minor: 15_000_000 }),
  ]));

  await page.getByRole('link', { name: /Budget studio/i }).click();
  await expect(page.getByRole('heading', { name: 'Budget studio' })).toBeVisible();
  await expect(page.locator('.budget-table-row').filter({ hasText: 'Catering' })).toBeVisible();
  const venueRow = page.locator('.budget-table-row').filter({ hasText: 'Venue' });
  await venueRow.getByLabel('Planned amount for Venue').fill('125000');
  await venueRow.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByText('Budget updated')).toBeVisible();

  await page.getByRole('link', { name: 'Ripple engine', exact: true }).click();
  await expect(page.getByText('Current plan: 150 guests')).toBeVisible();
  const guestCount = page.getByLabel(/try a new number of guests/i);
  await guestCount.fill('200');
  await page.getByRole('button', { name: /show me what changes/i }).click();
  await expect(page.getByRole('heading', { name: 'At 200 guests' })).toBeVisible();
  await expect(page.getByText('+ ₹50,000')).toBeVisible();
  await expect(page.getByText('Preview only · not saved')).toBeVisible();
  await page.getByRole('button', { name: 'Discard preview' }).click();
  await expect(page.getByText('Current plan: 150 guests')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Current plan: 150 guests')).toBeVisible();

  await guestCount.fill('200');
  await page.getByRole('button', { name: /show me what changes/i }).click();
  await expect(page.getByText('+ ₹50,000')).toBeVisible();
  await page.getByRole('button', { name: /review and confirm/i }).click();
  const confirm = page.getByRole('alertdialog');
  await expect(confirm).toContainText('This preview will be saved only after you confirm.');
  await confirm.getByRole('button', { name: 'Save this change' }).click();
  await expect(page.getByText('Current plan: 200 guests')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Current plan: 200 guests')).toBeVisible();

  await page.getByRole('link', { name: /Moment map/i }).click();
  const taskButton = page.getByRole('button', { name: /^Mark complete:/i }).first();
  await taskButton.click();
  await expect(page.getByText('Task status updated')).toBeVisible();

  await page.getByRole('link', { name: 'Vendors', exact: true }).click();
  const vendorStatus = page.locator('select[id^="vendor-status-"]').first();
  await vendorStatus.selectOption('contacted');
  await expect(page.getByText('Vendor details saved')).toBeVisible();
  await expect(vendorStatus).toHaveValue('contacted');

  await page.getByRole('link', { name: 'Compare plans', exact: true }).click();
  await page.getByLabel('Option one').fill('130');
  await page.getByLabel('Option two').fill('210');
  await page.getByRole('button', { name: 'Compare options' }).click();
  await expect(page.getByRole('heading', { name: 'Same celebration, different shape.' })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Projected event scenario comparison' })).toBeVisible();

  await page.getByRole('link', { name: /Command center/i }).click();
  const copilotLauncher = page.locator('.copilot-launch');
  await copilotLauncher.focus();
  await page.keyboard.press('Enter');
  const copilot = page.getByRole('dialog', { name: 'A little more clarity' });
  await expect(copilot).toBeVisible();
  const questionInput = page.getByLabel('Ask a question about your event');
  const copilotClose = copilot.getByRole('button', { name: 'Close assistant' });
  await expect(questionInput).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(copilotClose).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(questionInput).toBeFocused();
  await questionInput.fill('How many guests are in my saved plan?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByText('The saved plan is for 200 guests.')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(copilot).toBeHidden();
  await expect(copilotLauncher).toBeFocused();

  expect(planDraftRequests).toEqual(['POST']);
  expect(copilotRequests).toEqual(['POST']);
  const observationsResponse = await page.request.get('http://127.0.0.1:5002/__test__/ai-calls');
  expect(observationsResponse.ok()).toBeTruthy();
  const observations = await observationsResponse.json() as Array<{ operation: string; context_fields: string[]; known_fact_fields: string[] }>;
  const copilotObservation = observations.find((entry) => entry.operation === 'answer_event_question');
  expect(copilotObservation).toBeDefined();
  expect(copilotObservation?.context_fields).toContain('guest_count');
  expect(copilotObservation?.context_fields).not.toContain('notes');
  expect(copilotObservation?.context_fields).not.toContain('email');
  expect(copilotObservation?.context_fields).not.toContain('phone');
  expect(copilotObservation?.known_fact_fields).not.toContain('user_notes');

  const strangerContext = await browser.newContext();
  const strangerPage = await strangerContext.newPage();
  await strangerPage.goto('/');
  const foreignStatus = await strangerPage.evaluate(async (id) => {
    await fetch('/api/v1/session', { method: 'POST', credentials: 'include' });
    return (await fetch(`/api/v1/events/${id}`, { credentials: 'include' })).status;
  }, eventId);
  expect(foreignStatus).toBe(404);
  await strangerContext.close();

  expect(diagnostics.failedRequests).toEqual([]);
  expect(diagnostics.consoleErrors).toEqual([]);
});

test('main screens render without horizontal overflow and pass axe at requested viewports', async ({ page }) => {
  test.setTimeout(240_000);
  await mkdir(screenshots, { recursive: true });
  const eventId = await createWedding(page, 'A visually clean audit assumption: rate 100000 minor units per guest. Editable, not a quote.');
  const screens = [
    { name: 'landing', path: '/' },
    { name: 'architect', path: '/events/new?type=wedding' },
    { name: 'command-center', path: `/events/${eventId}` },
    { name: 'budget-studio', path: `/events/${eventId}/budget` },
    { name: 'ripple-engine', path: `/events/${eventId}/ripple` },
    { name: 'moment-map', path: `/events/${eventId}/map` },
    { name: 'vendors', path: `/events/${eventId}/vendors` },
    { name: 'scenario-comparison', path: `/events/${eventId}/scenarios` },
    { name: 'ai-copilot', path: `/events/${eventId}`, copilot: true },
  ];
  const viewports = [
    { name: 'desktop-1440x900', width: 1440, height: 900 },
    { name: 'laptop-1366x768', width: 1366, height: 768 },
    { name: 'tablet-768x1024', width: 768, height: 1024 },
    { name: 'mobile-390x844', width: 390, height: 844 },
  ];

  for (const viewport of viewports) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    for (const screen of screens) {
      await page.goto(screen.path);
      await page.waitForLoadState('networkidle');
      if (screen.copilot) {
        if (viewport.width <= 768) await page.getByRole('button', { name: 'Open navigation' }).click();
        await page.locator('.copilot-launch').click();
        await expect(page.getByRole('dialog', { name: 'A little more clarity' })).toBeVisible();
      }
      const dimensions = await page.evaluate(() => ({
        viewport: window.innerWidth,
        document: document.documentElement.scrollWidth,
        body: document.body.scrollWidth,
      }));
      expect(dimensions.document, `${screen.name} overflows at ${viewport.name}`).toBeLessThanOrEqual(viewport.width + 1);
      expect(dimensions.body, `${screen.name} body overflows at ${viewport.name}`).toBeLessThanOrEqual(viewport.width + 1);
      const path = join(screenshots, `${screen.name}-${viewport.name}.jpg`);
      await page.screenshot({ path, type: 'jpeg', quality: 62, fullPage: true, animations: 'disabled' });
      if (viewport.name === 'desktop-1440x900' || viewport.name === 'mobile-390x844') {
        const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
        const summarizedViolations = scan.violations.map(({ id, impact, description, nodes }) => ({ id, impact, description, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }));
        expect(summarizedViolations, `${screen.name} axe violations at ${viewport.name}`).toEqual([]);
      }
    }
    if (viewport.width <= 768) {
      await page.goto(`/events/${eventId}`);
      const menuButton = page.getByRole('button', { name: 'Open navigation' });
      await menuButton.click();
      await expect(menuButton).toHaveAttribute('aria-expanded', 'true');
      await expect(page.getByRole('button', { name: 'Close navigation', exact: true })).toBeFocused();
      await page.keyboard.press('Escape');
      await expect(menuButton).toHaveAttribute('aria-expanded', 'false');
      await expect(menuButton).toBeFocused();
    }
  }

});

test('captures the Ripple Engine contrast remediation before and after', async ({ page }) => {
  test.setTimeout(60_000);
  await mkdir(screenshots, { recursive: true });
  const eventId = await createWedding(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/events/${eventId}/ripple`);
  await page.waitForLoadState('networkidle');

  // Recreate the audited pre-fix muted text values so the comparison shows
  // the specific contrast remediation; the application source stays current.
  const priorPalette = await page.addStyleTag({ content: `
    .ripple-intro-banner p { color: #837982 !important; }
    #ripple-input-help { color: #9a918b !important; }
    .ripple-context p { color: #82776b !important; }
    .ripple-current-facts > span { color: #9a8f88 !important; }
    .ripple-current-facts small { color: #9c928c !important; }
    .ripple-empty > p:not(.eyebrow) { color: #908580 !important; }
    .ripple-empty-steps, .ripple-empty-steps > span, .ripple-empty-steps > svg { color: #aaa09a !important; }
  ` });
  await page.screenshot({ path: join(screenshots, 'before-ripple-contrast-remediation.jpg'), type: 'jpeg', quality: 72, fullPage: true });
  await priorPalette.evaluate((element) => element.remove());
  await page.screenshot({ path: join(screenshots, 'after-ripple-contrast-remediation.jpg'), type: 'jpeg', quality: 72, fullPage: true });
});
