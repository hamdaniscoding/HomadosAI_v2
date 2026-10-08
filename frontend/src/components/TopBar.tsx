import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';

const links = [
  { path: '/', label: 'Analyze' },
  { path: '/history', label: 'History' },
  { path: '/how-it-works', label: 'How it works' },
  { path: '/about', label: 'About' },
];

const TopBar = () => {
  const [health, setHealth] = useState<'ready' | 'loading' | 'offline'>('loading');
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    let timeout: ReturnType<typeof setTimeout>;
    
    const checkHealth = async () => {
      try {
        const res = await fetch('/api/v1/health');
        if (res.ok) {
          setHealth('ready');
        } else {
          setHealth('offline');
        }
      } catch (e) {
        setHealth('offline');
      }
      timeout = setTimeout(checkHealth, 5000);
    };
    
    checkHealth();
    return () => clearTimeout(timeout);
  }, []);

  return (
    <>
      <div style={{ position: 'relative', zIndex: 10, display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center', justifyContent: 'space-between', padding: '22px 48px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: '1 1 260px' }}>
          <img src="/logo.png" alt="Homados AI logo" style={{ width: '76px', height: 'auto', display: 'block', filter: 'drop-shadow(0 6px 12px rgba(255,90,0,.28))' }} />
          <span className="brand" style={{ fontFamily: "'Instrument Serif', serif", fontSize: '42px', letterSpacing: '-.005em', lineHeight: 1 }}>
            Homados <span className="brandai">AI</span>
          </span>
        </div>
        
        {/* Desktop Nav */}
        <nav className="bar" style={{ display: 'flex', gap: '2px', fontSize: '14px', padding: '5px', borderRadius: '999px', flex: '0 0 auto' }}>
          {links.map((l) => {
            const isActive = location.pathname === l.path || (l.path !== '/' && location.pathname.startsWith(l.path));
            return (
              <NavLink 
                key={l.path} 
                to={l.path} 
                style={{ position: 'relative' }} 
                className={`tab ${isActive ? 'on' : ''}`}
              >
                {isActive && (
                  <motion.div 
                    layoutId="nav-pill" 
                    style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg,#fff,rgba(255,255,255,.7))', borderRadius: '999px', boxShadow: '0 3px 10px rgba(120,60,20,.14), inset 0 1px 0 #fff', zIndex: -1 }} 
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                  />
                )}
                <span style={{ position: 'relative', zIndex: 1 }}>{l.label}</span>
              </NavLink>
            );
          })}
        </nav>
        
        <div style={{ flex: '1 1 220px', display: 'flex', justifyContent: 'flex-end' }}>
          <div className="glass" style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: '#4a4945', padding: '8px 15px', borderRadius: '999px' }}>
            <span className={health === 'ready' ? 'live' : ''} style={{ width: '7px', height: '7px', borderRadius: '50%', background: health === 'ready' ? '#FF5A00' : '#CDB9A8', display: 'inline-block' }}></span>
            {health === 'ready' ? 'Detector ready' : health === 'loading' ? 'Detector loading…' : 'Detector offline'}
          </div>
        </div>
      </div>

      <div className="mobile-menu-btn glass" style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 100, padding: '12px', borderRadius: '50%', cursor: 'pointer', display: 'none' }} onClick={() => setMenuOpen(!menuOpen)}>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
      </div>

      <AnimatePresence>
        {menuOpen && (
          <motion.div 
            initial={{ y: '100%' }} animate={{ y: 0 }} exit={{ y: '100%' }} transition={{ type: 'spring', bounce: 0, duration: 0.4 }}
            className="glass"
            style={{ position: 'fixed', bottom: 0, left: 0, right: 0, padding: '24px', borderTopLeftRadius: '24px', borderTopRightRadius: '24px', zIndex: 99, display: 'flex', flexDirection: 'column', gap: '16px' }}
          >
            {links.map((l) => (
              <NavLink key={l.path} to={l.path} onClick={() => setMenuOpen(false)} style={{ padding: '12px', fontSize: '18px', fontWeight: 500, color: 'var(--color-ink)', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
                {l.label}
              </NavLink>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @media (max-width: 720px) {
          .bar { display: none !important; }
          .mobile-menu-btn { display: flex !important; }
        }
      `}</style>
    </>
  );
};

export default TopBar;
