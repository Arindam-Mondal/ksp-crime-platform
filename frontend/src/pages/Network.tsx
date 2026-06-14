import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import {
  Share2,
  Search,
  Users,
  GitBranch,
  Maximize2,
  Plus,
  Minus,
  RefreshCw,
} from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";
import { ListSkeleton } from "../components/Skeleton";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

// Linear interpolate between two #rrggbb colors (for weight-graded edges).
function lerpHex(a: string, b: string, t: number): string {
  const pa = [1, 3, 5].map((i) => parseInt(a.slice(i, i + 2), 16));
  const pb = [1, 3, 5].map((i) => parseInt(b.slice(i, i + 2), 16));
  const mix = pa.map((v, i) => Math.round(v + (pb[i] - v) * t));
  return "#" + mix.map((v) => v.toString(16).padStart(2, "0")).join("");
}

const EDGE_LO = "#28344f";
const EDGE_HI = "#5b7fff";

function makeLayout(): cytoscape.LayoutOptions {
  // Tuned force layout: label-aware spacing + enough repulsion to avoid clumping.
  return {
    name: "cose",
    animate: true,
    animationDuration: 550,
    nodeDimensionsIncludeLabels: true,
    padding: 36,
    randomize: true,
    componentSpacing: 110,
    nodeRepulsion: () => 12000,
    idealEdgeLength: () => 95,
    edgeElasticity: () => 120,
    gravity: 0.35,
    numIter: 1400,
    fit: true,
  } as cytoscape.LayoutOptions;
}

