// Renders a mermaid source string into an SVG, themed to match the dark mission-control UI.
// Used by the Artifacts page to show the live Architecture diagram (TRD → flowchart + ER),
// fetched from /v1/artifacts/trd/content?format=mermaid. Falls back gracefully on parse errors.
import { useEffect, useRef, useState } from 'react';

let _initialized = false;

async function getMermaid() {
  const mod = await import('mermaid');
  const mermaid = mod.default;
  if (!_initialized) {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'dark',
      securityLevel: 'loose',
      fontFamily: 'JetBrains Mono, monospace',
      // NOTE: every value must be a concrete color mermaid can parse — a CSS var like
      // `rgb(var(--c-bg-deep))` throws during render and the diagram falls back to raw code.
      themeVariables: {
        background: '#0D0F14',
        primaryColor: '#0F1320',
        primaryBorderColor: '#5fbfe0',
        primaryTextColor: '#cfe9f5',
        lineColor: '#6fb9d8',
        secondaryColor: '#10151f',
        tertiaryColor: '#0c1018',
      },
    });
    _initialized = true;
  }
  return mermaid;
}

let _seq = 0;

// Mermaid's render() mutates global parser state and is NOT safe to call concurrently — when a
// page mounts several diagrams at once (e.g. the TRD flowchart + ER), parallel renders make one
// throw and fall back to raw source. Serialize every render through a single promise chain.
let _renderChain: Promise<unknown> = Promise.resolve();
export function renderMermaidQueued(source: string): Promise<string> {
  const job = _renderChain.then(async () => {
    const mermaid = await getMermaid();
    const { svg } = await mermaid.render(`mmd-${_seq++}`, source.trim());
    return svg;
  });
  _renderChain = job.catch(() => {});   // keep the chain alive even if one diagram fails
  return job;
}

/** Extract the inner graph bodies from a markdown blob that contains ```mermaid fenced blocks,
 *  or pass through a raw mermaid string unchanged. */
export function extractMermaidBlocks(src: string): string[] {
  if (!src) return [];
  const blocks: string[] = [];
  const re = /```mermaid\s*([\s\S]*?)```/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) blocks.push(m[1].trim());
  return blocks.length ? blocks : [src.trim()];
}

export function MermaidDiagram({ source }: { source: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    if (!source) return;
    (async () => {
      try {
        const svg = await renderMermaidQueued(source);
        if (alive && ref.current) { ref.current.innerHTML = svg; setError(null); }
      } catch (e: any) {
        if (alive) setError(String(e?.message ?? e));
      }
    })();
    return () => { alive = false; };
  }, [source]);

  if (error) {
    return (
      <pre className="text-[11px] text-on-surface-variant/50 bg-white/[0.02] border border-white/[0.06] rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
        {source}
      </pre>
    );
  }
  return <div ref={ref} className="mermaid-host w-full overflow-x-auto flex justify-center" />;
}
