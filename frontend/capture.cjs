const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Fake results screen by mocking the job endpoint
  await page.route('**/api/v1/jobs/*', async route => {
    const json = {
      status: 'done',
      progress: { done_windows: 10, total_windows: 10 },
      results: Array.from({length: 10}).map((_, i) => ({
        seq: i + 1,
        t: i * 5,
        window_seconds: 5,
        ai_probability: 0.1 + i * 0.05,
        smoothed_probability: 0.15 + i * 0.05,
        verdict: 'human',
        latency_ms: 100,
        detector: 'default',
        speech_ratio: 1.0,
        reason: null,
        active_speaker: null,
        speakers: []
      })),
      error: null
    };
    await route.fulfill({ json });
  });

  await page.route('**/api/v1/analyze', async route => {
    await route.fulfill({ json: { job_id: 'mock-123', duration_seconds: 50, total_windows: 10 } });
  });

  await page.goto('http://127.0.0.1:8000/');
  const fileInput = page.locator('input[type="file"]').first();
  await fileInput.setInputFiles('../data/human/h1.wav');
  
  await page.waitForSelector('text=Analysis complete');
  
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: '../docs/screens/results-1280.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '../docs/screens/results-390.png' });

  // Error screen
  await page.unroute('**/api/v1/jobs/*');
  await page.route('**/api/v1/jobs/*', async route => {
    await route.fulfill({ json: { status: 'error', error: 'Simulated backend crash', results: [] } });
  });
  await page.goto('http://127.0.0.1:8000/');
  await page.locator('input[type="file"]').first().setInputFiles('../data/human/h1.wav');
  await page.waitForSelector('text=Simulated backend crash');
  
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.screenshot({ path: '../docs/screens/error-1280.png' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: '../docs/screens/error-390.png' });

  await browser.close();
})();
