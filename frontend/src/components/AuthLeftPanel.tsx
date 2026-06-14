import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import AgentCanvas from './AgentCanvas';

const FEATURES = [
  'Market Research',
  'Product Design',
  'Architecture Planning',
  'Execution Strategy',
  'Investor Readiness',
];

export default function AuthLeftPanel() {
  const [health, setHealth]   = useState(99.98);
  const [memory, setMemory]   = useState(327);

  useEffect(() => {
    const id = setInterval(() => {
      setHealth(parseFloat((99.94 + Math.random() * 0.06).toFixed(2)));
      setMemory(m => m + Math.floor(Math.random() * 3 - 1));
    }, 2800);
    return () => clearInterval(id);
  }, []);

  const cards = [
    { label: 'SYSTEM HEALTH', value: `${health}%`,    delay: 0    },
    { label: 'TOOLS ONLINE',  value: '84',             delay: 0.8  },
    { label: 'MEMORY INDEX',  value: String(memory),  delay: 1.6  },
    { label: 'AGENTS ACTIVE', value: '5',              delay: 2.4  },
  ];

  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: '100%', width: '100%',
      overflow: 'hidden', position: 'relative',
      background: 'rgb(var(--c-bg-deep))',
    }}>
      {/* ── Canvas zone (fills remaining space above text section) ── */}
      <div style={{ flex: '1 1 auto', position: 'relative', minHeight: 0, overflow: 'hidden' }}>
        {/* Canvas fills this div */}
        <div style={{ position: 'absolute', inset: 0 }}>
          <AgentCanvas />
        </div>

        {/* APS logo — top-left, above canvas */}
        <Link to="/" style={{
          position: 'absolute', top: 28, left: 32, zIndex: 10,
          display: 'flex', alignItems: 'center', gap: 12,
          textDecoration: 'none', cursor: 'pointer',
        }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'rgb(var(--c-accent-cyan) / 0.09)',
            border: '1px solid rgb(var(--c-accent-cyan) / 0.28)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.2s, border-color 0.2s',
          }}
            onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgb(var(--c-accent-cyan) / 0.16)'; (e.currentTarget as HTMLDivElement).style.borderColor = 'rgb(var(--c-accent-cyan) / 0.5)'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgb(var(--c-accent-cyan) / 0.09)'; (e.currentTarget as HTMLDivElement).style.borderColor = 'rgb(var(--c-accent-cyan) / 0.28)'; }}
          >
            <span style={{ color: 'rgb(var(--c-accent-cyan))', fontFamily: '"JetBrains Mono", monospace', fontSize: 14, fontWeight: 700 }}>A</span>
          </div>
          <div>
            <div style={{ color: 'rgb(var(--c-primary))', fontFamily: '"JetBrains Mono", monospace', fontSize: 11, fontWeight: 700, letterSpacing: '0.22em' }}>APS</div>
            <div style={{ color: 'rgb(var(--c-primary) / 0.35)', fontFamily: '"JetBrains Mono", monospace', fontSize: 8.5, letterSpacing: '0.12em' }}>AUTONOMOUS PRODUCT STUDIO</div>
          </div>
        </Link>

        {/* Gradient fade at the bottom of canvas zone into text zone */}
        <div style={{
          position: 'absolute', bottom: 0, left: 0, right: 0, height: 72,
          background: 'linear-gradient(to bottom, transparent, rgb(var(--c-bg-deep) / 0.96))',
          pointerEvents: 'none',
        }} />
      </div>

      {/* ── Text + telemetry section — BELOW canvas, never overlaps ── */}
      <div style={{
        flexShrink: 0,
        background: 'rgb(var(--c-bg-deep) / 0.98)',
        borderTop: '1px solid rgb(var(--c-primary) / 0.05)',
        padding: '20px 36px 28px',
      }}>
        {/* Headline */}
        <div style={{
          fontFamily: '"JetBrains Mono", monospace',
          fontSize: 9,
          color: 'rgb(var(--c-accent-cyan) / 0.48)',
          letterSpacing: '0.28em',
          textTransform: 'uppercase',
          marginBottom: 10,
        }}>
          AUTONOMOUS STARTUP INTELLIGENCE
        </div>

        {/* Feature pills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 20px', marginBottom: 20 }}>
          {FEATURES.map(f => (
            <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div style={{ width: 3.5, height: 3.5, borderRadius: '50%', background: 'rgb(var(--c-accent-cyan))', opacity: 0.45, flexShrink: 0 }} />
              <span style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 11, color: 'rgb(var(--c-primary) / 0.55)', letterSpacing: '0.03em' }}>
                {f}
              </span>
            </div>
          ))}
        </div>

        {/* Floating telemetry cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
          {cards.map(c => (
            <motion.div
              key={c.label}
              animate={{ y: [0, -5, 0] }}
              transition={{ duration: 3.6, repeat: Infinity, ease: 'easeInOut', delay: c.delay }}
              style={{
                background: 'rgb(var(--c-accent-cyan) / 0.04)',
                border: '1px solid rgb(var(--c-accent-cyan) / 0.09)',
                borderRadius: 11,
                padding: '10px 14px',
              }}
            >
              <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 17, fontWeight: 700, color: 'rgb(var(--c-primary))', lineHeight: 1.1 }}>
                {c.value}
              </div>
              <div style={{ fontFamily: '"JetBrains Mono", monospace', fontSize: 8, color: 'rgb(var(--c-primary) / 0.35)', letterSpacing: '0.12em', marginTop: 4 }}>
                {c.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}
