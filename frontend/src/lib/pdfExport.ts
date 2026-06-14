// Beautiful, print-ready PDF export for a run's artifacts.
//
// The backend renders each artifact as Markdown (pure/deterministic). The browser is the best
// renderer we have — it already ships the mermaid library and handles fonts, vector SVG and
// clickable links perfectly — so we turn that Markdown into a branded, styled HTML document,
// render any mermaid diagrams (the TRD architecture flowchart + ER) to inline SVG, add a cover
// page with per-document context, and open the print dialog → a real, gorgeous PDF (not a raw
// .md dump). No backend PDF dependency required.
import { api } from './api';

// One-line "what is this document" blurb per artifact, shown on the cover.
const DOC_BLURB: Record<string, string> = {
  research: 'Market research, competitors & evidence',
  'research-brief': 'Market research, competitors & evidence',
  'market-analysis': 'Market sizing & demand analysis',
  prd: 'Product requirements — personas, features & MVP scope',
  trd: 'Technical architecture, data model & API design',
  'technical-design': 'Technical architecture, data model & API design',
  architecture: 'System architecture & data model',
  execution: 'Build plan — repo, backlog, sprints & roadmap',
  'execution-plan': 'Build plan — repo, backlog, sprints & roadmap',
  pitch: 'Pitch outline, demo script & investor memo',
  'pitch-package': 'Pitch outline, demo script & investor memo',
  brand: 'Brand identity, positioning & launch plan',
  legal: 'Legal document templates',
  funding: 'Funding pack — deck, financials & roadmap',
  availability: 'Domain & trademark availability',
  compliance: 'Regulatory compliance checklist',
};

function blurbFor(id: string): string {
  const key = id.toLowerCase();
  return DOC_BLURB[key] ?? Object.entries(DOC_BLURB).find(([k]) => key.includes(k))?.[1] ?? 'Generated document';
}

async function md2html(md: string): Promise<string> {
  const { marked } = await import('marked');
  marked.setOptions({ gfm: true, breaks: false });
  return marked.parse(md) as string;
}

// Render mermaid source → inline SVG string, themed light for paper.
async function renderMermaid(code: string, idx: number): Promise<string> {
  try {
    const mermaid = (await import('mermaid')).default;
    mermaid.initialize({
      startOnLoad: false, theme: 'neutral', securityLevel: 'loose',
      fontFamily: 'Inter, system-ui, sans-serif',
      flowchart: { useMaxWidth: true, htmlLabels: true },
    });
    const { svg } = await mermaid.render(`pdf-mmd-${Date.now()}-${idx}`, code.trim());
    return svg;
  } catch {
    return '<div class="diagram-fallback">Diagram could not be rendered.</div>';
  }
}

// Replace ```mermaid fences with rendered diagrams and ```svg fences (brand artwork) with the
// actual inline SVG, so the PDF shows visuals — not raw code blocks. Return body HTML.
async function buildBodyHtml(md: string): Promise<string> {
  const codes: string[] = [];
  const svgs: string[] = [];
  let tokenized = md.replace(/```mermaid\s*([\s\S]*?)```/g, (_m, code) => {
    codes.push(code);
    return `\n\n@@APSDIAGRAM_${codes.length - 1}@@\n\n`;
  });
  tokenized = tokenized.replace(/```svg\s*([\s\S]*?)```/g, (_m, svg) => {
    svgs.push(svg);
    return `\n\n@@APSSVG_${svgs.length - 1}@@\n\n`;
  });
  let html = await md2html(tokenized);
  for (let i = 0; i < codes.length; i++) {
    const svg = await renderMermaid(codes[i], i);
    const card = `<figure class="diagram">${svg}</figure>`;
    // marked wraps the lone token in <p>…</p>; replace either form.
    html = html.replace(`<p>@@APSDIAGRAM_${i}@@</p>`, card).replace(`@@APSDIAGRAM_${i}@@`, card);
  }
  for (let i = 0; i < svgs.length; i++) {
    const fig = `<figure class="brandart">${svgs[i]}</figure>`;
    html = html.replace(`<p>@@APSSVG_${i}@@</p>`, fig).replace(`@@APSSVG_${i}@@`, fig);
  }
  return html;
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
}

