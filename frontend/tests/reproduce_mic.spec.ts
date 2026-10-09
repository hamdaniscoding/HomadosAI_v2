import { test, expect } from '@playwright/test';
import * as path from 'path';

test('reproduce mic tap behavior and log all events with stack traces', async ({ page }) => {
  test.setTimeout(60000);

  const logs: string[] = [];
  page.on('console', msg => {
    const text = msg.text();
    console.log(`[BROWSER CONSOLE ${msg.type()}]:`, text);
    logs.push(`[CONSOLE ${msg.type()}]: ${text}`);
  });
  page.on('pageerror', err => {
    console.log('[BROWSER PAGE ERROR]:', err);
    logs.push(`[PAGE ERROR]: ${err.stack || err.message}`);
  });

  await page.addInitScript(() => {
    // Instrument AudioContext
    const origAudioContext = window.AudioContext || (window as any).webkitAudioContext;
    if (origAudioContext) {
      window.AudioContext = class extends origAudioContext {
        constructor(options?: AudioContextOptions) {
          super(options);
          console.log(`[DEBUG AudioContext created] sampleRate: ${this.sampleRate}, state: ${this.state}`);
          this.onstatechange = () => {
            console.log(`[DEBUG AudioContext statechange]: ${this.state}`);
          };
        }
        async resume() {
          console.log(`[DEBUG AudioContext resume called] current state: ${this.state}`);
          return super.resume();
        }
      } as any;
    }

    // Instrument WebSocket
    const origWebSocket = window.WebSocket;
    window.WebSocket = class extends origWebSocket {
      constructor(url: string | URL, protocols?: string | string[]) {
        super(url, protocols);
        console.log(`[DEBUG WS constructor] URL: ${url}`);
        this.addEventListener('open', (ev) => {
          console.log(`[DEBUG WS open event] readyState: ${this.readyState}`);
        });
        this.addEventListener('message', (ev) => {
          console.log(`[DEBUG WS message received]:`, typeof ev.data === 'string' ? ev.data : `binary bytes: ${ev.data.byteLength || (ev.data as any).size}`);
        });
        this.addEventListener('close', (ev) => {
          console.log(`[DEBUG WS close event] code: ${ev.code}, reason: ${ev.reason}, wasClean: ${ev.wasClean}\nStack: ${new Error().stack}`);
        });
        this.addEventListener('error', (ev) => {
          console.log(`[DEBUG WS error event]`);
        });
      }
      send(data: any) {
        if (typeof data === 'string') {
          console.log(`[DEBUG WS send text]: ${data}`);
        } else {
          // binary
          // console.log(`[DEBUG WS send binary]: len ${data.byteLength}`);
        }
        super.send(data);
      }
      close(code?: number, reason?: string) {
        console.log(`[DEBUG WS close called by client] code: ${code}, reason: ${reason}\nStack: ${new Error().stack}`);
        super.close(code, reason);
      }
    } as any;

    // Instrument getUserMedia
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      const origGUM = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
      navigator.mediaDevices.getUserMedia = async (constraints) => {
        console.log(`[DEBUG getUserMedia called] constraints:`, JSON.stringify(constraints));
        try {
          const stream = await origGUM(constraints);
          console.log(`[DEBUG getUserMedia success] tracks: ${stream.getTracks().length}, active: ${stream.active}`);
          stream.getTracks().forEach(track => {
            console.log(`[DEBUG track] id: ${track.id}, kind: ${track.kind}, label: ${track.label}, enabled: ${track.enabled}, readyState: ${track.readyState}`);
            track.onended = () => {
              console.log(`[DEBUG track ended] id: ${track.id}, label: ${track.label}`);
            };
          });
          return stream;
        } catch (err: any) {
          console.log(`[DEBUG getUserMedia error]:`, err.name, err.message);
          throw err;
        }
      };
    }
  });

  await page.goto('/');

  console.log('--- Clicking Tap here to detect ---');
  const tapBtn = page.locator('button:has-text("Tap here to detect AI or fake audio")');
  await tapBtn.click();

  // Watch what happens over the next 15 seconds
  for (let i = 0; i < 15; i++) {
    await page.waitForTimeout(1000);
    const stateText = await page.evaluate(() => {
      const live = document.querySelector('.live-container');
      const hasAnalysisComplete = document.body.innerText.includes('Analysis complete');
      return {
        url: window.location.href,
        hasLive: !!live,
        hasAnalysisComplete,
        bodyText: document.body.innerText.slice(0, 300)
      };
    });
    console.log(`[Second ${i + 1}] hasLive: ${stateText.hasLive}, hasAnalysisComplete: ${stateText.hasAnalysisComplete}`);
  }
});
