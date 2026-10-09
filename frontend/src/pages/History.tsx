import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { ProbabilityChart } from '../components/ProbabilityChart';

const History = () => {
  const [history, setHistory] = useState<any[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedData, setExpandedData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = () => {
    fetch('/api/v1/history')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load');
        return res.json();
      })
      .then(data => {
        setHistory(data.history || []);
        setError(null);
      })
      .catch(e => setError(e.message));
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const expandRow = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setExpandedData(null);
      return;
    }
    try {
      const res = await fetch(`/api/v1/history/${id}`);
      if (!res.ok) throw new Error('Failed to load item');
      const data = await res.json();
      setExpandedData(data);
      setExpandedId(id);
    } catch (e) {
      console.error(e);
    }
  };

  const deleteRow = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      await fetch(`/api/v1/history/${id}`, { method: 'DELETE' });
      fetchHistory();
      if (expandedId === id) {
        setExpandedId(null);
        setExpandedData(null);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const clearAll = async () => {
    if (confirm('Are you sure you want to clear all history?')) {
      try {
        await fetch(`/api/v1/history`, { method: 'DELETE' });
        fetchHistory();
        setExpandedId(null);
        setExpandedData(null);
      } catch (e) {
        console.error(e);
      }
    }
  };

  const formatDate = (ds: string) => {
    const d = new Date(ds);
    return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) + ', ' + d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div style={{ padding: '120px 24px', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
        <h1 style={{ fontFamily: "'Instrument Serif', serif", fontSize: '48px', margin: 0 }}>History</h1>
        {history.length > 0 && (
          <button onClick={clearAll} style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #ffaaaa', background: '#fff', color: '#ff4444', cursor: 'pointer' }}>Clear all</button>
        )}
      </div>

      {error ? (
        <div style={{ textAlign: 'center', color: '#ff4444' }}>
          <p>Error loading history: {error}</p>
        </div>
      ) : history.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--color-muted)' }}>
          <p>No analyses yet.</p>
          <Link to="/" style={{ color: 'var(--color-brand)', fontWeight: 600, marginTop: '16px', display: 'inline-block' }}>Analyze audio</Link>
        </div>
      ) : (
        <>
          <div style={{ fontSize: '14px', color: '#999', marginBottom: '16px' }}>Showing last 10 analyses</div>
          <div style={{ display: 'grid', gap: '16px' }}>
            {history.map(s => (
              <div key={s.id} className="glass" style={{ borderRadius: '16px', overflow: 'hidden' }}>
                <div onClick={() => expandRow(s.id)} style={{ padding: '24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', transition: 'background 0.2s' }}>
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {s.filename}
                      {s.verdict && (
                        <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', background: s.verdict === 'ai' ? '#ffebee' : '#e8f5e9', color: s.verdict === 'ai' ? '#d32f2f' : '#2e7d32', textTransform: 'uppercase' }}>
                          {s.verdict}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '14px', color: 'var(--color-muted)' }}>
                      {formatDate(s.created_at)} | Source: {s.source} | Duration: {s.duration_s.toFixed(1)}s
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '20px', fontWeight: 700 }}>{Math.round(s.avg_prob * 100)}%</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-muted)' }}>Avg</div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '20px', fontWeight: 700 }}>{Math.round(s.peak_prob * 100)}%</div>
                      <div style={{ fontSize: '11px', color: 'var(--color-muted)' }}>Peak</div>
                    </div>
                    <button onClick={(e) => deleteRow(e, s.id)} style={{ background: 'none', border: 'none', fontSize: '20px', color: '#999', cursor: 'pointer' }}>×</button>
                  </div>
                </div>
                
                {expandedId === s.id && expandedData && (
                  <div style={{ padding: '24px', borderTop: '1px solid #eee', background: '#fcfcfc' }}>
                    <ProbabilityChart scores={expandedData.results_series} calibrated={false} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
export default History;
