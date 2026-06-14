import { useEffect, useRef } from 'react';

interface OrbAgent { name: string; sub: string; angle: number; speed: number; }
interface Particle  { ai: number; t: number; dir: 1|-1; spd: number; sz: number; }
interface Pulse     { ai: number; t: number; spd: number; }
interface Star      { x: number; y: number; r: number; a: number; tw: number; }

const AGENTS: OrbAgent[] = [
  { name: 'RESEARCH',     sub: 'Market Intel',  angle: -Math.PI / 2,                     speed: 0.20 },
  { name: 'PRODUCT',      sub: 'Vision Layer',  angle: -Math.PI / 2 + (2 * Math.PI / 5), speed: 0.17 },
  { name: 'ARCHITECTURE', sub: 'System Design', angle: -Math.PI / 2 + (4 * Math.PI / 5), speed: 0.23 },
  { name: 'EXECUTION',    sub: 'Code Engine',   angle: -Math.PI / 2 + (6 * Math.PI / 5), speed: 0.19 },
  { name: 'PRESENTATION', sub: 'Output Layer',  angle: -Math.PI / 2 + (8 * Math.PI / 5), speed: 0.22 },
];

export default function AgentCanvas() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv  = ref.current!;
    const ctx = cv.getContext('2d')!;
    let raf = 0;
    let lt  = performance.now();

    const agents    = AGENTS.map(a => ({ ...a }));
    const particles: Particle[] = Array.from({ length: 30 }, (_, i) => ({
      ai: i % 5, t: Math.random(),
      dir: (Math.random() > 0.5 ? 1 : -1) as 1 | -1,
      spd: 0.22 + Math.random() * 0.30, sz: 1.4 + Math.random() * 1.8,
    }));
    const pulses: Pulse[] = Array.from({ length: 10 }, (_, i) => ({
      ai: i % 5, t: Math.random(), spd: 0.75 + Math.random() * 0.55,
    }));
    let stars: Star[] = [];

    function resize() {
      const dpr  = window.devicePixelRatio || 1;
      const rect = cv.getBoundingClientRect();
      cv.width   = rect.width  * dpr;
      cv.height  = rect.height * dpr;
      ctx.scale(dpr, dpr);
      stars = Array.from({ length: 80 }, () => ({
        x: Math.random() * rect.width,
        y: Math.random() * rect.height,
        r: 0.3 + Math.random() * 1.1,
        a: 0.06 + Math.random() * 0.32,
        tw: Math.random() * Math.PI * 2,
      }));
    }
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(cv);

    function draw(now: number) {
      const dt = Math.min((now - lt) / 1000, 0.05);
      lt = now;
      const t  = now / 1000;

      const dpr = window.devicePixelRatio || 1;
      const W   = cv.width  / dpr;
      const H   = cv.height / dpr;
      const cx  = W / 2;
      const cy  = H / 2;
      const OR  = Math.min(W, H) * 0.30;

      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = 'rgb(var(--c-bg-deep))';
      ctx.fillRect(0, 0, W, H);

      // Stars
      for (const s of stars) {
        const a = s.a * (0.55 + 0.45 * Math.sin(t * 0.65 + s.tw));
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(165,231,255,${a.toFixed(3)})`;
        ctx.fill();
      }

      // Ambient center glow
      const bg = ctx.createRadialGradient(cx, cy, 0, cx, cy, OR * 2.2);
      bg.addColorStop(0,   'rgba(0,180,220,0.07)');
      bg.addColorStop(0.5, 'rgba(0,120,170,0.03)');
      bg.addColorStop(1,   'transparent');
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      // Update agent angles
      for (const a of agents) a.angle += a.speed * dt;
      const pos = agents.map(a => ({
        x: cx + OR * Math.cos(a.angle),
        y: cy + OR * Math.sin(a.angle),
      }));

      // Orbit ring (dashed)
      ctx.save();
      ctx.setLineDash([3, 16]);
      ctx.beginPath();
      ctx.arc(cx, cy, OR, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgb(var(--c-primary) / 0.06)';
      ctx.lineWidth   = 0.7;
      ctx.stroke();
      ctx.restore();

      // Connection lines: center → each agent
      for (let i = 0; i < 5; i++) {
        const { x, y } = pos[i];
        const g = ctx.createLinearGradient(cx, cy, x, y);
        g.addColorStop(0, 'rgb(var(--c-accent-cyan) / 0.45)');
        g.addColorStop(1, 'rgb(var(--c-accent-cyan) / 0.03)');
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(x, y);
        ctx.strokeStyle = g;
        ctx.lineWidth   = 0.8;
        ctx.setLineDash([]);
        ctx.stroke();
      }

      // Particles
      for (const p of particles) {
        p.t += p.dir * p.spd * dt;
        if (p.t > 1) p.t = 0;
        if (p.t < 0) p.t = 1;
        const { x: ax, y: ay } = pos[p.ai];
        const px    = cx + (ax - cx) * p.t;
        const py    = cy + (ay - cy) * p.t;
        const alpha = 0.3 + 0.5 * Math.sin(p.t * Math.PI);

        const pg = ctx.createRadialGradient(px, py, 0, px, py, p.sz * 2.8);
        pg.addColorStop(0, `rgba(0,229,255,${alpha.toFixed(2)})`);
        pg.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(px, py, p.sz * 2.8, 0, Math.PI * 2);
        ctx.fillStyle = pg;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(px, py, p.sz * 0.65, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(210,248,255,${Math.min(1, alpha * 1.15).toFixed(2)})`;
        ctx.fill();
      }

      // Neural pulses (fast bright streaks along connections)
      for (const p of pulses) {
        p.t += p.spd * dt;
        if (p.t > 1) p.t = 0;
        const { x: ax, y: ay } = pos[p.ai];
        const px = cx + (ax - cx) * p.t;
        const py = cy + (ay - cy) * p.t;
        const pa = Math.sin(p.t * Math.PI) * 0.85;

        const ng = ctx.createRadialGradient(px, py, 0, px, py, 9);
        ng.addColorStop(0, `rgba(0,229,255,${(pa * 0.9).toFixed(2)})`);
        ng.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(px, py, 9, 0, Math.PI * 2);
        ctx.fillStyle = ng;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(px, py, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255,255,255,${pa.toFixed(2)})`;
        ctx.fill();
      }

      // ── Central intelligence core ──────────────────────
      const pulse = 0.5 + 0.5 * Math.sin(t * 2.3);
      const cR    = 16 + pulse * 3.5;

      // Outer glow layers
      for (let i = 6; i >= 0; i--) {
        const r = cR + i * 11 + pulse * 4;
        const a = Math.max(0, 0.065 - i * 0.008) * (0.65 + 0.35 * pulse);
        const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        cg.addColorStop(0, `rgba(0,229,255,${(a * 2.8).toFixed(3)})`);
        cg.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = cg;
        ctx.fill();
      }

      // Core rings
      ctx.beginPath();
      ctx.arc(cx, cy, cR + 8, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(0,229,255,${(0.32 + pulse * 0.18).toFixed(2)})`;
      ctx.lineWidth   = 1;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, cy, cR + 16, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(165,231,255,${(0.1 + pulse * 0.07).toFixed(2)})`;
      ctx.lineWidth   = 0.5;
      ctx.stroke();

      // Core fill
      const cf = ctx.createRadialGradient(cx, cy - 4, 0, cx, cy, cR);
      cf.addColorStop(0,    'rgba(210,248,255,0.95)');
      cf.addColorStop(0.45, 'rgb(var(--c-accent-cyan) / 0.82)');
      cf.addColorStop(1,    'rgba(0,120,170,0.55)');
      ctx.beginPath();
      ctx.arc(cx, cy, cR, 0, Math.PI * 2);
      ctx.fillStyle = cf;
      ctx.fill();

      // Core center dot
      ctx.beginPath();
      ctx.arc(cx, cy, 4.5, 0, Math.PI * 2);
      ctx.fillStyle = 'rgb(var(--c-overlay) / 0.96)';
      ctx.fill();

      // Core text
      ctx.textAlign    = 'center';
      ctx.textBaseline = 'middle';
      ctx.font         = 'bold 7px "JetBrains Mono", monospace';
      ctx.fillStyle    = 'rgb(var(--c-bg-deep) / 0.88)';
      ctx.fillText('APS',  cx, cy - 2.5);
      ctx.font = '6px "JetBrains Mono", monospace';
      ctx.fillText('CORE', cx, cy + 5.5);

      // ── Agent nodes ────────────────────────────────────
      for (let i = 0; i < 5; i++) {
        const { x, y } = pos[i];
        const ap  = 0.5 + 0.5 * Math.sin(t * 1.75 + i * 1.26);
        const nR  = 9.5;

        // Node glow
        const ng = ctx.createRadialGradient(x, y, 0, x, y, nR * 3.2);
        ng.addColorStop(0, `rgba(0,229,255,${(0.2 * ap).toFixed(2)})`);
        ng.addColorStop(1, 'transparent');
        ctx.beginPath();
        ctx.arc(x, y, nR * 3.2, 0, Math.PI * 2);
        ctx.fillStyle = ng;
        ctx.fill();

        // Node ring
        ctx.beginPath();
        ctx.arc(x, y, nR + 4.5, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(0,229,255,${(0.28 + ap * 0.2).toFixed(2)})`;
        ctx.lineWidth   = 0.7;
        ctx.stroke();

        // Node fill
        const nf = ctx.createRadialGradient(x, y - 2, 0, x, y, nR);
        nf.addColorStop(0, 'rgba(185,242,255,0.9)');
        nf.addColorStop(1, 'rgba(0,130,185,0.55)');
        ctx.beginPath();
        ctx.arc(x, y, nR, 0, Math.PI * 2);
        ctx.fillStyle = nf;
        ctx.fill();

        // Label — pushed outward from center
        const la = Math.atan2(y - cy, x - cx);
        const ld = nR + 22;
        const lx = x + Math.cos(la) * ld;
        const ly = y + Math.sin(la) * ld;

        ctx.textAlign    = 'center';
        ctx.textBaseline = 'middle';
        ctx.font         = 'bold 8px "JetBrains Mono", monospace';
        ctx.fillStyle    = 'rgb(var(--c-primary) / 0.88)';
        ctx.fillText(agents[i].name, lx, ly);
        ctx.font      = '7.5px "JetBrains Mono", monospace';
        ctx.fillStyle = 'rgb(var(--c-primary) / 0.36)';
        ctx.fillText(agents[i].sub, lx, ly + 12);
      }

      raf = requestAnimationFrame(draw);
    }

    raf = requestAnimationFrame(now => { lt = now; draw(now); });
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  }, []);

  return (
    <canvas ref={ref} style={{ width: '100%', height: '100%', display: 'block' }} />
  );
}
