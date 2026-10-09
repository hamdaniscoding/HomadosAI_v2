import React, { useRef, useEffect, useState } from 'react';
import { WsResultMessage } from '../types/protocol';

interface ProbabilityChartProps {
  scores: WsResultMessage[];
  currentTime?: number; // for scrubber
}

export const ProbabilityChart: React.FC<ProbabilityChartProps> = ({ scores, currentTime }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const height = 160;

  useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        setWidth(entries[0].contentRect.width);
      }
    });
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  if (width === 0 || scores.length === 0) {
    return (
      <div ref={containerRef} style={{ width: '100%', height: `${height}px`, background: '#faf9f8', borderRadius: '12px', position: 'relative' }}>
        {scores.length === 0 && width > 0 && (
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#666', fontSize: '14px' }}>
            The graph starts after the first 5 seconds of audio
          </div>
        )}
      </div>
    );
  }

  const maxT = Math.max(60, scores[scores.length - 1].t);
  const paddingX = 20;
  const paddingY = 20;
  
  const mapX = (t: number) => paddingX + (t / maxT) * (width - paddingX * 2);
  const mapY = (p: number) => height - paddingY - p * (height - paddingY * 2);

  // Separate valid points for smooth curve and gaps
  const validPoints: {x: number, y: number}[] = [];
  const rawPoints: {x: number, y: number}[] = [];
  
  scores.forEach(s => {
    if (s.smoothed_probability !== null) {
      validPoints.push({ x: mapX(s.t), y: mapY(s.smoothed_probability) });
    }
    if (s.ai_probability !== null) {
      rawPoints.push({ x: mapX(s.t), y: mapY(s.ai_probability) });
    }
  });

  // Simple spline (Catmull-Rom)
  const getSplinePath = (pts: {x: number, y: number}[]) => {
    if (pts.length === 0) return '';
    if (pts.length === 1) return `M ${pts[0].x},${pts[0].y}`;
    
    let path = `M ${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i === 0 ? 0 : i - 1];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2 < pts.length ? i + 2 : i + 1];
      
      const cp1x = p1.x + (p2.x - p0.x) / 6;
      const cp1y = p1.y + (p2.y - p0.y) / 6;
      const cp2x = p2.x - (p3.x - p1.x) / 6;
      const cp2y = p2.y - (p3.y - p1.y) / 6;
      
      path += ` C ${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
    }
    return path;
  };

  const currentX = currentTime !== undefined ? mapX(currentTime) : null;

  return (
    <div ref={containerRef} style={{ width: '100%', height: `${height}px`, position: 'relative' }}>
      <svg width={width} height={height} style={{ display: 'block' }}>
        {/* Background grid */}
        <line x1={paddingX} y1={mapY(0.5)} x2={width - paddingX} y2={mapY(0.5)} stroke="#e0e0e0" strokeDasharray="4 4" />
        <line x1={paddingX} y1={mapY(1)} x2={width - paddingX} y2={mapY(1)} stroke="#e0e0e0" />
        <line x1={paddingX} y1={mapY(0)} x2={width - paddingX} y2={mapY(0)} stroke="#e0e0e0" />
        
        {/* Axis labels */}
        <text x={width / 2} y={height - 2} textAnchor="middle" fontSize="12" fill="#666">Time (s)</text>
        <text x={10} y={height / 2} transform={`rotate(-90 10,${height/2})`} textAnchor="middle" fontSize="12" fill="#666">Probability of AI / spoof (%)</text>
        
        {/* Main curve */}
        {validPoints.length > 0 && <path d={getSplinePath(validPoints)} fill="none" stroke="#FF5A00" strokeWidth="3" />}
        
        {/* Raw dots */}
        {rawPoints.map((pt, i) => (
          <circle key={i} cx={pt.x} cy={pt.y} r="2" fill="#FFB27A" opacity={0.5} />
        ))}
        
        {/* Current time indicator */}
        {currentX !== null && (
          <line x1={currentX} y1={0} x2={currentX} y2={height} stroke="#333" strokeWidth="2" opacity={0.5} />
        )}
      </svg>
    </div>
  );
};
