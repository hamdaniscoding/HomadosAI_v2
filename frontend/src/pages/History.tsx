import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';

const History = () => {
  const [sessions, setSessions] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/v1/sessions')
      .then(res => res.json())
      .then(data => setSessions(data.sessions || []))
      .catch(e => console.error(e));
  }, []);

  return (
    <div style={{ padding: '120px 24px', maxWidth: '800px', margin: '0 auto' }}>
      <h1 style={{ fontFamily: "'Instrument Serif', serif", fontSize: '48px', marginBottom: '40px', textAlign: 'center' }}>History</h1>
      
      {sessions.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
          <p>No saved sessions yet.</p>
          <Link to="/" style={{ color: 'var(--color-brand)', fontWeight: 600, marginTop: '16px', display: 'inline-block' }}>Analyze audio</Link>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px' }}>
          {sessions.map(s => (
            <div key={s.id} className="glass" style={{ padding: '24px', borderRadius: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: '8px' }}>{new Date(s.start_time).toLocaleString()}</div>
                <div style={{ fontSize: '14px', color: 'var(--color-muted)' }}>
                  Duration: {s.duration_seconds}s | Source: {s.source} | Speakers: {s.speaker_count}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '24px', fontWeight: 700 }}>{Math.round(s.mean_score * 100)}</div>
                <div style={{ fontSize: '12px', color: 'var(--color-muted)' }}>Mean Score</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
export default History;
