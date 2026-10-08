const About = () => {
  return (
    <div style={{ padding: '80px 24px', maxWidth: '800px', margin: '0 auto', position: 'relative', zIndex: 10 }}>
      <h1 style={{ fontFamily: "'Instrument Serif', serif", fontSize: '64px', marginBottom: '40px' }}>About the Project</h1>
      
      <div className="glass" style={{ padding: '40px', borderRadius: '24px', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>Homados AI</h2>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6, marginBottom: '16px' }}>
          This project is being developed for the <strong>Smart India Hackathon 2026</strong>, 
          addressing problem statement <strong>26104</strong>.
        </p>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>
          Homados AI aims to detect AI-generated and fake audio in real-time.
        </p>
      </div>

      <div className="glass" style={{ padding: '40px', borderRadius: '24px', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>Privacy & Data Handling</h2>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6, marginBottom: '16px' }}>
          Audio is analyzed strictly in memory. It is never written to disk.
        </p>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>
          Scores and session metadata are only stored if you explicitly check the "Save this session" box.
        </p>
      </div>

      <div className="glass" style={{ padding: '40px', borderRadius: '24px', marginBottom: '32px' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>Model Status</h2>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>
          The detection model is currently <strong>in training</strong> and is not yet validated for production use.
        </p>
      </div>

      <div className="glass" style={{ padding: '40px', borderRadius: '24px' }}>
        <h2 style={{ fontSize: '24px', marginBottom: '16px', fontFamily: "'Instrument Serif', serif" }}>Team</h2>
        <p style={{ color: 'var(--color-muted)', lineHeight: 1.6 }}>
          [Team names to be added]
        </p>
      </div>
    </div>
  );
};
export default About;
