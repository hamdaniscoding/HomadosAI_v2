import { useEffect, useRef } from 'react';

const BackgroundField = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glow1Ref = useRef<HTMLDivElement>(null);
  const glow2Ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const cv = canvasRef.current;
    const g1 = glow1Ref.current;
    const g2 = glow2Ref.current;
    
    if (!cv || !g1 || !g2) return;
    const ctx = cv.getContext('2d');
    if (!ctx) return;

    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    let reduce = mediaQuery.matches;
    
    const updateMotionPreference = (e: MediaQueryListEvent) => {
      reduce = e.matches;
    };
    mediaQuery.addEventListener('change', updateMotionPreference);

    const GAP = 24, R0 = 620;
    let W = 0, H = 0, dpr = 1, dots: { hx: number, hy: number, x: number, y: number, vx: number, vy: number }[] = [];
    
    const tgt = { x: -999, y: -999, on: 0 };
    const m1 = { x: -999, y: -999, a: 0 };
    const m2 = { x: -999, y: -999, a: 0 };

    const build = () => {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = cv.clientWidth; H = cv.clientHeight;
      
      const cols = Math.floor(W / GAP);
      const rows = Math.floor(H / GAP);
      let actualGap = GAP;
      
      // limit max dots to ~4000
      if (cols * rows > 4000) {
        const area = W * H;
        actualGap = Math.sqrt(area / 4000);
      }

      cv.width = W * dpr; cv.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      dots = [];
      for (let y = actualGap / 2; y < H; y += actualGap) {
        for (let x = actualGap / 2; x < W; x += actualGap) {
          dots.push({ hx: x, hy: y, x: x, y: y, vx: 0, vy: 0 });
        }
      }
    };
    build();

    const pos = (e: any) => {
      if (window.innerWidth < 768) {
        tgt.on = 0;
        return; // disable pointer tracking under 768px width
      }
      const r = cv.getBoundingClientRect();
      const sx = r.width ? cv.clientWidth / r.width : 1;
      const sy = r.height ? cv.clientHeight / r.height : 1;
      const p = e.touches && e.touches[0] ? e.touches[0] : e;
      tgt.x = (p.clientX - r.left) * sx;
      tgt.y = (p.clientY - r.top) * sy;
      if (!tgt.on) { m1.x = m2.x = tgt.x; m1.y = m2.y = tgt.y; }
      tgt.on = 1;
    };
    const leave = () => { tgt.on = 0; };

    window.addEventListener('pointermove', pos, { passive: true, capture: true });
    window.addEventListener('mousemove', pos, { passive: true, capture: true });
    document.addEventListener('pointerleave', leave);
    window.addEventListener('blur', leave);
    
    // Resume when visible
    const onVisibilityChange = () => {
      if (document.hidden) {
        tgt.on = 0;
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    const ro = new ResizeObserver(build);
    ro.observe(cv);

    let t0 = performance.now(), raf = 0, alive = true;
    
    const frame = (now: number) => {
      if (!alive) return;
      raf = requestAnimationFrame(frame);
      if (document.hidden) return; // pause loop when hidden

      const t = (now - t0) / 1000;
      
      m1.x += (tgt.x - m1.x) * 0.055; m1.y += (tgt.y - m1.y) * 0.055;
      m2.x += (tgt.x - m2.x) * 0.022; m2.y += (tgt.y - m2.y) * 0.022;
      m1.a += (tgt.on - m1.a) * 0.04; m2.a += (tgt.on - m2.a) * 0.025;
      
      g1.style.transform = `translate(${m1.x.toFixed(1)}px,${m1.y.toFixed(1)}px)`;
      g2.style.transform = `translate(${m2.x.toFixed(1)}px,${m2.y.toFixed(1)}px)`;
      g1.style.opacity = m1.a.toFixed(3); 
      g2.style.opacity = m2.a.toFixed(3);
      
      ctx.clearRect(0, 0, W, H);
      
      for (let i = 0; i < dots.length; i++) {
        const d = dots[i];
        const dx = m1.x - d.hx, dy = m1.y - d.hy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const breath = Math.sin(t * 0.7);
        const R = R0 * (1 + 0.07 * breath);
        let k = 0;
        
        if (dist < R) { k = Math.pow(1 - dist / R, 1.7) * m1.a; }
        
        let tx = d.hx, ty = d.hy;
        
        if (!reduce) {
          // Idle drift
          tx += Math.sin(t * 0.45 + d.hx * 0.013) * 1.6;
          ty += Math.cos(t * 0.4 + d.hy * 0.013) * 1.6;
          
          const pull = 0.34 * (1 + 0.14 * breath);
          tx += dx * pull * k; ty += dy * pull * k;
          
          const wv = Math.sin(t * 0.8 - dist * 0.016) * 5 * k;
          if (dist > 1) { tx += (dx / dist) * wv; ty += (dy / dist) * wv; }
        }
        
        d.vx += (tx - d.x) * 0.05; d.vy += (ty - d.y) * 0.05;
        d.vx *= 0.86; d.vy *= 0.86;
        d.x += d.vx; d.y += d.vy;
        
        const r = 1.1 + 1.7 * k;
        const al = 0.42 + 0.5 * k;
        const ko = k * 0.5;
        
        const rr = Math.round(205 + 50 * ko), gg = Math.round(185 - 95 * ko), bb = Math.round(168 - 168 * ko);
        ctx.fillStyle = `rgba(${rr},${gg},${bb},${al.toFixed(2)})`;
        
        if (k < 0.02) { 
          ctx.fillRect(d.x - 1, d.y - 1, 2, 2); 
        } else { 
          ctx.beginPath(); ctx.arc(d.x, d.y, r, 0, 6.2832); ctx.fill(); 
        }
      }
    };
    raf = requestAnimationFrame(frame);

    return () => {
      alive = false;
      cancelAnimationFrame(raf);
      window.removeEventListener('pointermove', pos, true);
      window.removeEventListener('mousemove', pos, true);
      document.removeEventListener('pointerleave', leave);
      window.removeEventListener('blur', leave);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      mediaQuery.removeEventListener('change', updateMotionPreference);
      ro.disconnect();
    };
  }, []);

  return (
    <>
      <div style={{ animation: 'w1 28s ease-in-out infinite', position: 'absolute', top: '-120px', left: '-120px', width: '640px', height: '640px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,90,0,.17),rgba(255,90,0,0) 70%)', zIndex: 0 }}></div>
      <div style={{ animation: 'w2 34s ease-in-out infinite', position: 'absolute', top: '120px', right: '-160px', width: '700px', height: '700px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,150,80,.24),rgba(255,150,80,0) 68%)', zIndex: 0 }}></div>
      <div style={{ animation: 'w3 40s ease-in-out infinite', position: 'absolute', top: '760px', left: '30%', width: '600px', height: '600px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,120,40,.20),rgba(255,120,40,0) 70%)', zIndex: 0 }}></div>
      <div style={{ animation: 'w2 44s ease-in-out -18s infinite reverse', position: 'absolute', top: '380px', left: '8%', width: '520px', height: '520px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,170,110,.20),rgba(255,170,110,0) 70%)', zIndex: 0 }}></div>
      
      <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', zIndex: 1 }}></canvas>
      
      <div ref={glow2Ref} style={{ position: 'absolute', left: 0, top: 0, width: '1500px', height: '1500px', margin: '-750px 0 0 -750px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,150,80,.05),rgba(255,150,80,0) 68%)', opacity: 0, pointerEvents: 'none', willChange: 'transform,opacity', zIndex: 2 }}></div>
      <div ref={glow1Ref} style={{ position: 'absolute', left: 0, top: 0, width: '1100px', height: '1100px', margin: '-550px 0 0 -550px', borderRadius: '50%', background: 'radial-gradient(circle,rgba(255,90,0,.10),rgba(255,90,0,0) 70%)', opacity: 0, pointerEvents: 'none', willChange: 'transform,opacity', zIndex: 2 }}></div>
      
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.22, mixBlendMode: 'multiply', pointerEvents: 'none', zIndex: 3 }} xmlns="http://www.w3.org/2000/svg">
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>
          <feColorMatrix values="0 0 0 0 .2  0 0 0 0 .12  0 0 0 0 .05  0 0 0 .9 0"/>
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)"/>
      </svg>
    </>
  );
};

export default BackgroundField;
