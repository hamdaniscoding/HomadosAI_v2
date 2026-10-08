import { useState, useEffect } from 'react';

const HowItWorks = () => {
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    fetch('/api/v1/health').then(r => r.json()).then(setHealth).catch(() => {});
  }, []);

  return (
    <div style={{ padding: '80px 24px', maxWidth: '800px', margin: '0 auto', position: 'relative', zIndex: 10 }}>
      <h1 style={{ fontFamily: "'Instrument Serif', serif", fontSize: '64px', marginBottom: '60px', textAlign: 'center' }}>How it works</h1>
      
      <div style={{ display: 'grid', gap: '80px' }}>
        <section className="glass" style={{ padding: '40px', borderRadius: '24px', position: 'sticky', top: '100px' }}>
          <div style={{ color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '0.1em', marginBottom: '16px' }}>01 LISTEN</div>
          <h2 style={{ fontSize: '32px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>We convert everything to 16 kHz mono.</h2>
          <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>The raw audio is captured in the browser, instantly downmixed, resampled, and streamed securely.</p>
          <div style={{ marginTop: '24px', padding: '24px', background: 'rgba(0,0,0,0.03)', borderRadius: '12px', textAlign: 'center', fontSize: '14px', color: 'var(--color-muted)' }}>[Diagram: Audio Waveform]</div>
        </section>

        <section className="glass" style={{ padding: '40px', borderRadius: '24px', position: 'sticky', top: '120px' }}>
          <div style={{ color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '0.1em', marginBottom: '16px' }}>02 WINDOW</div>
          <h2 style={{ fontSize: '32px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>We analyze the last 5 seconds.</h2>
          <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>We don't look at single words in isolation. We look at context.</p>
          <div style={{ marginTop: '24px', padding: '24px', background: 'rgba(0,0,0,0.03)', borderRadius: '12px', textAlign: 'center', fontSize: '14px', color: 'var(--color-muted)' }}>[Diagram: Sliding Bracket]</div>
        </section>

        <section className="glass" style={{ padding: '40px', borderRadius: '24px', position: 'sticky', top: '140px' }}>
          <div style={{ color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '0.1em', marginBottom: '16px' }}>03 SEPARATE</div>
          <h2 style={{ fontSize: '32px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>We split the speakers.</h2>
          <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>If multiple people are talking, we try to track them independently.</p>
          <div style={{ marginTop: '24px', padding: '24px', background: 'rgba(0,0,0,0.03)', borderRadius: '12px', textAlign: 'center', fontSize: '14px', color: 'var(--color-muted)' }}>[Diagram: Speaker separation]</div>
        </section>

        <section className="glass" style={{ padding: '40px', borderRadius: '24px', position: 'sticky', top: '160px' }}>
          <div style={{ color: 'var(--color-brand)', fontWeight: 700, letterSpacing: '0.1em', marginBottom: '16px' }}>04 SCORE</div>
          <h2 style={{ fontSize: '32px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>One number a second.</h2>
          <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>The neural network outputs a probability score from 0 to 100.</p>
        </section>
      </div>

      <div style={{ marginTop: '120px', padding: '40px', background: 'linear-gradient(145deg,#1b1714,#0d0b0a)', color: '#F3EEE8', borderRadius: '24px' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '24px', fontFamily: "'Instrument Serif', serif" }}>Live Detector Facts</h2>
        {health ? (
          <ul style={{ lineHeight: 1.8, color: '#BDB6AD', marginBottom: '32px' }}>
            <li>Detector: <span style={{ color: '#fff' }}>{health.detector}</span></li>
            <li>Device: <span style={{ color: '#fff' }}>{health.device}</span></li>
            <li>Window: <span style={{ color: '#fff' }}>{health.window_seconds}s</span></li>
            <li>Hop: <span style={{ color: '#fff' }}>{health.hop_seconds}s</span></li>
          </ul>
        ) : (
          <div style={{ color: '#BDB6AD', marginBottom: '32px' }}>Loading...</div>
        )}
        
        <h2 style={{ fontSize: '24px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif", color: '#FF7A2B' }}>Limitations</h2>
        <ul style={{ lineHeight: 1.8, color: '#BDB6AD' }}>
          <li>Model is not yet validated.</li>
          <li>Phone-quality audio is harder to analyze.</li>
          <li>Speaker separation is experimental (limited to 2 speakers).</li>
          <li>A score is not proof; results can be wrong.</li>
        </ul>
      </div>
    </div>
  );
};
export default HowItWorks;