export default function Network() {
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const offenders = useQuery({ queryKey: ["topOffenders"], queryFn: api.topOffenders });
  const ego = useQuery({
    queryKey: ["ego", selected],
    queryFn: () => api.ego(selected!),
    enabled: !!selected,
  });

  const graphEl = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  const items = offenders.data?.items ?? [];
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? items.filter((o) => o.name.toLowerCase().includes(q)) : items;
  }, [items, filter]);

  const selectedName = items.find((o) => o.person_id === selected)?.name;

  const stats = useMemo(() => {
    if (!ego.data) return null;
    const associates = Math.max(0, ego.data.nodes.length - 1);
    const links = ego.data.edges.length;
    const strongest = ego.data.edges.reduce((m, e) => Math.max(m, e.weight), 0);
    return { associates, links, strongest };
  }, [ego.data]);

  useEffect(() => {
    if (!graphEl.current || !ego.data) return;
    const root = ego.data.root;

    // Degree drives node size + which labels show (de-clutters leaf nodes).
    const degree = new Map<string, number>();
    ego.data.edges.forEach((e) => {
      degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
      degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    });
    const maxDeg = Math.max(1, ...degree.values());
    const maxW = Math.max(1, ...ego.data.edges.map((e) => e.weight));

    const nodes = ego.data.nodes.map((n) => {
      const isRoot = n.id === root;
      const deg = degree.get(n.id) ?? 0;
      const size = isRoot ? 56 : 22 + Math.round((deg / maxDeg) * 26);
      return {
        data: {
          id: n.id,
          label: n.name,
          size,
          isRoot: isRoot ? 1 : 0,
          showLabel: isRoot || deg >= Math.max(2, maxDeg * 0.5) ? 1 : 0,
        },
      };
    });
    const edges = ego.data.edges.map((e) => {
      const t = e.weight / maxW;
      return {
        data: {
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          weight: e.weight,
          w: 1.2 + t * 5,
          color: lerpHex(EDGE_LO, EDGE_HI, t),
        },
      };
    });

    const stylesheet: any[] = [
      {
        selector: "node",
        style: {
          "background-color": "#5b7fff",
          "background-opacity": 0.95,
          width: "data(size)",
          height: "data(size)",
          label: "data(label)",
          color: "#cdd6ea",
          "font-size": 10,
          "font-family": "JetBrains Mono, monospace",
          "font-weight": 500,
          "text-valign": "bottom",
          "text-halign": "center",
          "text-margin-y": 5,
          "text-opacity": "data(showLabel)",
          "min-zoomed-font-size": 9,
          "text-background-color": "#0a0e17",
          "text-background-opacity": 0.72,
          "text-background-padding": 3,
          "text-background-shape": "roundrectangle",
          "text-max-width": "90px",
          "text-wrap": "ellipsis",
          "border-width": 2,
          "border-color": "#0a0e17",
          "transition-property": "opacity, border-color, background-color",
          "transition-duration": 140,
        },
      },
      {
        selector: 'node[isRoot = 1]',
        style: {
          "background-color": "#ef4444",
          "border-width": 3,
          "border-color": "#fca5a5",
          "underlay-color": "#ef4444",
          "underlay-opacity": 0.22,
          "underlay-padding": 12,
          color: "#fff",
          "font-size": 12,
          "font-weight": 700,
        },
      },
      {
        selector: "edge",
        style: {
          width: "data(w)",
          "line-color": "data(color)",
          "curve-style": "bezier",
          opacity: 0.6,
          label: "data(weight)",
          "font-size": 9,
          "font-family": "JetBrains Mono, monospace",
          color: "#b6c0d8",
          "text-opacity": 0,
          "text-background-color": "#0a0e17",
          "text-background-opacity": 0.85,
          "text-background-padding": 2,
          "transition-property": "opacity, line-color, width",
          "transition-duration": 140,
        },
      },
      { selector: ".faded", style: { opacity: 0.08, "text-opacity": 0 } },
      {
        selector: "node.focus",
        style: { "border-color": "#869bff", "text-opacity": 1, "z-index": 99 },
      },
      {
        selector: "edge.focus",
        style: { "line-color": "#5b7fff", opacity: 1, "text-opacity": 1 },
      },
    ];

    cyRef.current?.destroy();
    const cy = cytoscape({
      container: graphEl.current,
      elements: [...nodes, ...edges],
      style: stylesheet,
      layout: makeLayout(),
      minZoom: 0.25,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
    });
    cyRef.current = cy;

    // Hover to isolate a node's neighborhood.
    cy.on("mouseover", "node", (e) => {
      const nb = e.target.closedNeighborhood();
      cy.elements().addClass("faded");
      nb.removeClass("faded").addClass("focus");
    });
    cy.on("mouseout", "node", () => cy.elements().removeClass("faded focus"));

    // Click an associate to re-center the graph on them.
    cy.on("tap", "node", (e) => {
      const id = e.target.id();
      if (id !== root) setSelected(id);
    });

    return () => cy.destroy();
  }, [ego.data]);

  const fit = () => cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 36 } }, { duration: 250 });
  const zoomBy = (factor: number) => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.animate({ zoom: { level: cy.zoom() * factor, position: { x: cy.width() / 2, y: cy.height() / 2 } } }, { duration: 150 });
  };
  const relayout = () => cyRef.current?.layout(makeLayout()).run();

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
    <div className="space-y-7">
      <PageHeader
        icon={Share2}
        eyebrow="Criminological Analysis"
        title="Network & Link Analysis"
        subtitle="Co-offending associations derived from incident graph edges"
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel
          icon={Users}
          title="Repeat offenders"
          subtitle={items.length ? `${items.length} ranked by activity` : undefined}
          bodyClassName="p-3"
        >
          <div className="relative mb-3">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter offenders…"
              className="w-full rounded-lg border border-line bg-bg/60 py-2 pl-9 pr-3 text-sm text-white/90 outline-none transition-colors placeholder:text-muted focus:border-accent"
            />
          </div>

          {offenders.isPending ? (
            <ListSkeleton rows={9} />
          ) : (
            <ul className="max-h-[480px] space-y-1 overflow-auto pr-1">
              {filtered.map((o) => {
                const active = selected === o.person_id;
                return (
                  <li key={o.person_id}>
                    <button
                      onClick={() => setSelected(o.person_id)}
                      className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-all duration-150 ${
                        active ? "bg-surface-2 ring-1 ring-accent/40" : "hover:bg-white/[0.04]"
                      }`}
                    >
                      <span
                        className={`tabular grid h-8 w-8 shrink-0 place-items-center rounded-lg text-[11px] font-bold ${
                          active ? "bg-accent text-white" : "bg-bg/70 text-accent-soft ring-1 ring-line"
                        }`}
                      >
                        {initials(o.name)}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-white/90">{o.name}</span>
                        <span className="tabular block text-[11px] text-muted">{o.person_id}</span>
                      </span>
                      <Badge variant={active ? "accent" : "neutral"}>{o.incidents}</Badge>
                    </button>
                  </li>
                );
              })}
              {filtered.length === 0 && (
                <li className="px-3 py-8 text-center text-sm text-muted">No offenders match “{filter}”.</li>
              )}
            </ul>
          )}
        </Panel>

        <div className="lg:col-span-2">
          <Panel
            icon={GitBranch}
            title={selectedName ? `Association graph — ${selectedName}` : "Association graph"}
            subtitle={selected ? selected : undefined}
            bodyClassName="p-0"
            actions={
              stats && selected ? (
                <div className="hidden items-center gap-2 sm:flex">
                  <Badge variant="accent">{stats.associates} associates</Badge>
                  <Badge variant="neutral">{stats.links} links</Badge>
                  {stats.strongest > 1 && <Badge variant="info">×{stats.strongest} strongest</Badge>}
                </div>
              ) : undefined
            }
          >
            {!selected ? (
              <EmptyState
                icon={Share2}
                title="No offender selected"
                hint="Pick a repeat offender from the list to map their co-offending network and association strength."
              />
            ) : (
              <div className="relative">
                {ego.isPending && (
                  <div className="absolute inset-0 z-20 grid place-items-center bg-surface/50 backdrop-blur-sm">
                    <span className="flex items-center gap-2 text-sm text-muted">
                      <RefreshCw size={14} className="animate-spin" /> Building graph…
                    </span>
                  </div>
                )}

                <div
                  ref={graphEl}
                  className="h-[520px] w-full rounded-b-2xl"
                  style={{
                    background:
                      "radial-gradient(circle at 50% 38%, rgba(91,127,255,0.07), transparent 62%), #090d16",
                  }}
                />

                {/* Zoom / layout controls */}
                <div className="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
                  <CtrlBtn onClick={() => zoomBy(1.25)} label="Zoom in"><Plus size={15} /></CtrlBtn>
                  <CtrlBtn onClick={() => zoomBy(0.8)} label="Zoom out"><Minus size={15} /></CtrlBtn>
                  <CtrlBtn onClick={fit} label="Fit to view"><Maximize2 size={14} /></CtrlBtn>
                  <CtrlBtn onClick={relayout} label="Re-run layout"><RefreshCw size={14} /></CtrlBtn>
                </div>

                {/* Legend */}
                <div className="pointer-events-none absolute bottom-3 left-3 z-10 rounded-xl border border-line bg-surface/85 px-3.5 py-2.5 text-[11px] backdrop-blur-md">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-danger" /> Focus offender
                    </span>
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-accent" /> Associate
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-muted">
                    <span className="h-[3px] w-7 rounded-full bg-gradient-to-r from-[#28344f] to-accent" />
                    edge thickness = shared incidents
                  </div>
                </div>

                <div className="pointer-events-none absolute bottom-3 right-3 z-10 text-[11px] text-muted">
                  click a node to re-center · hover to isolate
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
