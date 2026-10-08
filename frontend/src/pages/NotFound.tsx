import { Link } from 'react-router-dom';

const NotFound = () => {
  return (
    <div style={{ padding: '160px 24px', textAlign: 'center', position: 'relative', zIndex: 10 }}>
      <div style={{ fontSize: '12px', letterSpacing: '.24em', color: '#FF5A00', textTransform: 'uppercase', fontWeight: 700, marginBottom: '16px' }}>Error 404</div>
      <h1 style={{ fontFamily: "'Instrument Serif', serif", fontSize: '80px', marginBottom: '24px' }}>Page not found</h1>
      <p style={{ color: 'var(--color-muted)', marginBottom: '40px' }}>The page you are looking for does not exist.</p>
      <Link to="/" className="cta" style={{ display: 'inline-flex', padding: '16px 32px', background: 'linear-gradient(135deg,#FF8A3D 0%,#FF5A00 55%,#D43F00 100%)', color: '#fff', borderRadius: '999px', fontWeight: 600 }}>
        Return home
      </Link>
    </div>
  );
};
export default NotFound;
