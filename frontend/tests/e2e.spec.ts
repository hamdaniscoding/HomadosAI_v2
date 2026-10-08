import { test, expect } from '@playwright/test';
import * as path from 'path';

test.describe('Homados AI E2E', () => {
  test('full user flow', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', err => errors.push(err.message));
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Go to home
    await page.goto('/');
    
    // Check hero and nav
    await expect(page.locator('text=Is that voice real?')).toBeVisible();
    await expect(page.locator('text=Detector ready')).toBeVisible({ timeout: 10000 });
    
    // Screen idle at 1280
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.screenshot({ path: '../docs/screens/idle-1280.png' });
    // Screen idle at 390
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: '../docs/screens/idle-390.png' });
    await page.setViewportSize({ width: 1280, height: 800 });

    // Enable Save session
    await page.locator('text=Save this session to History').click();
    
    // Upload file
    const fileInput = page.locator('input[type="file"]').first();
    const filePath = path.resolve(process.cwd(), '../data/human/h1.mp3');
    await fileInput.setInputFiles(filePath);
    
    // Check Collecting state
    await expect(page.locator('text=Collecting audio')).toBeVisible();
    await page.screenshot({ path: '../docs/screens/collecting-1280.png' });

    // Canvas cursor logic check
    const canvas = page.locator('canvas');
    await canvas.waitFor({ state: 'visible' });
    const box = await canvas.boundingBox();
    if (box) {
      await page.mouse.move(box.x + 100, box.y + 100);
      await page.waitForTimeout(500);
      const s1 = await canvas.screenshot();
      await page.mouse.move(box.x + 500, box.y + 500);
      await page.waitForTimeout(500);
      const s2 = await canvas.screenshot();
      expect(s1).not.toEqual(s2);
    }
    
    // Wait for Score Live
    await expect(page.locator('text=smoothed over last 5').or(page.locator('text=raw'))).toBeVisible({ timeout: 15000 });
    await page.screenshot({ path: '../docs/screens/live-1280.png' });
    
    // Check uncalibrated pill
    await expect(page.locator('text=Uncalibrated, score only')).toBeVisible();

    // Stop
    await page.locator('button:has-text("Stop")').click();

    // Go to history
    await page.locator('text=History').click();
    await expect(page.locator('text=Mean Score').first()).toBeVisible({ timeout: 5000 });
    await page.screenshot({ path: '../docs/screens/history-1280.png' });

    // Go to How it works
    await page.locator('text=How it works').click();
    await expect(page.locator('text=We convert everything to 16 kHz mono.')).toBeVisible();
    await page.screenshot({ path: '../docs/screens/how-it-works-1280.png' });

    // Go to About
    await page.locator('text=About').click();
    await expect(page.locator('text=Smart India Hackathon 2026')).toBeVisible();
    await page.screenshot({ path: '../docs/screens/about-1280.png' });

    // Check errors
    expect(errors.length).toBe(0);
  });
});
