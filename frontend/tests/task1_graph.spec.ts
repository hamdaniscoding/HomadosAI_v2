import { test, expect } from '@playwright/test';
import * as path from 'path';

test.describe('Task 1 - Graph Overflow Regression Tests', () => {
  const widths = [1920, 1280, 768, 390];

  for (const width of widths) {
    test(`graph does not overflow card at width ${width}px`, async ({ page }) => {
      test.setTimeout(180000);
      await page.setViewportSize({ width, height: 900 });
      await page.goto('/');

      // Replay a short human file so we enter the live / results state
      const replayInput = page.locator('label:has-text("or replay at real speed") input[type="file"]');
      const filePath = path.resolve(process.cwd(), '../data/human/h1.wav');
      await replayInput.setInputFiles(filePath);

      // Wait for live view to appear and chart to render points
      const card = page.locator('.glass-card-responsive').first();
      await expect(card).toBeVisible({ timeout: 15000 });

      // Wait until at least one result message appears (or wait 6s)
      await page.waitForTimeout(6000);

      // Devtools-style inspection: log scrollWidth vs clientWidth
      const metrics = await page.evaluate(() => {
        const doc = document.documentElement;
        const cardEl = document.querySelector('.glass-card-responsive') as HTMLElement;
        const liveContainer = document.querySelector('.live-container') as HTMLElement;
        const ring = document.querySelector('.score-ring') as HTMLElement;
        const chartWrapper = document.querySelector('.chart-wrapper') as HTMLElement;
        const svg = document.querySelector('svg[height="240"]') as SVGElement;
        const summary = document.querySelector('.chart-summary-row') as HTMLElement;

        return {
          innerWidth: window.innerWidth,
          doc: { scrollWidth: doc.scrollWidth, clientWidth: doc.clientWidth },
          card: cardEl ? { scrollWidth: cardEl.scrollWidth, clientWidth: cardEl.clientWidth, right: cardEl.getBoundingClientRect().right } : null,
          liveContainer: liveContainer ? { scrollWidth: liveContainer.scrollWidth, clientWidth: liveContainer.clientWidth } : null,
          ring: ring ? { scrollWidth: ring.scrollWidth, clientWidth: ring.clientWidth } : null,
          chartWrapper: chartWrapper ? { scrollWidth: chartWrapper.scrollWidth, clientWidth: chartWrapper.clientWidth, right: chartWrapper.getBoundingClientRect().right } : null,
          svg: svg ? { widthAttr: svg.getAttribute('width'), right: svg.getBoundingClientRect().right } : null,
          summary: summary ? { scrollWidth: summary.scrollWidth, clientWidth: summary.clientWidth, right: summary.getBoundingClientRect().right } : null,
        };
      });

      console.log(`[Task 1 Inspection Width ${width}]:`, JSON.stringify(metrics, null, 2));

      // Assertions required by Task 1:
      // 1. chart.right <= card.right
      // 2. summaryRow.right <= card.right
      // 3. no horizontal page scroll (document.documentElement.scrollWidth <= innerWidth)
      expect(metrics.doc.scrollWidth).toBeLessThanOrEqual(metrics.innerWidth);

      if (metrics.card && metrics.chartWrapper) {
        expect(metrics.chartWrapper.right).toBeLessThanOrEqual(metrics.card.right + 1); // 1px rounding tolerance
      }

      if (metrics.card && metrics.summary) {
        expect(metrics.summary.right).toBeLessThanOrEqual(metrics.card.right + 1);
      }

      // Save screenshot
      await page.screenshot({ path: `../docs/screens/graph-${width}.png` });
    });
  }
});
