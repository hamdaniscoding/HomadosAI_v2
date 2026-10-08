import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AudioStreamClient, StreamState } from '../lib/stream';
import { ServerMessage, ScoreUpdate } from '../types/protocol';

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

const Home = () => {
  const [state, setState] = useState<StreamState>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const [saveSession, setSaveSession] = useState(false);
  const [dismissBanner, setDismissBanner] = useState(false);
  
  const [scores, setScores] = useState<ScoreUpdate[]>([]);
  const [latestScore, setLatestScore] = useState<ScoreUpdate | null>(null);
  const [fileProgress, setFileProgress] = useState<{received: number, total: number} | null>(null);
  const [sourceName, setSourceName] = useState('');
  
  const clientRef = useRef<AudioStreamClient | null>(null);
  
  useEffect(() => {
    const saved = sessionStorage.getItem('dismissBanner');
    if (saved) {
      setTimeout(() => setDismissBanner(true), 0);
    }
  }, []);

  const initClient = (srcName: string) => {
    setSourceName(srcName);
    setScores([]);
    setLatestScore(null);
    setFileProgress(null);
    setErrorMsg('');
    
    if (!clientRef.current) {
      clientRef.current = new AudioStreamClient({
        onStateChange: (s) => {
          setState(s);
          if (s === 'idle' || s === 'stopped' || s === 'error') {
            clientRef.current = null;
          }
        },
        onMessage: (msg: ServerMessage) => {
          if (msg.type === 'error') {
            setErrorMsg(`${msg.code}: ${msg.message}`);
            setState('error');
            clientRef.current?.stop();
          } else if (msg.type === 'score') {
            if (state !== 'live' && msg.ai_probability !== null) {
              setState('live');
            }
            setLatestScore(msg);
            setScores(prev => [...prev.slice(-60), msg]);
          }
        },
        onError: (msg) => {
          setErrorMsg(msg);
        },
        onProgress: (r, t) => setFileProgress({ received: r, total: t })
      });
    }
  };

  const handleMic = () => {
    initClient('Microphone');
    clientRef.current?.startMicrophone(saveSession);
  };
  
  const handleTab = () => {
    initClient('Tab audio');
    clientRef.current?.startTab(saveSession);
  };

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      initClient(file.name);
      clientRef.current?.startFile(file, saveSession);
    }
  };

  const stop = () => {
    clientRef.current?.stop();
  };

  const isLive = state === 'live' || state === 'collecting' || state === 'reconnecting';

  return (
    <div style={{ position: 'relative', zIndex: 10, maxWidth: '1000px', margin: '0 auto', padding: '56px 24px 80px' }}>
      
      {!dismissBanner && (
        <div className="glass" style={{ marginBottom: '24px', padding: '12px 16px', borderRadius: '12px', fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>Research preview. The detection model is still being trained and its scores have not been validated.</span>
          <button onClick={() => { setDismissBanner(true); sessionStorage.setItem('dismissBanner', '1'); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-ink)' }}>✕</button>
        </div>
      )}

      <AnimatePresence mode="wait">
        {!isLive && state !== 'error' && (
          <motion.div key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ textAlign: 'center' }}>
            <div className="i1" style={{ position: 'relative', width: '130px', height: '130px', margin: '0 auto 26px' }}>
              <div className="r1" style={{ position: 'absolute', inset: 0, border: '1px solid #FF5A00', borderRadius: '50%' }}></div>
              <div className="r2" style={{ position: 'absolute', inset: 0, border: '1px solid #FF5A00', borderRadius: '50%' }}></div>
              <div className="r3" style={{ position: 'absolute', inset: 0, border: '1px solid #FF5A00', borderRadius: '50%' }}></div>
              <div className="orb" style={{ position: 'absolute', inset: '34px', borderRadius: '50%', background: 'radial-gradient(circle at 32% 28%,#FFD2B0 0%,#FF8A3D 30%,#FF5A00 62%,#B83600 100%)', boxShadow: '0 14px 40px rgba(255,90,0,.55), inset 0 -8px 16px rgba(120,30,0,.35), inset 0 6px 12px rgba(255,255,255,.55)' }}></div>
            </div>
            
            <div className="i2" style={{ fontSize: '12px', letterSpacing: '.24em', color: '#FF5A00', textTransform: 'uppercase', fontWeight: 700 }}>AI voice and fake audio detection</div>
            <h1 className="i2" style={{ margin: '18px 0 0', fontFamily: "'Instrument Serif', serif", fontWeight: 400, fontSize: '100px', lineHeight: 1, letterSpacing: '-.02em' }}>Is that voice <span className="gloss" style={{ display: 'inline-block', padding: '0 .08em' }}>real?</span></h1>
            <p className="i3" style={{ margin: '26px auto 0', maxWidth: '580px', fontSize: '18px', lineHeight: 1.55, color: '#5c5b57' }}>Play a call, speak into your microphone, or drop in a recording. Homados AI listens and tells you, every second, how likely the voice is to be AI-generated.</p>
            
            <div className="i4" style={{ marginTop: '38px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
              <button onClick={handleMic} className="cta" style={{ border: 'none', cursor: 'pointer', background: 'linear-gradient(135deg,#FF8A3D 0%,#FF5A00 55%,#D43F00 100%)', color: '#fff', padding: '19px 40px', borderRadius: '999px', fontWeight: 600, fontSize: '16px', display: 'inline-flex', alignItems: 'center', gap: '12px', boxShadow: '0 12px 30px rgba(255,90,0,.38), inset 0 1px 0 rgba(255,255,255,.55)' }}>
                <span className="sh"></span><span style={{ width: '10px', height: '10px', borderRadius: '50%', background: '#fff', display: 'inline-block', boxShadow: '0 0 12px #fff' }}></span>
                Tap here to detect AI or fake audio
              </button>
              <label style={{ fontSize: '14px', color: '#111', borderBottom: '1px solid #CDB9A8', paddingBottom: '2px', cursor: 'pointer' }}>
                or upload a recording instead
                <input type="file" accept="audio/*" style={{ display: 'none' }} onChange={handleFile} />
              </label>
              <div style={{ fontSize: '13px', color: '#7a7771' }}>Nothing is saved unless you choose to save it.</div>
            </div>

            <div className="i5" style={{ position: 'relative', maxWidth: '920px', margin: '84px auto 0', padding: '0 24px' }}>
              <div style={{ textAlign: 'center', fontSize: '12px', letterSpacing: '.22em', color: '#7a7771', textTransform: 'uppercase', fontWeight: 600 }}>Pick what you want to check</div>
              <div style={{ marginTop: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', textAlign: 'left' }}>
                <button onClick={handleMic} className="card glass" style={{ border: '1px solid rgba(255,255,255,0.75)', cursor: 'pointer', borderRadius: '22px', padding: '28px', color: '#111', display: 'block', textAlign: 'left' }}>
                  <div style={{ fontSize: '12px', letterSpacing: '.12em', color: '#FF5A00', fontWeight: 700 }}>01</div>
                  <div style={{ marginTop: '12px', fontFamily: "'Instrument Serif', serif", fontSize: '30px' }}>Microphone</div>
                  <div style={{ marginTop: '8px', fontSize: '15px', lineHeight: 1.5, color: '#5c5b57' }}>Speak, or hold your phone near a speaker. See the result live.</div>
                </button>
                <button onClick={handleTab} className="card glass" style={{ border: '1px solid rgba(255,255,255,0.75)', cursor: 'pointer', borderRadius: '22px', padding: '28px', color: '#111', display: 'block', textAlign: 'left' }}>
                  <div style={{ fontSize: '12px', letterSpacing: '.12em', color: '#FF5A00', fontWeight: 700 }}>02</div>
                  <div style={{ marginTop: '12px', fontFamily: "'Instrument Serif', serif", fontSize: '30px' }}>Live call</div>
                  <div style={{ marginTop: '8px', fontSize: '15px', lineHeight: 1.5, color: '#5c5b57' }}>Capture audio from a browser tab or your screen during a call.</div>
                </button>
                <label className="card glass" style={{ cursor: 'pointer', borderRadius: '22px', padding: '28px', color: '#111', display: 'block', textAlign: 'left' }}>
                  <input type="file" accept="audio/*" style={{ display: 'none' }} onChange={handleFile} />
                  <div style={{ fontSize: '12px', letterSpacing: '.12em', color: '#FF5A00', fontWeight: 700 }}>03</div>
                  <div style={{ marginTop: '12px', fontFamily: "'Instrument Serif', serif", fontSize: '30px' }}>Recording</div>
                  <div style={{ marginTop: '8px', fontSize: '15px', lineHeight: 1.5, color: '#5c5b57' }}>Upload an audio file. We replay it at normal speed and score it.</div>
                </label>
              </div>
            </div>

            <div style={{ position: 'relative', maxWidth: '920px', margin: '72px auto 0', padding: '0 24px', textAlign: 'left' }}>
              <div style={{ position: 'relative', overflow: 'hidden', background: 'linear-gradient(145deg,#1b1714,#0d0b0a)', color: '#F3EEE8', borderRadius: '28px', padding: '40px 44px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: '28px', boxShadow: '0 30px 70px rgba(255,90,0,.18),inset 0 1px 0 rgba(255,255,255,.12)' }}>
                <div style={{ position: 'absolute', top: '-80px', right: '-60px', width: '300px', height: '300px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,90,0,.45),rgba(255,90,0,0) 70%)' }}></div>
                <div style={{ position: 'relative' }}><div style={{ fontSize: '12px', letterSpacing: '.2em', color: '#FF7A2B', textTransform: 'uppercase', fontWeight: 700 }}>How to read the result</div><div style={{ marginTop: '12px', fontFamily: "'Instrument Serif', serif", fontSize: '34px', lineHeight: 1.1 }}>One number, in plain words.</div></div>
                <div style={{ position: 'relative', fontSize: '15px', lineHeight: 1.6, color: '#BDB6AD' }}><b style={{ color: '#fff', fontWeight: 600 }}>Score 0 to 100.</b> Higher means the voice is more likely to be AI-generated. Each speaker on a call gets their own score.</div>
                <div style={{ position: 'relative', fontSize: '15px', lineHeight: 1.6, color: '#BDB6AD' }}><b style={{ color: '#fff', fontWeight: 600 }}>Honest by design.</b> It needs about five seconds of speech first. If audio is too quiet or noisy, it says so instead of guessing.</div>
              </div>
            </div>

            <div style={{ position: 'relative', maxWidth: '920px', margin: '40px auto 0', padding: '0 24px 56px', display: 'flex', flexWrap: 'wrap', gap: '12px 28px', justifyContent: 'center', fontSize: '13px', color: '#7a7771' }}>
              <span>Updated every second</span><span>Works with phone-quality audio</span><span>Open results, no black box</span>
            </div>
            
            <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'center' }}>
              <label style={{ fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input type="checkbox" checked={saveSession} onChange={e => setSaveSession(e.target.checked)} />
                Save this session to History
              </label>
            </div>
          </motion.div>
        )}

        {isLive && (
          <motion.div key="live" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="glass" style={{ padding: '32px', borderRadius: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <div style={{ fontSize: '14px', fontWeight: 600 }}>{sourceName}</div>
              <button onClick={stop} style={{ padding: '8px 16px', borderRadius: '8px', border: '1px solid #ccc', background: '#fff', cursor: 'pointer' }}>Stop</button>
            </div>
            
            {state === 'reconnecting' && <div style={{ color: '#FF5A00', fontWeight: 600, marginBottom: '16px' }}>Reconnecting…</div>}
            
            <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
              <div style={{ width: '160px', height: '160px', borderRadius: '50%', border: '4px solid #eee', position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {/* SVG Ring for score */}
                {latestScore?.ai_probability !== null && latestScore?.ai_probability !== undefined && (
                  <svg style={{ position: 'absolute', inset: -4, width: '168px', height: '168px', transform: 'rotate(-90deg)' }}>
                    <circle cx="84" cy="84" r="80" fill="none" stroke="#FF5A00" strokeWidth="4" strokeDasharray="502" strokeDashoffset={502 - (502 * ((latestScore.smoothed_probability ?? latestScore.ai_probability) * 100) / 100)} style={{ transition: 'stroke-dashoffset 0.5s ease-out' }} />
                  </svg>
                )}
                
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '48px', fontWeight: 700, fontFamily: "'Instrument Serif', serif" }}>
                    {latestScore?.ai_probability === null || latestScore?.ai_probability === undefined ? '—' : Math.round((latestScore.smoothed_probability ?? latestScore.ai_probability) * 100)}
                  </div>
                  {latestScore?.ai_probability !== null && latestScore?.ai_probability !== undefined && (
                    <div style={{ fontSize: '10px', color: '#7a7771' }}>{latestScore.smoothed_probability !== null ? 'smoothed over last 5' : 'raw'}</div>
                  )}
                </div>
              </div>
              
              <div style={{ flex: 1 }}>
                <div style={{ height: '120px', borderBottom: '1px solid #eee', position: 'relative' }}>
                  {/* Real-time chart */}
                  {scores.length === 0 ? (
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#7a7771', fontSize: '14px' }}>Waiting for the first score</div>
                  ) : (
                    <svg style={{ width: '100%', height: '100%' }} viewBox={`0 0 ${scores.length > 0 ? Math.max(60, scores[scores.length-1].t) : 60} 100`} preserveAspectRatio="none">
                      {/* SVG path for smoothed */}
                      {(() => {
                        const pts = scores.filter(s => s.smoothed_probability !== null).map(s => `${s.t},${100 - (s.smoothed_probability! * 100)}`).join(' L');
                        return pts ? <path d={`M${pts}`} fill="none" stroke="#FF5A00" strokeWidth="2" /> : null;
                      })()}
                      {/* SVG dots for raw */}
                      {scores.filter(s => s.ai_probability !== null).map((s, i) => (
                        <circle key={i} cx={s.t} cy={100 - (s.ai_probability! * 100)} r="1" fill="#FFB27A" />
                      ))}
                    </svg>
                  )}
                </div>
              </div>
            </div>
            
            {/* Status Line */}
            <div aria-live="polite" style={{ marginTop: '24px', fontSize: '14px', color: '#5c5b57' }}>
              {latestScore ? (
                <>
                  {latestScore.reason ? (
                    <span style={{ color: '#D43F00' }}>{formatReason(latestScore.reason)}</span>
                  ) : (
                    <span>Collecting audio, {latestScore.received_seconds.toFixed(1)} of {latestScore.needed_seconds} s</span>
                  )}
                </>
              ) : (
                <span>Connecting...</span>
              )}
            </div>

            {/* Verdict Uncalibrated */}
            {latestScore?.ai_probability !== null && !latestScore?.reason && (
               <div style={{ marginTop: '12px', display: 'inline-block', background: '#eee', padding: '4px 8px', borderRadius: '4px', fontSize: '12px' }}>
                 Uncalibrated, score only
               </div>
            )}
            
            {/* Speakers */}
            {latestScore?.speakers && latestScore.speakers.length > 0 && (
              <div style={{ marginTop: '24px', display: 'flex', gap: '16px' }}>
                {latestScore.speakers.map((sp, i) => (
                  <div key={sp.id} style={{ padding: '12px', border: '1px solid #eee', borderRadius: '12px', flex: 1, background: latestScore.active_speaker === sp.id ? '#fff8f0' : 'transparent' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#7a7771' }}>Speaker {i + 1} {latestScore.active_speaker === sp.id && '(Active)'}</div>
                    <div style={{ fontSize: '24px', fontWeight: 700 }}>{sp.ai_probability === null ? '—' : Math.round((sp.smoothed_probability ?? sp.ai_probability) * 100)}</div>
                  </div>
                ))}
              </div>
            )}
            
            {/* Footer */}
            {latestScore && (
              <div style={{ marginTop: '24px', display: 'flex', gap: '16px', fontSize: '12px', fontFamily: 'monospace', color: '#7a7771', borderTop: '1px solid #eee', paddingTop: '16px' }}>
                <span>{latestScore.detector_name}</span>
                <span>Lat: {latestScore.latency_ms}ms</span>
                <span>Speech: {Math.round(latestScore.speech_ratio * 100)}%</span>
                <span>ID: {latestScore.session_id.substring(0, 8)}</span>
              </div>
            )}
            
            {fileProgress && (
              <div style={{ marginTop: '16px', height: '4px', background: '#eee', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${(fileProgress.received / fileProgress.total) * 100}%`, background: '#FF5A00' }}></div>
              </div>
            )}
          </motion.div>
        )}

        {state === 'error' && (
          <motion.div key="error" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="glass" style={{ padding: '32px', borderRadius: '24px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 600, color: '#D43F00', marginBottom: '16px' }}>Error</div>
            <div style={{ fontSize: '16px', color: '#5c5b57', marginBottom: '24px' }}>{errorMsg}</div>
            <button onClick={() => setState('idle')} style={{ padding: '12px 24px', borderRadius: '999px', border: 'none', background: '#FF5A00', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>Try Again</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Home;
