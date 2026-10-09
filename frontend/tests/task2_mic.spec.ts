import { test, expect } from '@playwright/test';

test.describe('Task 2: Live Microphone Detection & Honest Empty States', () => {
  test.beforeEach(async ({ request }) => {
    // Clear history before each test
    await request.delete('/api/v1/history');
  });

  test('mic stream runs for >12s, moves level meter, scores points, and Stop persists to History', async ({ page, request }) => {
    test.setTimeout(120000);

    await page.goto('/');

    const tapBtn = page.getByRole('button', { name: /Tap here to detect AI or fake audio/i });
    await expect(tapBtn).toBeVisible();
    await tapBtn.click();

    // Must show Listening / Collecting
    await expect(page.locator('text=Listening').first()).toBeVisible({ timeout: 5000 });

    // Assert level meter is rendered and active
    const meterBar = page.locator('.mic-level-bar');
    await expect(meterBar).toBeVisible();

    // Verify still on live view after 12 seconds
    await page.waitForTimeout(13000);
    await expect(page.locator('button:has-text("Stop & View Results")')).toBeVisible();

    // Verify at least 2 scored points exist (either dots in SVG or Analyzed >= 2 in summary)
    const analyzedEl = page.locator('text=Analyzed:').locator('..').locator('strong');
    await expect(analyzedEl).toBeVisible();
    const analyzedText = await analyzedEl.innerText();
    const analyzedNum = parseInt(analyzedText, 10);
    expect(analyzedNum).toBeGreaterThanOrEqual(2);

    // Also verify SVG dots exist for raw scores
    const dots = page.locator('svg circle[r="2"]');
    const dotCount = await dots.count();
    expect(dotCount).toBeGreaterThanOrEqual(2);

    // Press Stop & View Results
    const stopBtn = page.locator('button:has-text("Stop & View Results")');
    await stopBtn.click();

    // Verify results page stays visible and shows "Analysis complete"
    await expect(page.locator('text=Analysis complete: Microphone')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Windows Analyzed')).toBeVisible();

    // Verify exactly one History row was created with source "live"
    await expect.poll(async () => {
      const res = await request.get('/api/v1/history');
      if (!res.ok()) return 0;
      const data = await res.json();
      return data.history.length;
    }, { timeout: 10000, intervals: [300, 600, 1000] }).toBe(1);

    const historyRes = await request.get('/api/v1/history');
    expect(historyRes.ok()).toBeTruthy();
    const historyData = await historyRes.json();
    expect(historyData.history.length).toBe(1);
    expect(historyData.history[0].source).toBe('live');
    expect(historyData.history[0].windows_analysed).toBeGreaterThanOrEqual(2);
    expect(historyData.history[0].duration_s).toBeGreaterThanOrEqual(12.0);
  });

  test('aborted short session (<5s) shows honest empty state and creates no History row', async ({ page, request }) => {
    test.setTimeout(60000);

    // Ensure database is clean
    await request.delete('/api/v1/history');

    await page.goto('/');

    const tapBtn = page.getByRole('button', { name: /Tap here to detect AI or fake audio/i });
    await tapBtn.click();

    await expect(page.locator('text=Listening').first()).toBeVisible({ timeout: 5000 });

    // Stop after only 2 seconds
    await page.waitForTimeout(2000);
    const stopBtn = page.locator('button:has-text("Stop & View Results")');
    await stopBtn.click();

    // Must show Honest Empty State
    await expect(page.locator('text=Not enough audio: Microphone')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=need at least 5 s of speech to score')).toBeVisible();

    // Dash '—' displayed instead of 0%
    await expect(page.getByText('—').first()).toBeVisible();

    // Save to History button must be disabled
    const saveBtn = page.getByRole('button', { name: /Save to History/i });
    await expect(saveBtn).toBeDisabled();

    // Give backend socket close 1.5s to ensure nothing is written
    await page.waitForTimeout(1500);

    // Assert no row in history
    const historyRes = await request.get('/api/v1/history');
    expect(historyRes.ok()).toBeTruthy();
    const historyData = await historyRes.json();
    expect(historyData.history.length).toBe(0);
  });
});