function docShell(opts: { title: string; blurb: string; idea: string; runId: string; body: string }): string {
  const date = new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(opts.title)} · APS</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
<style>
  :root{ --ink:#0f1722; --muted:#5b6675; --line:#e4e7ec; --accent:#0e7490; --accent2:#0891b2; --soft:#f6f9fb; }
  *{ box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  html,body{ margin:0; padding:0; color:var(--ink); font-family:'Inter',system-ui,sans-serif; font-size:13px; line-height:1.65; }
  a{ color:var(--accent); text-decoration:none; border-bottom:1px solid #0e749033; }
  /* ---- cover ---- */
  .cover{ position:relative; padding:64px 56px 40px; background:linear-gradient(135deg,#0b3b46 0%,#0e7490 55%,#0891b2 100%); color:#fff; overflow:hidden; }
  .cover::after{ content:''; position:absolute; inset:0; background:radial-gradient(ellipse at 85% 10%, rgba(255,255,255,.18), transparent 60%); }
  .cover .brand{ position:relative; font-family:'Space Grotesk',sans-serif; font-weight:700; letter-spacing:.32em; font-size:12px; text-transform:uppercase; opacity:.9; }
  .cover h1{ position:relative; font-family:'Space Grotesk',sans-serif; font-size:38px; line-height:1.1; margin:14px 0 6px; font-weight:700; }
  .cover .blurb{ position:relative; font-size:15px; opacity:.92; max-width:560px; }
  .cover .idea{ position:relative; margin-top:22px; font-size:13px; opacity:.85; }
  .cover .idea b{ font-weight:600; }
  .cover .meta{ position:relative; margin-top:26px; display:flex; gap:22px; font-size:11px; letter-spacing:.05em; text-transform:uppercase; opacity:.85; font-family:'JetBrains Mono',monospace; }
  .accentbar{ height:5px; background:linear-gradient(90deg,#0891b2,#22d3ee,#0891b2); }
  /* ---- body ---- */
  .doc{ padding:40px 56px 64px; max-width:860px; margin:0 auto; }
  .doc h1{ font-family:'Space Grotesk',sans-serif; font-size:24px; margin:34px 0 10px; color:#0b2530; border-bottom:2px solid var(--line); padding-bottom:6px; }
  .doc h2{ font-family:'Space Grotesk',sans-serif; font-size:18px; margin:26px 0 8px; color:var(--accent); }
  .doc h3{ font-size:14.5px; margin:20px 0 6px; color:#16323d; font-weight:700; }
  .doc p{ margin:8px 0; }
  .doc ul,.doc ol{ margin:8px 0 8px 4px; padding-left:20px; }
  .doc li{ margin:3px 0; }
  .doc strong{ color:#0b2530; }
  .doc blockquote{ margin:12px 0; padding:8px 16px; border-left:3px solid var(--accent2); background:var(--soft); color:var(--muted); border-radius:0 6px 6px 0; }
  .doc code{ font-family:'JetBrains Mono',monospace; font-size:.86em; background:#eef3f6; padding:1px 5px; border-radius:4px; color:#0b4a58; }
  .doc pre{ background:#0f1722; color:#d6e6ee; padding:14px 16px; border-radius:8px; overflow:auto; font-size:11.5px; line-height:1.5; }
  .doc pre code{ background:none; color:inherit; padding:0; }
  .doc table{ width:100%; border-collapse:collapse; margin:14px 0; font-size:12px; box-shadow:0 0 0 1px var(--line); border-radius:8px; overflow:hidden; }
  .doc th{ background:#0e7490; color:#fff; text-align:left; padding:8px 11px; font-weight:600; font-size:11px; letter-spacing:.02em; }
  .doc td{ padding:7px 11px; border-top:1px solid var(--line); vertical-align:top; }
  .doc tr:nth-child(even) td{ background:var(--soft); }
  .diagram{ margin:18px 0; padding:18px; border:1px solid var(--line); border-radius:10px; background:#fcfeff; text-align:center; page-break-inside:avoid; }
  .diagram svg{ max-width:100%; height:auto; }
  .brandart{ margin:16px 0; padding:18px; border:1px solid var(--line); border-radius:10px; background:#fff; text-align:center; page-break-inside:avoid; }
  .brandart svg{ max-width:100%; height:auto; }
  .diagram-fallback{ color:var(--muted); font-style:italic; }
  .doc hr{ border:none; border-top:1px solid var(--line); margin:22px 0; }
  .footer{ margin-top:40px; padding-top:14px; border-top:1px solid var(--line); color:var(--muted); font-size:10.5px; font-family:'JetBrains Mono',monospace; text-align:center; }
  /* keep blocks intact across pages */
  h1,h2,h3{ page-break-after:avoid; } table,.diagram,pre,blockquote{ page-break-inside:avoid; }
  @page{ margin:14mm; }
  @media print{ .cover{ padding:56px 48px 36px; } .doc{ padding:28px 40px; } }
</style></head>
<body>
  <section class="cover">
    <div class="brand">◇ Autonomous Product Studio</div>
    <h1>${escapeHtml(opts.title)}</h1>
    <div class="blurb">${escapeHtml(opts.blurb)}</div>
    <div class="idea"><b>Venture:</b> ${escapeHtml(opts.idea || '—')}</div>
    <div class="meta"><span>Run ${escapeHtml(opts.runId)}</span><span>${date}</span></div>
  </section>
  <div class="accentbar"></div>
  <main class="doc">
    ${opts.body}
    <div class="footer">Generated by Autonomous Product Studio · ${escapeHtml(opts.runId)} · ${date}</div>
  </main>
  <script>
    // Wait for fonts + diagrams to settle, then open the print dialog → "Save as PDF".
    function go(){ window.focus(); window.print(); }
    if (document.fonts && document.fonts.ready) { document.fonts.ready.then(()=>setTimeout(go,350)); }
    else { window.addEventListener('load', ()=>setTimeout(go,500)); }
  </script>
</body></html>`;
}

/** Export one artifact as a styled, print-ready PDF (opens the browser print dialog). */
export async function exportArtifactPDF(opts: {
  artifactId: string; artifactName: string; runId: string; idea?: string;
}): Promise<void> {
  // 1) main markdown
  let md = '';
  try { md = (await api.artifactContent(opts.artifactId, opts.runId))?.body ?? ''; } catch { /* */ }
  // 2) architecture diagrams (TRD only; 404 elsewhere → skip) — append so they render in the PDF
  try {
    const mmd = await api.artifactMermaid(opts.artifactId, opts.runId);
    const body = (mmd && (mmd.body ?? mmd)) as string;
    if (body && /```mermaid|flowchart|erDiagram/.test(body)) {
      const block = /```mermaid/.test(body) ? body : '```mermaid\n' + body.trim() + '\n```';
      md += `\n\n## Architecture Diagrams\n\n${block}\n`;
    }
  } catch { /* no diagram for this artifact */ }

  if (!md.trim()) md = `_No content was generated for **${opts.artifactName}**._`;

  // Cover context: use the venture idea (fetch the run's label if the caller didn't pass it).
  let idea = opts.idea ?? '';
  if (!idea) { try { const r: any = await api.run(opts.runId); idea = r?.label ?? r?.idea ?? ''; } catch { /* */ } }

  const bodyHtml = await buildBodyHtml(md);
  const html = docShell({
    title: opts.artifactName, blurb: blurbFor(opts.artifactId),
    idea, runId: opts.runId, body: bodyHtml,
  });

  const win = window.open('', '_blank');
  if (!win) throw new Error('Popup blocked — allow popups to export the PDF.');
  win.document.open();
  win.document.write(html);
  win.document.close();
}
