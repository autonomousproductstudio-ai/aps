// Renders an artifact's real Markdown (from GET /v1/artifacts/{id}/content) for artifacts that
// don't have a bespoke showcase component — e.g. the Launch Studio set (Brand, Legal, Funding,
// Name Availability, Compliance) plus Execution Plan / Pitch Package. Dependency-free: a small
// line renderer for headings, lists, code fences, tables, and inline bold/code. Falls back to a
// readable monospace block and never crashes the page.
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { getActiveRun } from '../lib/useBackend';
import { MermaidDiagram } from './MermaidDiagram';

// Parse a GitHub-flavored markdown pipe table into a styled HTML table (the old renderer dumped
// it as raw `|` text). Drops the `|---|` separator row; first row is the header.
function renderTable(lines: string[], key: number): React.ReactNode {
  const isSep = (r: string[]) => r.length > 0 && r.every((c) => /^:?-{2,}:?$/.test(c.replace(/\s/g, '')) || c === '');
  const rows = lines
    .map((l) => l.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim()))
    .filter((r) => r.length > 0);
  let header: string[] | null = null;
  const body: string[][] = [];
  for (const r of rows) {
    if (isSep(r)) continue;
    if (header === null) header = r;
    else body.push(r);
  }
  if (!header) return null;
  return (
    <div key={key} className="my-3 overflow-x-auto rounded-lg border border-white/[0.08]">
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr>{header.map((c, i) => (
            <th key={i} className="text-left px-3 py-2 bg-primary/10 text-primary font-semibold border-b border-white/[0.08] whitespace-nowrap">{inline(c)}</th>
          ))}</tr>
        </thead>
        <tbody>{body.map((r, ri) => (
          <tr key={ri} className={ri % 2 ? 'bg-white/[0.02]' : ''}>
            {r.map((c, ci) => <td key={ci} className="px-3 py-2 text-on-surface/70 border-b border-white/[0.04] align-top">{inline(c)}</td>)}
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function inline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g);
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**'))
      return <strong key={i} className="text-on-surface font-semibold">{p.slice(2, -2)}</strong>;
    if (p.startsWith('`') && p.endsWith('`'))
      return <code key={i} className="px-1 py-0.5 rounded bg-white/[0.06] text-primary/80 font-mono-label text-[12px]">{p.slice(1, -1)}</code>;
    const link = p.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link)
      return <a key={i} href={link[2]} target="_blank" rel="noreferrer" className="text-primary/80 underline decoration-primary/30 hover:decoration-primary">{link[1]}</a>;
    return <span key={i}>{p}</span>;
  });
}

function renderMarkdown(md: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  const lines = md.split('\n');
  let i = 0, key = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith('```')) {                     // fenced code block
      const lang = line.trim().slice(3).trim().toLowerCase();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith('```')) { buf.push(lines[i]); i++; }
      i++;
      const code = buf.join('\n');
      // a ```mermaid block → render the live diagram (flowchart / ER), not raw code.
      if (lang === 'mermaid' && code.trim()) {
        out.push(<div key={key++} className="my-3 p-4 rounded-xl bg-[#0A0C11]/60 border border-white/[0.06]"><MermaidDiagram source={code} /></div>);
      }
      // an ```svg block is our own deterministic brand artwork → render it as the actual logo.
      else if (lang === 'svg' && code.includes('<svg')) {
        out.push(<div key={key++} className="my-3 p-4 rounded-lg bg-white/[0.03] border border-white/[0.06] flex justify-center"
                      dangerouslySetInnerHTML={{ __html: code }} />);
      } else {
        out.push(<pre key={key++} className="my-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] overflow-x-auto font-mono-label text-[11px] text-on-surface/70 whitespace-pre">{code}</pre>);
      }
      continue;
    }
    const h = line.match(/^(#{1,4})\s+(.*)$/);
    if (h) {
      const lvl = h[1].length;
      const sz = lvl === 1 ? 'text-[18px]' : lvl === 2 ? 'text-[15px]' : 'text-[13px]';
      out.push(<div key={key++} className={`${sz} font-bold text-on-surface ${lvl <= 2 ? 'mt-5 mb-2' : 'mt-3 mb-1'}`}>{inline(h[2])}</div>);
      i++; continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {                          // unordered list run
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, '')); i++; }
      out.push(<ul key={key++} className="my-2 space-y-1 list-disc pl-5">{items.map((t, j) => <li key={j} className="text-[12px] text-on-surface/65 leading-relaxed">{inline(t)}</li>)}</ul>);
      continue;
    }
    if (line.includes('|') && line.trim().startsWith('|')) { // table block → real HTML table
      const buf: string[] = [];
      while (i < lines.length && lines[i].includes('|')) { buf.push(lines[i]); i++; }
      const tbl = renderTable(buf, key++);
      out.push(tbl ?? <pre key={key++} className="my-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] overflow-x-auto font-mono-label text-[11px] text-on-surface/70">{buf.join('\n')}</pre>);
      continue;
    }
    if (line.trim() === '') { i++; continue; }
    out.push(<p key={key++} className="my-2 text-[12.5px] text-on-surface/70 leading-relaxed">{inline(line)}</p>);
    i++;
  }
  return out;
}

// `fallback` lets a caller supply a rich showcase (the page's bespoke mock) to render while
// loading or when the backend has no content for this run — so the design always shows something
// and hydrates to the real per-run markdown the moment it arrives.
export function MarkdownArtifact(
  { artifactId, run, fallback }: { artifactId: string; run?: string; fallback?: React.ReactNode },
) {
  const [md, setMd] = useState<string>('');
  const [state, setState] = useState<'loading' | 'ok' | 'empty'>('loading');
  useEffect(() => {
    let alive = true;
    const activeRun = run || getActiveRun();
    if (!activeRun) { setState('empty'); return; }
    setState('loading');
    api.artifactContent(artifactId, activeRun)
      .then((d: any) => { if (!alive) return; if (d?.body && d.body.trim()) { setMd(d.body); setState('ok'); } else setState('empty'); })
      .catch(() => { if (alive) setState('empty'); });
    return () => { alive = false; };
  }, [artifactId, run]);

  if (state === 'ok')
    return <div className="max-w-3xl">{renderMarkdown(md)}</div>;
  // Not loaded (loading or empty): prefer the caller's showcase fallback when given.
  if (fallback !== undefined)
    return <>{fallback}</>;
  if (state === 'loading')
    return <div className="text-center py-12 text-on-surface-variant/30 font-mono-label text-[12px]">Loading artifact…</div>;
  return <div className="text-center py-12 text-on-surface-variant/30 font-mono-label text-[12px]">No content generated yet for this artifact.</div>;
}
