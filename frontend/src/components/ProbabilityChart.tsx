import React, { useRef, useEffect, useState, useMemo } from 'react';
import { WsResultMessage } from '../types/protocol';

interface ProbabilityChartProps {
  scores: WsResultMessage[];
  currentTime?: number;
  calibrated?: boolean;
  threshold?: number;
  mode?: 'live' | 'results';
}

export const ProbabilityChart: React.FC<ProbabilityChartProps> = ({
  scores,
  currentTime,
  calibrated = false,
  threshold = 0.5,
  mode = 'results',
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [hoverX, setHoverX] = useState<number | null>(null);
  const height = 240;

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0] && entries[0].contentRect) {
        setWidth(Math.floor(entries[0].contentRect.width));
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const summary = useMemo(() => {
    const analyzed = scores.filter((s) => s.ai_probability !== null);
    const skipped = scores.length - analyzed.length;
    if (analyzed.length === 0) {
      return { avg: 0, peak: 0, peakT: 0, timeAbove: 0, analyzed: 0, skipped };
    }

    let sum = 0;
    let peak = 0;
    let peakT = 0;
    let above = 0;
    analyzed.forEach((s) => {
      const p = s.smoothed_probability ?? s.ai_probability ?? 0;
      sum += p;
      if (p > peak) {
        peak = p;
        peakT = s.t;
      }
      if (p > 0.5) {
        above += scores.length > 1 ? scores[1].t - scores[0].t : 1;
      }
    });
    return {
      avg: sum / analyzed.length,
      peak,
      peakT,
      timeAbove: above,
      analyzed: analyzed.length,
      skipped,
    };
  }, [scores]);

  const paddingXLeft = 48;
  const paddingXRight = 16;
  const paddingYTop = 16;
  const paddingYBottom = 38;

  if (width === 0 || scores.length === 0) {
    return (
      <div
        ref={containerRef}
        style={{
          width: '100%',
          minWidth: 0,
          maxWidth: '100%',
          height: `${height}px`,
          background: '#faf9f8',
          borderRadius: '12px',
          position: 'relative',
          overflow: 'hidden',
          boxSizing: 'border-box',
        }}
      >
        {scores.length === 0 && width > 0 && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#777',
              fontSize: '13px',
              padding: '16px',
              textAlign: 'center',
            }}
          >
            The graph starts after the first 5 seconds of audio
          </div>
        )}
      </div>
    );
  }

  const plotWidth = Math.max(10, width - paddingXLeft - paddingXRight);
  const plotHeight = Math.max(10, height - paddingYTop - paddingYBottom);

  // Time boundaries
  const latestT = scores.length > 0 ? scores[scores.length - 1].t : 0;
  let minT = 0;
  let maxT = 60;

  if (mode === 'live') {
    if (latestT <= 60) {
      minT = 0;
      maxT = 60;
    } else {
      minT = Math.floor(latestT - 60);
      maxT = minT + 60;
    }
  } else {
    minT = 0;
    maxT = Math.max(latestT, 5);
  }

  const spanT = Math.max(1, maxT - minT);

  const mapX = (t: number) => {
    return paddingXLeft + ((t - minT) / spanT) * plotWidth;
  };

  const mapY = (p: number) => {
    const clampedP = Math.max(0, Math.min(1, p));
    return paddingYTop + (1 - clampedP) * plotHeight;
  };

  // Adaptive X ticks (ticks adapt every 5/10/15/20/30s and never overlap)
  const getAdaptiveXTicks = () => {
    // We want at least 48px space per tick label
    const maxTicks = Math.max(2, Math.floor(plotWidth / 48));
    const rawStep = spanT / maxTicks;
    const steps = [1, 2, 5, 10, 15, 20, 30, 60, 120, 300];
    let step = steps.find((s) => s >= rawStep) || Math.ceil(rawStep);
    if (spanT >= 40 && step < 5) step = 5;

    const start = Math.ceil(minT / step) * step;
    const ticks: number[] = [];
    for (let t = start; t <= maxT + 0.001; t += step) {
      ticks.push(Math.round(t * 10) / 10);
    }
    return ticks;
  };

  const xTicks = getAdaptiveXTicks();
  const yTicks = [0, 0.25, 0.5, 0.75, 1.0];

  // Discontinuous paths for smoothed probability (gaps on skipped/null)
  let currentPath = '';
  const paths: string[] = [];
  let lastValid = false;

  // Render points that fall within or slightly adjacent to [minT, maxT]
  const visibleScores = scores.filter((s) => s.t >= minT - 2 && s.t <= maxT + 2);

  visibleScores.forEach((s) => {
    const val = s.smoothed_probability ?? s.ai_probability;
    const isValid = val !== null && val !== undefined;
    if (isValid) {
      const x = mapX(s.t);
      const y = mapY(val!);
      if (!lastValid) {
        currentPath = `M ${x.toFixed(1)},${y.toFixed(1)}`;
      } else {
        currentPath += ` L ${x.toFixed(1)},${y.toFixed(1)}`;
      }
    } else {
      if (lastValid && currentPath) {
        paths.push(currentPath);
        currentPath = '';
      }
    }
    lastValid = isValid;
  });
  if (currentPath) paths.push(currentPath);

  const handleMouseMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clientX = 'touches' in e ? e.touches[0].clientX : (e as React.MouseEvent).clientX;
    const x = clientX - rect.left;
    if (x >= paddingXLeft && x <= width - paddingXRight) {
      setHoverX(x);
    } else {
      setHoverX(null);
    }
  };

  let hoveredScore: WsResultMessage | null = null;
  if (hoverX !== null && scores.length > 0) {
    const tHover = minT + ((hoverX - paddingXLeft) / plotWidth) * spanT;
    hoveredScore = scores.reduce((prev, curr) =>
      Math.abs(curr.t - tHover) < Math.abs(prev.t - tHover) ? curr : prev,
      scores[0]
    );
  }

  const currentX = currentTime !== undefined && currentTime >= minT && currentTime <= maxT
    ? mapX(currentTime)
    : null;

  const clipId = `chart-clip-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        width: '100%',
        minWidth: 0,
        maxWidth: '100%',
        boxSizing: 'border-box',
        overflow: 'hidden',
      }}
    >
      {/* Small header row above chart: legend and status note never clipped */}
      <div
        className="chart-header-row"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '8px',
          width: '100%',
          minWidth: 0,
          maxWidth: '100%',
          boxSizing: 'border-box',
          fontSize: '11px',
          padding: '0 2px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
            color: '#666',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div
              style={{
                width: '12px',
                height: '2px',
                background: '#FF5A00',
                borderRadius: '1px',
              }}
            />
            <span>Smoothed</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background: '#FFB27A',
              }}
            />
            <span>Raw</span>
          </div>
          <div style={{ color: '#8c8881' }}>Gaps = no speech / skipped</div>
        </div>

        <div
          style={{
            color: '#8c8881',
            fontStyle: 'italic',
            whiteSpace: 'nowrap',
          }}
        >
          {calibrated ? `Threshold: ${Math.round(threshold * 100)}%` : 'Uncalibrated, score only'}
        </div>
      </div>

      {/* SVG Chart Container */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          minWidth: 0,
          maxWidth: '100%',
          height: `${height}px`,
          position: 'relative',
          background: '#fff',
          border: '1px solid #e8e6e1',
          borderRadius: '12px',
          overflow: 'hidden',
          boxSizing: 'border-box',
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverX(null)}
        onTouchMove={handleMouseMove}
        onTouchEnd={() => setHoverX(null)}
      >
        <svg
          width={width}
          height={height}
          style={{
            display: 'block',
            width: '100%',
            maxWidth: '100%',
            height: `${height}px`,
            overflow: 'hidden',
          }}
        >
          <defs>
            <clipPath id={clipId}>
              <rect
                x={paddingXLeft}
                y={paddingYTop}
                width={plotWidth}
                height={plotHeight}
              />
            </clipPath>
          </defs>

          {/* Y grid lines and ticks */}
          {yTicks.map((p) => (
            <React.Fragment key={p}>
              <line
                x1={paddingXLeft}
                y1={mapY(p)}
                x2={width - paddingXRight}
                y2={mapY(p)}
                stroke="#f0ede8"
                strokeDasharray={p === 0 || p === 1 ? undefined : '3 3'}
              />
              <text
                x={paddingXLeft - 8}
                y={mapY(p) + 4}
                textAnchor="end"
                fontSize="11"
                fill="#777"
              >
                {Math.round(p * 100)}
              </text>
            </React.Fragment>
          ))}

          {/* Calibrated threshold line */}
          {calibrated && (
            <line
              x1={paddingXLeft}
              y1={mapY(threshold)}
              x2={width - paddingXRight}
              y2={mapY(threshold)}
              stroke="#ff4444"
              strokeDasharray="4 4"
            />
          )}

          {/* X grid lines and ticks */}
          {xTicks.map((t) => (
            <React.Fragment key={t}>
              <line
                x1={mapX(t)}
                y1={paddingYTop}
                x2={mapX(t)}
                y2={height - paddingYBottom}
                stroke="#f7f6f4"
              />
              <line
                x1={mapX(t)}
                y1={height - paddingYBottom}
                x2={mapX(t)}
                y2={height - paddingYBottom + 4}
                stroke="#ccc"
              />
              <text
                x={mapX(t)}
                y={height - paddingYBottom + 16}
                textAnchor="middle"
                fontSize="11"
                fill="#666"
              >
                {t}
              </text>
            </React.Fragment>
          ))}

          {/* Axis titles */}
          <text
            x={paddingXLeft + plotWidth / 2}
            y={height - 6}
            textAnchor="middle"
            fontSize="11"
            fill="#333"
            fontWeight="bold"
          >
            Time (s)
          </text>
          <text
            x={12}
            y={paddingYTop + plotHeight / 2}
            transform={`rotate(-90 12,${paddingYTop + plotHeight / 2})`}
            textAnchor="middle"
            fontSize="11"
            fill="#333"
            fontWeight="bold"
          >
            Probability of AI / spoof (%)
          </text>

          {/* Plotting area clipped strictly within bounds */}
          <g clipPath={`url(#${clipId})`}>
            {/* Smoothed paths */}
            {paths.map((p, i) => (
              <path
                key={i}
                d={p}
                fill="none"
                stroke="#FF5A00"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ))}

            {/* Raw dots */}
            {visibleScores.map((s, i) => {
              if (s.ai_probability !== null && s.ai_probability !== undefined) {
                return (
                  <circle
                    key={i}
                    cx={mapX(s.t)}
                    cy={mapY(s.ai_probability)}
                    r="2"
                    fill="#FFB27A"
                    opacity={0.65}
                  />
                );
              }
              return null;
            })}

            {/* Current playback / scrub indicator */}
            {currentX !== null && (
              <line
                x1={currentX}
                y1={paddingYTop}
                x2={currentX}
                y2={height - paddingYBottom}
                stroke="#222"
                strokeWidth="2"
                opacity={0.4}
              />
            )}

            {/* Hover guideline */}
            {hoverX !== null && hoveredScore && (
              <line
                x1={mapX(hoveredScore.t)}
                y1={paddingYTop}
                x2={mapX(hoveredScore.t)}
                y2={height - paddingYBottom}
                stroke="#0066cc"
                strokeDasharray="2 2"
              />
            )}
          </g>
        </svg>

        {/* Hover Tooltip */}
        {hoverX !== null && hoveredScore && (
          <div
            style={{
              position: 'absolute',
              left: Math.max(
                paddingXLeft,
                Math.min(mapX(hoveredScore.t) + 10, width - paddingXRight - 150)
              ),
              top: 24,
              background: 'rgba(20, 20, 20, 0.88)',
              color: '#fff',
              padding: '6px 10px',
              borderRadius: '6px',
              fontSize: '11px',
              pointerEvents: 'none',
              zIndex: 10,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              maxWidth: '180px',
            }}
          >
            <div>
              <strong>Time:</strong> {hoveredScore.t.toFixed(1)}s
            </div>
            {hoveredScore.smoothed_probability !== null || hoveredScore.ai_probability !== null ? (
              <>
                <div>
                  <strong>Smoothed:</strong>{' '}
                  {hoveredScore.smoothed_probability !== null
                    ? `${(hoveredScore.smoothed_probability * 100).toFixed(1)}%`
                    : '—'}
                </div>
                <div>
                  <strong>Raw:</strong>{' '}
                  {hoveredScore.ai_probability !== null
                    ? `${(hoveredScore.ai_probability * 100).toFixed(1)}%`
                    : '—'}
                </div>
                {hoveredScore.active_speaker && (
                  <div>
                    <strong>Speaker:</strong> {hoveredScore.active_speaker}
                  </div>
                )}
              </>
            ) : (
              <div style={{ color: '#ffb0b0' }}>
                Skipped: {hoveredScore.reason || 'No speech'}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary row wraps into 2-3 columns on narrow widths */}
      <div
        className="chart-summary-row"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(115px, 1fr))',
          gap: '8px 14px',
          fontSize: '12px',
          background: 'rgba(255, 255, 255, 0.65)',
          border: '1px solid rgba(220, 215, 205, 0.6)',
          padding: '10px 14px',
          borderRadius: '10px',
          color: '#444',
          width: '100%',
          minWidth: 0,
          maxWidth: '100%',
          boxSizing: 'border-box',
          overflow: 'hidden',
        }}
      >
        <div>
          <span style={{ color: '#7a7670' }}>Avg:</span>{' '}
          <strong>{(summary.avg * 100).toFixed(1)}%</strong>
        </div>
        <div>
          <span style={{ color: '#7a7670' }}>Peak:</span>{' '}
          <strong>{(summary.peak * 100).toFixed(1)}%</strong>{' '}
          <span style={{ fontSize: '11px', color: '#7a7670' }}>
            ({summary.peakT.toFixed(1)}s)
          </span>
        </div>
        <div>
          <span style={{ color: '#7a7670' }}>&gt;50%:</span>{' '}
          <strong>{summary.timeAbove.toFixed(1)}s</strong>
        </div>
        <div>
          <span style={{ color: '#7a7670' }}>Analyzed:</span>{' '}
          <strong>{summary.analyzed}</strong>
        </div>
        <div>
          <span style={{ color: '#7a7670' }}>Skipped:</span>{' '}
          <strong>{summary.skipped}</strong>
        </div>
      </div>
    </div>
  );
};
