import { expect, test } from '@playwright/test';

test('plans, previews, cancels, confirms, reloads, and updates a wedding workspace', async ({ page }) => {
  await page.goto('/events/new?type=wedding');
  await page.getByLabel(/give it a name/i).fill('Nagpur Wedding Browser Test');
  await expect(page.getByLabel(/guests or attendees/i)).toHaveValue('150');
  await expect(page.getByLabel(/budget in rupees/i)).toHaveValue('600000');
  await page.getByRole('button', { name: /prepare my plan/i }).click();

  await expect(page.getByText('Offline demo · sample blueprint')).toBeVisible();
  await page.getByRole('button', { name: /save this plan/i }).click();
  const planDialog = page.getByRole('alertdialog');
  await expect(planDialog).toContainText('saved to your event workspace');
  await expect(planDialog).toContainText('no live OpenAI response was generated');
  await planDialog.getByRole('button', { name: 'Confirm and save' }).click();

  await expect(page).toHaveURL(/\/events\/[^/]+$/);
  await expect(page.getByText('Saved to your workspace')).toBeVisible();

  await page.getByRole('link', { name: 'Ripple engine', exact: true }).click();
  const guestCount = page.getByLabel(/try a new number of guests/i);
  await guestCount.fill('200');
  await page.getByRole('button', { name: /show me what changes/i }).click();
  await expect(page.getByRole('heading', { name: 'At 200 guests' })).toBeVisible();
  await expect(page.getByText('Preview only · not saved')).toBeVisible();
  await page.getByRole('button', { name: 'Discard preview' }).click();
  await expect(page.getByText('One change.', { exact: false })).toBeVisible();
  await page.reload();
  await expect(page.getByText('Current plan: 150 guests')).toBeVisible();

  await guestCount.fill('200');
  await page.getByRole('button', { name: /show me what changes/i }).click();
  await expect(page.getByRole('heading', { name: 'At 200 guests' })).toBeVisible();
  await page.getByRole('button', { name: /review and confirm/i }).click();
  const rippleDialog = page.getByRole('alertdialog');
  await expect(rippleDialog).toContainText('This preview will be saved only after you confirm.');
  await rippleDialog.getByRole('button', { name: 'Save this change' }).click();
  await expect(page.getByText('Change saved')).toBeVisible();
  await expect(page.getByText('Current plan: 200 guests')).toBeVisible();
  await page.reload();
  await expect(page.getByText('Current plan: 200 guests')).toBeVisible();

  await page.getByRole('link', { name: /Moment map/i }).click();
  const firstTask = page.getByRole('button', { name: /^Mark complete:/i }).first();
  await firstTask.click();
  await expect(page.getByText('Task status updated')).toBeVisible();
  await expect(page.getByText('You completed').first()).toBeVisible();

  await page.getByRole('link', { name: 'Vendors', exact: true }).click();
  const firstVendorStatus = page.locator('select[id^="vendor-status-"]').first();
  await firstVendorStatus.selectOption('contacted');
  await expect(page.getByText('Vendor details saved')).toBeVisible();
  await expect(firstVendorStatus).toHaveValue('contacted');

  await page.locator('.copilot-launch').click();
  await page.getByLabel('Ask a question about your event').fill('How many guests are in this event?');
  await page.getByRole('button', { name: 'Send question' }).click();
  await expect(page.getByText(/offline demo response; OpenAI was not called/i)).toBeVisible();
});
