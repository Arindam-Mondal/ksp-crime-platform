import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Maximize2, Plus, Minus, RefreshCw } from "lucide-react";
import type { EgoNode, EgoEdge } from "../../lib/api";
import { initials, tileColor } from "../../lib/avatar";

const EDGE_LO = [40, 52, 79]; // #28344f
const EDGE_HI = [91, 127, 255]; // #5b7fff

function rgba(c: number[], a: number) {
  return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
}
function lerp(a: number[], b: number[], t: number) {
  return a.map((v, i) => Math.round(v + (b[i] - v) * t));
}
function radiusOf(n: any, scale = 1) {
  return (n.is_root ? 13 : 6 + Math.min(8, Math.sqrt(n.cases || 1) * 1.4)) * scale;
}

export default function ForceGraph({
  nodes,
  edges,
  height = 520,
  nodeScale = 1,
  onNodeClick,
}: {
  nodes: EgoNode[];
  edges: EgoEdge[];
  height?: number;
  nodeScale?: number;
  onNodeClick?: (id: string) => void;
}) {
  const fgRef = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hoverId, setHoverId] = useState<string | null>(null);

  // Fresh, mutable copies (react-force-graph mutates node/link objects in place).
  const data = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n })),
      links: edges.map((e) => ({ ...e })),
    }),
    [nodes, edges]
  );
  const maxW = useMemo(() => Math.max(1, ...edges.map((e) => e.weight)), [edges]);

  // Adjacency for hover highlighting (by id, from the raw edges).
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    edges.forEach((e) => {
      (m.get(e.source) ?? m.set(e.source, new Set()).get(e.source)!).add(e.target);
      (m.get(e.target) ?? m.set(e.target, new Set()).get(e.target)!).add(e.source);
    });
    return m;
  }, [edges]);

  const highlightNodes = useMemo(() => {
    if (!hoverId) return null;
    const s = new Set<string>([hoverId]);
    neighbors.get(hoverId)?.forEach((n) => s.add(n));
    return s;
  }, [hoverId, neighbors]);

  // Responsive width.
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width));
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Spread the layout so avatar nodes don't clump: stronger repulsion + weaker
  // ties pushed further apart than strong ones.
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fg.d3Force("charge")?.strength(-230 * nodeScale).distanceMax(420);
    const link = fg.d3Force("link");
    if (link) link.distance((l: any) => 46 + (1 - l.weight / maxW) * 46);
    fg.d3ReheatSimulation();
  }, [data, maxW, nodeScale]);

  const drawNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, scale: number) => {
      const r = radiusOf(node, nodeScale);
      const faded = highlightNodes ? !highlightNodes.has(node.id) : false;
      const focused = highlightNodes ? highlightNodes.has(node.id) : false;
      ctx.save();
      ctx.globalAlpha = faded ? 0.12 : 1;

      // initials disc (deliberately no photo — see lib/avatar.ts)
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.fillStyle = tileColor(node.id);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.font = `700 ${r * 0.85}px JetBrains Mono, monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(initials(node.name), node.x, node.y);

      // ring (red glow for the focus offender)
      if (node.is_root) {
        ctx.shadowColor = "#ef4444";
        ctx.shadowBlur = 16;
      }
      ctx.lineWidth = node.is_root ? 3 : focused ? 2.4 : 1.5;
      ctx.strokeStyle = node.is_root ? "#ef4444" : focused ? "#869bff" : "#243049";
      ctx.beginPath();
      ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.shadowBlur = 0;

      // label
      if (node.is_root || focused || scale >= 1.4) {
        const fs = 11 / scale;
        ctx.font = `500 ${fs}px Manrope, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        const label = node.name.length > 16 ? node.name.slice(0, 15) + "…" : node.name;
        const pad = 3 / scale;
        const w = ctx.measureText(label).width;
        ctx.fillStyle = "rgba(10,14,23,0.72)";
        ctx.fillRect(node.x - w / 2 - pad, node.y + r + 2 / scale, w + pad * 2, fs + pad);
        ctx.fillStyle = "#cdd6ea";
        ctx.fillText(label, node.x, node.y + r + 3 / scale);
      }
      ctx.restore();
    },
    [highlightNodes, nodeScale]
  );

  const pointerArea = useCallback((node: any, color: string, ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(node.x, node.y, radiusOf(node, nodeScale), 0, 2 * Math.PI);
    ctx.fill();
  }, [nodeScale]);

  const linkColor = useCallback(
    (link: any) => {
      const t = link.weight / maxW;
      if (hoverId) {
        const sid = typeof link.source === "object" ? link.source.id : link.source;
        const tid = typeof link.target === "object" ? link.target.id : link.target;
        const on = sid === hoverId || tid === hoverId;
        return rgba(lerp(EDGE_LO, EDGE_HI, t), on ? 0.95 : 0.05);
      }
      return rgba(lerp(EDGE_LO, EDGE_HI, t), 0.45 + 0.4 * t);
    },
    [hoverId, maxW]
  );

  const fit = () => fgRef.current?.zoomToFit(400, 50);
  const zoomBy = (f: number) => fgRef.current?.zoom(fgRef.current.zoom() * f, 250);
  const reheat = () => fgRef.current?.d3ReheatSimulation();

  const CtrlBtn = ({ onClick, label, children }: { onClick: () => void; label: string; children: React.ReactNode }) => (
    <button
      onClick={onClick}
      title={label}
      aria-label={label}
      className="grid h-8 w-8 place-items-center rounded-lg border border-line bg-surface/85 text-muted backdrop-blur-md transition-colors hover:border-line-strong hover:text-white"
    >
      {children}
    </button>
  );

  return (
    <div
      ref={wrapRef}
      className="relative w-full overflow-hidden rounded-b-2xl"
      style={{
        height,
        background: "radial-gradient(circle at 50% 38%, rgba(91,127,255,0.07), transparent 62%), #090d16",
      }}
    >
      <ForceGraph2D
        ref={fgRef}
        width={width}
        height={height}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeLabel={(n: any) => `${n.name} · ${n.cases} FIRs`}
        nodeCanvasObject={drawNode}
        nodePointerAreaPaint={pointerArea}
        linkColor={linkColor}
        linkWidth={(l: any) => 1 + (l.weight / maxW) * 4}
        linkDirectionalParticles={(l: any) => (l.weight >= 2 ? Math.min(4, l.weight) : 0)}
        linkDirectionalParticleWidth={(l: any) => 1 + (l.weight / maxW) * 2}
        linkDirectionalParticleSpeed={0.006}
        onNodeHover={(n: any) => {
          setHoverId(n ? n.id : null);
          if (wrapRef.current) wrapRef.current.style.cursor = n ? "pointer" : "default";
        }}
        onNodeClick={(n: any) => onNodeClick?.(n.id)}
        onBackgroundClick={() => setHoverId(null)}
        cooldownTicks={120}
        onEngineStop={() => fgRef.current?.zoomToFit(400, 50)}
        enableNodeDrag={true}
      />

      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
        <CtrlBtn onClick={() => zoomBy(1.25)} label="Zoom in"><Plus size={15} /></CtrlBtn>
        <CtrlBtn onClick={() => zoomBy(0.8)} label="Zoom out"><Minus size={15} /></CtrlBtn>
        <CtrlBtn onClick={fit} label="Fit to view"><Maximize2 size={14} /></CtrlBtn>
        <CtrlBtn onClick={reheat} label="Re-run layout"><RefreshCw size={14} /></CtrlBtn>
      </div>
    </div>
  );
}
