import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AudioStreamClient } from '../lib/stream';
import { ServerMessage } from '../types/protocol';
import { useAnalysis } from '../store/AnalysisContext';
import { ProbabilityChart } from '../components/ProbabilityChart';

const REASON_MAP: Record<string, string> = {
  detector_busy: 'Catching up, one update skipped',
  thresholds_not_calibrated: 'Score only',
  window_too_short: 'Window too short',
  audio_too_quiet: 'Audio too quiet',
  audio_too_noisy: 'Audio too noisy',
  not_enough_speech: 'No speech detected in window',
};

const formatReason = (reason: string | null | undefined) => {
  if (!reason) return '';
  return REASON_MAP[reason] || reason;
};

const Home = () => {
  const {
    state,
    sourceName,
    sessionId,
    scores,
    latestScore,
    latestStatus,
    errorMsg,
    rms,
    deviceName,
    setState,
    setSourceName,
    setSessionId,
    setScores,
    setLatestScore,
    setLatestStatus,
    setErrorMsg,
    setRms,
    setDeviceName,
    reset,
  } = useAnalysis();

  const [dismissBanner, setDismissBanner] = useState(false);
  const [scrubTime, setScrubTime] = useState<number | undefined>(undefined);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [silenceWarning, setSilenceWarning] = useState(false);
  const [savedToHistory, setSavedToHistory] = useState(false);

  const clientRef = useRef<AudioStreamClient | null>(null);
  const lastSoundTimeRef = useRef<number>(Date.now());
  const startTimeRef = useRef<number>(Date.now());

  useEffect(() => {
    const saved = sessionStorage.getItem('dismissBanner');
    if (saved) {
      setTimeout(() => setDismissBanner(true), 0);
    }
  }, []);

  const isLive =
    state === 'live' ||
    state === 'collecting' ||
    state === 'reconnecting' ||
    state === 'analyzing';
  const isFinished = state === 'finished';

  // Live timer & 3-second silence detection
  useEffect(() => {
    let timer: any = null;
    if (isLive) {
      startTimeRef.current = Date.now();
      lastSoundTimeRef.current = Date.now();
      setSilenceWarning(false);
      setElapsedSeconds(0);
      setSavedToHistory(false);

      timer = setInterval(() => {
        const now = Date.now();
        const sec = Math.floor((now - startTimeRef.current) / 100) / 10;
        setElapsedSeconds(sec);

        if (now - lastSoundTimeRef.current >= 3000 && sec >= 3.0) {
          setSilenceWarning(true);
        } else {
          setSilenceWarning(false);
        }
      }, 100);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isLive]);

  // Keep silence timer updated when RMS > 0.005
  useEffect(() => {
    if (rms > 0.005) {
      lastSoundTimeRef.current = Date.now();
      setSilenceWarning(false);
    }
  }, [rms]);

  const initClient = (srcName: string) => {
    reset();
    setSourceName(srcName);
    setSavedToHistory(false);

    if (!clientRef.current) {
      clientRef.current = new AudioStreamClient({
        onStateChange: (s) => {
          setState(s);
          if (s === 'idle' || s === 'finished' || s === 'failed') {
            clientRef.current = null;
          }
        },
        onMessage: (msg: ServerMessage) => {
          if (msg.type === 'error') {
            setErrorMsg(`${msg.code}: ${msg.message}`);
            setState('failed');
            clientRef.current?.stop(false);
          } else if (msg.type === 'ready') {
            setSessionId(msg.session_id);
          } else if (msg.type === 'status') {
            setLatestStatus(msg);
          } else if (msg.type === 'result') {
            if (state !== 'live' && msg.ai_probability !== null) {
              setState('live');
            }
            setLatestScore(msg);
            setScores((prev) => [...prev, msg]);
          }
        },
        onError: (msg) => {
          setErrorMsg(msg);
          setState('failed');
        },
        onRms: (val) => setRms(val),
        onDeviceName: (name) => setDeviceName(name),
      });
    }
  };

  const handleMic = () => {
    initClient('Microphone');
    clientRef.current?.startMicrophone(true);
  };

  const handleFileFast = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      initClient(file.name);
      clientRef.current?.startFileUpload(file, true);
    }
    e.target.value = '';
  };

  const handleFileSimulated = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      initClient(file.name + ' (Replay)');
      clientRef.current?.startFileSimulated(file, true);
    }
    e.target.value = '';
  };

  const stop = () => {
    clientRef.current?.stop(true);
  };

  // Compute Results summary
  let windowsAnalyzed = 0;
  let windowsSkipped = 0;
  let totalProb = 0;
  let peakProb = 0;
  let timeAbove50 = 0;

  scores.forEach((s) => {
    if (s.ai_probability !== null && s.ai_probability !== undefined) {
      windowsAnalyzed++;
      const val = s.smoothed_probability ?? s.ai_probability;
      totalProb += val;
      if (val > peakProb) peakProb = val;
      if (val > 0.5) timeAbove50++;
    } else {
      windowsSkipped++;
    }
  });

  const avgProb = windowsAnalyzed > 0 ? totalProb / windowsAnalyzed : 0;
  const totalAudioDuration =
    latestStatus?.received_seconds ??
    (scores.length > 0 ? scores[scores.length - 1].t : elapsedSeconds);

  // Honest empty state threshold: at least 1 scored window and >= 5.0 s of audio
  const hasEnoughAudio = windowsAnalyzed > 0 && totalAudioDuration >= 5.0;

  const exportCSV = () => {
    const header = 'time,raw_prob,smoothed_prob,reason\n';
    const rows = scores
      .map(
        (s) =>
          `${s.t},${s.ai_probability ?? ''},${s.smoothed_probability ?? ''},${s.reason || ''}`
      )
      .join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `homados_analysis_${sessionId || 'export'}.csv`;
    a.click();
  };

  const handleSaveToHistory = async () => {
    if (!hasEnoughAudio || savedToHistory) return;
    try {
      const res = await fetch('/api/v1/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: sessionId || `live_${Date.now()}`,
          created_at: new Date().toISOString(),
          source: 'live',
          filename: sourceName,
          duration_s: totalAudioDuration,
          detector: latestScore?.detector || 'Gustking/wav2vec2-large-xlsr',
          avg_prob: avgProb,
          peak_prob: peakProb,
          peak_t: latestScore?.t || 0,
          windows_analysed: windowsAnalyzed,
          windows_skipped: windowsSkipped,
          verdict: latestScore?.verdict,
          reason: latestScore?.reason,
          results_series: scores,
        }),
      });
      if (res.ok) {
        setSavedToHistory(true);
      }
    } catch (e) {
      console.error('Failed to save to history', e);
    }
  };

  return (
    <div
      style={{
        position: 'relative',
        zIndex: 10,
        maxWidth: '1000px',
        margin: '0 auto',
        padding: '56px 24px 80px',
      }}
    >
      {/* Research Preview Banner */}
      {!dismissBanner && (
        <div
          style={{
            background: 'rgba(255, 90, 0, 0.08)',
            border: '1px solid rgba(255, 90, 0, 0.25)',
            borderRadius: '12px',
            padding: '12px 18px',
            marginBottom: '28px',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '13px',
            color: '#B83600',
          }}
        >
          <span>
            <strong>Research Preview:</strong> Homados AI analyzes audio locally using your hardware. Audio is processed on your machine and History stores only the last 10 analyses.
          </span>
          <button
            onClick={() => {
              setDismissBanner(true);
              sessionStorage.setItem('dismissBanner', 'true');
            }}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: '#B83600',
              fontWeight: 700,
              fontSize: '16px',
            }}
          >
            ✕
          </button>
        </div>
      )}

      <AnimatePresence mode="wait">
        {!isLive && !isFinished && state !== 'failed' && (
          <motion.div
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ textAlign: 'center' }}
          >
            <div
              className="i1"
              style={{
                position: 'relative',
                width: '130px',
                height: '130px',
                margin: '0 auto 26px',
              }}
            >
              <div
                className="r1"
                style={{
                  position: 'absolute',
                  inset: 0,
                  border: '1px solid #FF5A00',
                  borderRadius: '50%',
                }}
              />
              <div
                className="r2"
                style={{
                  position: 'absolute',
                  inset: 0,
                  border: '1px solid #FF5A00',
                  borderRadius: '50%',
                }}
              />
              <div
                className="r3"
                style={{
                  position: 'absolute',
                  inset: 0,
                  border: '1px solid #FF5A00',
                  borderRadius: '50%',
                }}
              />
              <div
                className="orb"
                style={{
                  position: 'absolute',
                  inset: '34px',
                  borderRadius: '50%',
                  background:
                    'radial-gradient(circle at 32% 28%,#FFD2B0 0%,#FF8A3D 30%,#FF5A00 62%,#B83600 100%)',
                  boxShadow:
                    '0 14px 40px rgba(255,90,0,.55), inset 0 -8px 16px rgba(120,30,0,.35), inset 0 6px 12px rgba(255,255,255,.55)',
                }}
              />
            </div>

            <div
              className="i2"
              style={{
                fontSize: '12px',
                letterSpacing: '.24em',
                color: '#FF5A00',
                textTransform: 'uppercase',
                fontWeight: 700,
              }}
            >
              AI voice and fake audio detection
            </div>
            <h1
              className="i2"
              style={{
                margin: '18px 0 0',
                fontFamily: "'Instrument Serif', serif",
                fontWeight: 400,
                fontSize: '100px',
                lineHeight: 1,
                letterSpacing: '-.02em',
              }}
            >
              Is that voice{' '}
              <span
                className="gloss"
                style={{ display: 'inline-block', padding: '0 .08em' }}
              >
                real?
              </span>
            </h1>

            <div
              className="i4"
              style={{
                marginTop: '38px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '14px',
              }}
            >
              <button
                onClick={handleMic}
                className="cta"
                style={{
                  border: 'none',
                  cursor: 'pointer',
                  background:
                    'linear-gradient(135deg,#FF8A3D 0%,#FF5A00 55%,#D43F00 100%)',
                  color: '#fff',
                  padding: '19px 40px',
                  borderRadius: '999px',
                  fontWeight: 600,
                  fontSize: '16px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '12px',
                  boxShadow:
                    '0 12px 30px rgba(255,90,0,.38), inset 0 1px 0 rgba(255,255,255,.55)',
                }}
              >
                Tap here to detect AI or fake audio
              </button>
              <label
                style={{
                  fontSize: '14px',
                  color: '#111',
                  borderBottom: '1px solid #CDB9A8',
                  paddingBottom: '2px',
                  cursor: 'pointer',
                }}
              >
                or fast-upload a recording instead
                <input
                  type="file"
                  accept="audio/*"
                  style={{ display: 'none' }}
                  onChange={handleFileFast}
                />
              </label>
              <label
                style={{
                  fontSize: '14px',
                  color: '#111',
                  borderBottom: '1px solid #CDB9A8',
                  paddingBottom: '2px',
                  cursor: 'pointer',
                }}
              >
                or replay at real speed
                <input
                  type="file"
                  accept="audio/*"
                  style={{ display: 'none' }}
                  onChange={handleFileSimulated}
                />
              </label>
            </div>
          </motion.div>
        )}

        {isLive && (
          <motion.div
            key="live"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="glass glass-card-responsive"
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '24px',
              }}
            >
              <div style={{ fontSize: '14px', fontWeight: 600 }}>
                {state === 'collecting' ? 'Listening' : 'Live'}: {sourceName}
              </div>
              <button
                onClick={stop}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ccc',
                  background: '#fff',
                  cursor: 'pointer',
                  fontWeight: 600,
                }}
              >
                Stop & View Results
              </button>
            </div>

            <div className="live-container">
              <div className="score-ring">
                {latestScore?.ai_probability !== null &&
                  latestScore?.ai_probability !== undefined && (
                    <svg
                      viewBox="0 0 100 100"
                      style={{
                        position: 'absolute',
                        inset: 0,
                        width: '100%',
                        height: '100%',
                        transform: 'rotate(-90deg)',
                      }}
                    >
                      <circle
                        cx="50"
                        cy="50"
                        r="44"
                        fill="none"
                        stroke="#FF5A00"
                        strokeWidth="6"
                        strokeDasharray="276.46"
                        strokeDashoffset={
                          276.46 -
                          (276.46 *
                            ((latestScore.smoothed_probability ??
                              latestScore.ai_probability) *
                              100)) /
                            100
                        }
                        style={{ transition: 'stroke-dashoffset 0.5s ease-out' }}
                      />
                    </svg>
                  )}
                <div style={{ textAlign: 'center' }}>
                  <div className="score-val">
                    {latestScore?.ai_probability === null ||
                    latestScore?.ai_probability === undefined
                      ? '—'
                      : Math.round(
                          (latestScore.smoothed_probability ??
                            latestScore.ai_probability) * 100
                        )}
                  </div>
                </div>
              </div>

              <div className="chart-wrapper">
                <ProbabilityChart scores={scores} mode="live" />
              </div>
            </div>

            {/* Live Progress / Timer & Audio Level Meter */}
            <div
              aria-live="polite"
              style={{
                marginTop: '24px',
                fontSize: '14px',
                color: '#5c5b57',
                display: 'flex',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: '16px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: '#FF5A00',
                    boxShadow: '0 0 8px #FF5A00',
                  }}
                />
                <span style={{ fontWeight: 600, color: '#222' }}>
                  {scores.length > 0 ? 'Live Scoring' : 'Listening'}
                </span>
              </div>

              <span>
                {latestStatus && latestStatus.received_seconds < 5.0 ? (
                  `Collecting ${latestStatus.received_seconds.toFixed(1)} / 5.0 s`
                ) : latestScore?.reason ? (
                  <span style={{ color: '#D43F00' }}>
                    {formatReason(latestScore.reason)}
                  </span>
                ) : latestStatus ? (
                  `Active (${latestStatus.received_seconds.toFixed(1)} s analyzed)`
                ) : (
                  `Collecting ${elapsedSeconds.toFixed(1)} / 5.0 s`
                )}
              </span>

              {/* Real microphone signal RMS level meter */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span style={{ fontSize: '11px', color: '#888' }}>Mic Level:</span>
                <div
                  className="mic-level-meter"
                  style={{
                    width: '100px',
                    height: '8px',
                    background: '#e8e6e1',
                    borderRadius: '4px',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    className="mic-level-bar"
                    style={{
                      width: `${Math.min(100, Math.round(rms * 350))}%`,
                      height: '100%',
                      background: rms > 0.8 ? '#D43F00' : '#FF5A00',
                      transition: 'width 0.08s ease-out',
                    }}
                  />
                </div>
              </div>
            </div>

            {/* 3s Silence detection alert */}
            {silenceWarning && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '10px 14px',
                  background: '#fff9e6',
                  border: '1px solid #ffd166',
                  borderRadius: '8px',
                  fontSize: '13px',
                  color: '#8a6500',
                }}
              >
                <strong>No sound detected from this microphone</strong> (
                {deviceName || 'Default Input'}).
                <span
                  style={{
                    display: 'block',
                    fontSize: '12px',
                    marginTop: '4px',
                    color: '#6d5000',
                  }}
                >
                  Hint: Please verify that your microphone is unmuted and the correct input device is selected in system settings.
                </span>
              </div>
            )}
          </motion.div>
        )}

        {isFinished && (
          <motion.div
            key="results"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass glass-card-responsive"
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '24px',
              }}
            >
              <div
                style={{
                  fontSize: '24px',
                  fontWeight: 600,
                  fontFamily: "'Instrument Serif', serif",
                }}
              >
                {hasEnoughAudio
                  ? `Analysis complete: ${sourceName}`
                  : `Not enough audio: ${sourceName}`}
              </div>
              <button
                onClick={() => reset()}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ccc',
                  background: '#fff',
                  cursor: 'pointer',
                }}
              >
                Analyze another
              </button>
            </div>

            {/* Honest Empty State Banner if < 5 s of audio or 0 windows */}
            {!hasEnoughAudio && (
              <div
                style={{
                  padding: '14px 18px',
                  background: '#fef3e2',
                  border: '1px solid #fed7aa',
                  borderRadius: '12px',
                  color: '#9a3412',
                  fontSize: '14px',
                  marginBottom: '24px',
                }}
              >
                <strong>Not enough audio</strong> — need at least 5 s of speech to score.
              </div>
            )}

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                gap: '16px',
                marginBottom: '32px',
              }}
            >
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Windows Analyzed
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio ? windowsAnalyzed : '—'}
                </div>
              </div>
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Windows Skipped
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio ? windowsSkipped : '—'}
                </div>
              </div>
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Average Probability
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio ? `${Math.round(avgProb * 100)}%` : '—'}
                </div>
              </div>
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Peak Probability
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio ? `${Math.round(peakProb * 100)}%` : '—'}
                </div>
              </div>
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Time &gt; 50%
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio ? `${timeAbove50}s` : '—'}
                </div>
              </div>
              <div
                style={{
                  padding: '16px',
                  background: '#fff',
                  borderRadius: '12px',
                  border: '1px solid #eee',
                }}
              >
                <div style={{ fontSize: '12px', color: '#7a7771' }}>
                  Speech Ratio (Final)
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600 }}>
                  {hasEnoughAudio && latestScore
                    ? `${Math.round(latestScore.speech_ratio * 100)}%`
                    : '—'}
                </div>
              </div>
            </div>

            <div
              style={{
                marginBottom: '16px',
                width: '100%',
                minWidth: 0,
                maxWidth: '100%',
                overflow: 'hidden',
              }}
            >
              <ProbabilityChart
                scores={scores}
                currentTime={scrubTime}
                mode="results"
              />
            </div>

            {scores.length > 0 && hasEnoughAudio && (
              <input
                type="range"
                min={scores[0].t}
                max={scores[scores.length - 1].t}
                step="1"
                onChange={(e) => setScrubTime(Number(e.target.value))}
                style={{ width: '100%', marginBottom: '24px' }}
              />
            )}

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <button
                onClick={exportCSV}
                disabled={!hasEnoughAudio}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ccc',
                  background: '#fff',
                  cursor: hasEnoughAudio ? 'pointer' : 'not-allowed',
                  opacity: hasEnoughAudio ? 1 : 0.5,
                }}
              >
                Export CSV
              </button>
              <button
                onClick={() => {}}
                disabled={!hasEnoughAudio}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ccc',
                  background: '#fff',
                  cursor: hasEnoughAudio ? 'pointer' : 'not-allowed',
                  opacity: hasEnoughAudio ? 1 : 0.5,
                }}
              >
                Download chart (PNG)
              </button>
              <button
                onClick={handleSaveToHistory}
                disabled={!hasEnoughAudio || savedToHistory}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #ccc',
                  background: savedToHistory ? '#e8f5e9' : '#fff',
                  color: savedToHistory ? '#2e7d32' : 'inherit',
                  cursor: hasEnoughAudio && !savedToHistory ? 'pointer' : 'not-allowed',
                  opacity: hasEnoughAudio ? 1 : 0.5,
                }}
              >
                {savedToHistory ? 'Saved to History ✓' : 'Save to History'}
              </button>
            </div>
          </motion.div>
        )}

        {state === 'failed' && (
          <motion.div
            key="error"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass"
            style={{
              padding: '32px',
              borderRadius: '24px',
              textAlign: 'center',
            }}
          >
            <div
              style={{
                fontSize: '24px',
                fontWeight: 600,
                color: '#D43F00',
                marginBottom: '16px',
              }}
            >
              Error
            </div>
            <div
              style={{
                fontSize: '15px',
                lineHeight: 1.5,
                color: '#5c5b57',
                marginBottom: '24px',
                maxWidth: '600px',
                margin: '0 auto 24px',
              }}
            >
              {errorMsg}
            </div>
            <button
              onClick={() => reset()}
              style={{
                padding: '12px 24px',
                borderRadius: '999px',
                border: 'none',
                background: '#FF5A00',
                color: '#fff',
                cursor: 'pointer',
                fontWeight: 600,
              }}
            >
              Try Again
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Home;
