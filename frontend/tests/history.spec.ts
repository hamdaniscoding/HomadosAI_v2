import { test, expect } from '@playwright/test';

test.describe('History', () => {
  test('upload a file and view it in history', async ({ page }) => {
    // 1. Upload file
    await page.goto('/');
    
    await page.locator('input[type="file"]').first().setInputFiles('../data/human/h1.wav');
    
    // Wait for "Analysis complete"
    await expect(page.locator('text=Analysis complete').first()).toBeVisible({ timeout: 300000 });
    
    // 2. Open History
    await page.getByRole('link', { name: 'History' }).click();
    
    // 3. Check row has file name
    await expect(page.locator('text=h1.wav').first()).toBeVisible();
    
    // Avg % should be visible
    await expect(page.getByText('Avg').first()).toBeVisible();
    
  });
});
