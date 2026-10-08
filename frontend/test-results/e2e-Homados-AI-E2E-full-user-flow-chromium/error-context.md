# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: e2e.spec.ts >> Homados AI E2E >> full user flow
- Location: tests\e2e.spec.ts:5:3

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:5173/
Call log:
  - navigating to "http://127.0.0.1:5173/", waiting until "load"

```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | import * as path from 'path';
  3  | 
  4  | test.describe('Homados AI E2E', () => {
  5  |   test('full user flow', async ({ page }) => {
  6  |     const errors: string[] = [];
  7  |     page.on('pageerror', err => errors.push(err.message));
  8  |     page.on('console', msg => {
  9  |       if (msg.type() === 'error') {
  10 |         errors.push(msg.text());
  11 |       }
  12 |     });
  13 | 
  14 |     // Go to home
> 15 |     await page.goto('/');
     |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://127.0.0.1:5173/
  16 |     
  17 |     // Check hero and nav
  18 |     await expect(page.locator('text=Is that voice real?')).toBeVisible();
  19 |     await expect(page.locator('text=Detector ready')).toBeVisible({ timeout: 10000 });
  20 |     
  21 |     // Screen idle at 1280
  22 |     await page.setViewportSize({ width: 1280, height: 800 });
  23 |     await page.screenshot({ path: '../docs/screens/idle-1280.png' });
  24 |     // Screen idle at 390
  25 |     await page.setViewportSize({ width: 390, height: 844 });
  26 |     await page.screenshot({ path: '../docs/screens/idle-390.png' });
  27 |     await page.setViewportSize({ width: 1280, height: 800 });
  28 | 
  29 |     // Enable Save session
  30 |     await page.locator('text=Save this session to History').click();
  31 |     
  32 |     // Upload file
  33 |     const fileInput = page.locator('input[type="file"]').first();
  34 |     const filePath = path.resolve(__dirname, '../../../data/human/h1.mp3');
  35 |     await fileInput.setInputFiles(filePath);
  36 |     
  37 |     // Check Collecting state
  38 |     await expect(page.locator('text=Collecting audio')).toBeVisible();
  39 |     await page.screenshot({ path: '../docs/screens/collecting-1280.png' });
  40 | 
  41 |     // Canvas cursor logic check
  42 |     const canvas = page.locator('canvas');
  43 |     await canvas.waitFor({ state: 'visible' });
  44 |     const box = await canvas.boundingBox();
  45 |     if (box) {
  46 |       await page.mouse.move(box.x + 100, box.y + 100);
  47 |       await page.waitForTimeout(500);
  48 |       const s1 = await canvas.screenshot();
  49 |       await page.mouse.move(box.x + 500, box.y + 500);
  50 |       await page.waitForTimeout(500);
  51 |       const s2 = await canvas.screenshot();
  52 |       expect(s1).not.toEqual(s2);
  53 |     }
  54 |     
  55 |     // Wait for Score Live
  56 |     await expect(page.locator('text=smoothed over last 5').or(page.locator('text=raw'))).toBeVisible({ timeout: 15000 });
  57 |     await page.screenshot({ path: '../docs/screens/live-1280.png' });
  58 |     
  59 |     // Check uncalibrated pill
  60 |     await expect(page.locator('text=Uncalibrated, score only')).toBeVisible();
  61 | 
  62 |     // Stop
  63 |     await page.locator('button:has-text("Stop")').click();
  64 | 
  65 |     // Go to history
  66 |     await page.locator('text=History').click();
  67 |     await expect(page.locator('text=Mean Score').first()).toBeVisible({ timeout: 5000 });
  68 |     await page.screenshot({ path: '../docs/screens/history-1280.png' });
  69 | 
  70 |     // Go to How it works
  71 |     await page.locator('text=How it works').click();
  72 |     await expect(page.locator('text=We convert everything to 16 kHz mono.')).toBeVisible();
  73 |     await page.screenshot({ path: '../docs/screens/how-it-works-1280.png' });
  74 | 
  75 |     // Go to About
  76 |     await page.locator('text=About').click();
  77 |     await expect(page.locator('text=Smart India Hackathon 2026')).toBeVisible();
  78 |     await page.screenshot({ path: '../docs/screens/about-1280.png' });
  79 | 
  80 |     // Check errors
  81 |     expect(errors.length).toBe(0);
  82 |   });
  83 | });
  84 | 
```