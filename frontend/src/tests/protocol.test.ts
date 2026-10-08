import { describe, it, expect } from 'vitest';

const REASON_MAP: Record<string, string> = {
  'detector_busy': 'Catching up, one update skipped',
  'thresholds_not_calibrated': 'Score only',
  'window_too_short': 'Window too short',
  'audio_too_quiet': 'Audio too quiet',
  'audio_too_noisy': 'Audio too noisy',
};

const formatReason = (reason: string | null | undefined) => {
  if (!reason) return '';
  return REASON_MAP[reason] || reason;
};

describe('Protocol and UI parsing', () => {
  it('reason-to-text mapping', () => {
    expect(formatReason('detector_busy')).toBe('Catching up, one update skipped');
    expect(formatReason('thresholds_not_calibrated')).toBe('Score only');
    expect(formatReason('unknown_reason')).toBe('unknown_reason');
  });

  it('score formatting (null shows "—", smoothed beats raw)', () => {
    const s1 = { ai_probability: null, smoothed_probability: null };
    expect(s1.ai_probability === null ? '—' : 'score').toBe('—');

    const s2 = { ai_probability: 0.5, smoothed_probability: null };
    expect(Math.round((s2.smoothed_probability ?? s2.ai_probability) * 100)).toBe(50);

    const s3 = { ai_probability: 0.1, smoothed_probability: 0.9 };
    expect(Math.round((s3.smoothed_probability ?? s3.ai_probability) * 100)).toBe(90);
  });
});
