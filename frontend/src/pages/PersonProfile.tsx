import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from "recharts";
import {
  ArrowLeft, ShieldAlert, Layers, Users, MapPin, Clock,
  ListChecks, GitBranch, ChevronDown, Fingerprint, Activity, FileText, Lock,
} from "lucide-react";
import { api, Associate, CrimeRow } from "../lib/api";
import Panel from "../components/Panel";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";
import Avatar from "../components/Avatar";
import EmptyState from "../components/EmptyState";
import { Skeleton, TableSkeleton } from "../components/Skeleton";
import DonutChart from "../components/charts/DonutChart";
import ForceGraph from "../components/network/ForceGraph";
import {
  CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle, cursorFill,
  HEAD_COLORS, PALETTE,
} from "../components/charts/theme";

const THREAT_VARIANT: Record<string, any> = { Low: "success", Medium: "warning", High: "danger" };
const THREAT_RING: Record<string, string> = { Low: "#10b981", Medium: "#f59e0b", High: "#ef4444" };

function gravityVariant(g: string): any {
  return g === "Heinous" ? "danger" : "info";
}
function statusVariant(s: string): any {
  if (s === "Charge Sheeted" || s === "Convicted") return "success";
  if (s === "Under Investigation") return "warning";
  if (s === "Closed - Undetected") return "danger";
  return "neutral";
}
function fmtDate(dt: string): string {
  if (!dt) return "—";
  const d = new Date(dt.replace(" ", "T"));
  return isNaN(+d) ? dt.slice(0, 10) : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
function fmtMonthYear(dt: string | null): string {
  if (!dt) return "—";
  const d = new Date(dt.replace(" ", "T"));
  return isNaN(+d) ? dt.slice(0, 7) : d.toLocaleDateString("en-GB", { month: "short", year: "numeric" });
}

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

function CrimeMap({ crimes }: { crimes: CrimeRow[] }) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const pts = useMemo(() => crimes.filter((c) => c.lat != null && c.lon != null), [crimes]);

  useEffect(() => {
    if (!el.current || mapRef.current || pts.length === 0) return;
    const map = new maplibregl.Map({ container: el.current, style: OSM_STYLE, center: [pts[0].lon!, pts[0].lat!], zoom: 6 });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    map.on("load", () => {
      map.addSource("crimes", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: pts.map((c) => ({
            type: "Feature",
            geometry: { type: "Point", coordinates: [c.lon!, c.lat!] },
            properties: { gravity: c.gravity, crime: c.sub_head },
          })),
        },
      });
      map.addLayer({
        id: "pts",
        type: "circle",
        source: "crimes",
        paint: {
          "circle-radius": 6,
          "circle-color": ["match", ["get", "gravity"], "Heinous", "#ef4444", "Non-Heinous", "#38bdf8", "#5b7fff"],
          "circle-opacity": 0.85,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#0a0e17",
        },
      });
      const b = new maplibregl.LngLatBounds();
      pts.forEach((c) => b.extend([c.lon!, c.lat!]));
      map.fitBounds(b, { padding: 48, maxZoom: 9, duration: 0 });
    });
    return () => { map.remove(); mapRef.current = null; };
  }, [pts]);

  if (pts.length === 0) return <EmptyState icon={MapPin} title="No geocoded cases" hint="This person's FIRs have no mapped coordinates." />;
  return <div ref={el} className="h-[420px] w-full overflow-hidden rounded-b-2xl" />;
}

function AssociateRow({ rootId, a }: { rootId: string; a: Associate }) {
  const [open, setOpen] = useState(false);
  const rel = useQuery({ queryKey: ["rel", rootId, a.person_id], queryFn: () => api.relationship(rootId, a.person_id), enabled: open });
  return (
    <li className="rounded-lg border border-line/70 bg-bg/30">
      <div className="flex items-center gap-3 px-3 py-2">
        <Avatar id={a.person_id} gender={a.gender} name={a.name} size={34} />
        <Link to={`/person/${a.person_id}`} className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-white/90 hover:text-accent-soft">{a.name}</span>
          <span className="block text-[11px] text-muted">mostly {a.top_shared_crime || "—"}</span>
        </Link>
        <Badge variant="accent">{a.shared} shared</Badge>
        <button onClick={() => setOpen((v) => !v)} className="grid h-7 w-7 place-items-center rounded-md text-muted transition-colors hover:bg-white/5 hover:text-white" aria-label="Toggle shared cases">
          <ChevronDown size={15} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      {open && (
        <div className="border-t border-line/70 px-3 py-2">
          {rel.isPending ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <ul className="space-y-1.5">
              {(rel.data?.shared ?? []).map((s) => (
                <li key={s.id} className="flex items-center gap-2 text-xs">
                  <Badge variant={gravityVariant(s.gravity)}>{s.gravity}</Badge>
                  <span className="tabular text-muted">{s.crime_no}</span>
                  <span className="text-white/80">{s.sub_head}</span>
                  <span className="text-muted">· {s.district}</span>
                  <span className="tabular ml-auto text-muted">{fmtDate(s.datetime)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </li>
  );
}

export default function PersonProfile() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const profile = useQuery({ queryKey: ["person", id], queryFn: () => api.person(id), enabled: !!id });
  const ego = useQuery({ queryKey: ["ego", id], queryFn: () => api.ego(id), enabled: !!id });

  const [showAll, setShowAll] = useState(false);

  if (profile.isError) {
    return (
      <div className="space-y-6">
        <BackLink />
        <EmptyState icon={Fingerprint} title="Person not found" hint={`No record for ${id}.`} />
      </div>
    );
  }

  const p = profile.data;
  const crimes = p?.crimes ?? [];
  const visibleCrimes = showAll ? crimes : crimes.slice(0, 10);

  return (
    <div className="space-y-6">
      <BackLink />

      {/* Identity card */}
      {profile.isPending || !p ? (
        <Skeleton className="h-40 w-full rounded-2xl" />
      ) : (
        <section className="animate-fade-in-up rounded-2xl border border-line bg-surface/80 p-6 shadow-card">
          <div className="flex flex-wrap items-center gap-5">
            <Avatar id={p.person.id} gender={p.person.gender} name={p.person.name} size={88} ring={THREAT_RING[p.threat.level]} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-bold tracking-tight text-white">{p.person.name}</h1>
                <Badge variant={THREAT_VARIANT[p.threat.level]} dot>{p.threat.level} threat · {p.threat.score}</Badge>
              </div>
              <div className="tabular mt-1 text-sm text-muted">
                {p.person.id} · identity resolved across {p.stats.total_cases} FIR{p.stats.total_cases === 1 ? "" : "s"}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Chip icon={Users}>{p.person.gender === "F" ? "Female" : p.person.gender === "T" ? "Transgender" : "Male"} · {p.person.age ?? "?"} yrs</Chip>
                <Chip icon={MapPin}>
                  {p.person.districts.slice(0, 3).join(", ")}
                  {p.person.districts.length > 3 ? ` +${p.person.districts.length - 3}` : ""}
                </Chip>
                <Chip icon={Clock}>{fmtMonthYear(p.stats.first_seen)} → {fmtMonthYear(p.stats.last_seen)}</Chip>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label="Linked FIRs" value={p ? String(p.stats.total_cases) : "—"} icon={Layers} accent="danger" caption={p?.stats.top_crime ? `Mostly ${p.stats.top_crime}` : undefined} />
        <StatCard label="Heinous cases" value={p ? String(p.stats.heinous_cases) : "—"} icon={ShieldAlert} accent="warning" caption={p ? `of ${p.stats.total_cases} total` : undefined} />
        <StatCard label="Co-accused" value={p ? String(p.stats.co_accused) : "—"} icon={Users} accent="info" caption="Linked associates" />
        <StatCard label="Arrests" value={p ? String(p.stats.arrests + p.stats.surrenders) : "—"} icon={Lock} accent="success" caption={p ? `${p.stats.surrenders} surrendered · ${p.stats.chargesheet_rate}% chargesheeted` : undefined} />
      </div>

      {/* Timeline */}
      <Panel icon={Activity} title="Activity timeline" subtitle="Monthly FIR involvement">
        <div style={{ height: 220 }}>
          {profile.isPending ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={p?.timeline ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                <defs>
                  <linearGradient id="pTl" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART.accentSoft} stopOpacity={0.45} />
                    <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="month" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} minTickGap={20} />
                <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={32} allowDecimals={false} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                <Area type="monotone" dataKey="count" stroke={CHART.accentSoft} strokeWidth={2} fill="url(#pTl)" dot={false} activeDot={{ r: 4, fill: CHART.accentSoft, stroke: "#0a0e17", strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {/* Crime mix + sections */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel icon={ListChecks} title="Crime sub-heads">
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <DonutChart data={p.crime_mix.by_type.map((x) => ({ name: x.name, value: x.count }))} colors={(_, i) => PALETTE[i % PALETTE.length]} height={200} />
          )}
        </Panel>
        <Panel icon={ShieldAlert} title="Crime heads">
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <DonutChart data={p.crime_mix.by_head.map((x) => ({ name: x.name, value: x.count }))} colors={(n) => HEAD_COLORS[n] ?? CHART.accent} height={200} />
          )}
        </Panel>
        <Panel icon={FileText} title="Sections invoked" subtitle="Across all linked FIRs">
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <div className="flex flex-wrap gap-2">
              {p.top_sections.length ? p.top_sections.map((m) => (
                <span key={m.name} className="rounded-full border border-line bg-surface-2/60 px-3 py-1 text-xs text-white/80">
                  {m.name} <span className="tabular text-muted">×{m.count}</span>
                </span>
              )) : <span className="text-sm text-muted">No sections recorded.</span>}
            </div>
          )}
        </Panel>
      </div>

      {/* Arrest history */}
      <Panel icon={Lock} title="Arrest & surrender history" subtitle="From the ArrestSurrender table">
        {profile.isPending ? (
          <TableSkeleton rows={3} />
        ) : p && p.arrest_history.length ? (
          <ul className="space-y-2">
            {p.arrest_history.map((a, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2.5 rounded-xl border border-line bg-bg/30 px-4 py-2.5 text-sm">
                <Badge variant={a.type === "Surrender" ? "info" : "warning"}>{a.type}</Badge>
                <span className="tabular text-white/85">{fmtDate(a.date)}</span>
                <span className="text-muted">· {a.sub_head}</span>
                <span className="tabular text-muted">{a.crime_no}</span>
                <span className="ml-auto text-xs text-white/70">
                  {a.district}{a.state && a.state !== "Karnataka" ? `, ${a.state} (out-of-state)` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={Lock} title="No arrests recorded" hint="No arrest or surrender events are linked to this person." />
        )}
      </Panel>

      {/* Crime map */}
      <Panel icon={MapPin} title="Crime map" subtitle="Case locations — red = heinous" bodyClassName="p-0">
        {profile.isPending ? <Skeleton className="h-[420px] w-full" /> : <CrimeMap crimes={crimes} />}
      </Panel>

      {/* Crime history table */}
      <Panel
        icon={ListChecks}
        title="Case history"
        subtitle={p ? `${crimes.length} linked FIRs` : undefined}
        actions={crimes.length > 10 ? (
          <button onClick={() => setShowAll((v) => !v)} className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition-colors hover:border-line-strong hover:text-white">
            {showAll ? "Show top 10" : `Show all ${crimes.length}`}
          </button>
        ) : undefined}
      >
        {profile.isPending ? (
          <TableSkeleton rows={8} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                  <th className="py-2.5 pr-4">Crime No</th>
                  <th className="py-2.5 pr-4">Sub-head</th>
                  <th className="py-2.5 pr-4">Sections</th>
                  <th className="py-2.5 pr-4">Gravity</th>
                  <th className="py-2.5 pr-4">District</th>
                  <th className="py-2.5 pr-4">Date</th>
                  <th className="py-2.5">Status</th>
                </tr>
              </thead>
              <tbody>
                {visibleCrimes.map((c) => (
                  <tr key={c.id} className="border-b border-line/60 transition-colors hover:bg-white/[0.025]">
                    <td className="tabular py-2.5 pr-4 text-muted">{c.crime_no}</td>
                    <td className="py-2.5 pr-4 font-medium text-white/90">{c.sub_head}</td>
                    <td className="tabular py-2.5 pr-4 text-white/60">{c.sections.join(", ")}</td>
                    <td className="py-2.5 pr-4"><Badge variant={gravityVariant(c.gravity)}>{c.gravity}</Badge></td>
                    <td className="py-2.5 pr-4 text-white/70">{c.district}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{fmtDate(c.datetime)}</td>
                    <td className="py-2.5"><Badge variant={statusVariant(c.status)}>{c.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Associations + mini graph */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Users} title="Known associates" subtitle={p ? `${p.associates.length} co-accused · expand for shared cases` : undefined}>
          {profile.isPending ? (
            <TableSkeleton rows={6} />
          ) : p && p.associates.length ? (
            <ul className="max-h-[440px] space-y-2 overflow-auto pr-1">
              {p.associates.map((a) => <AssociateRow key={a.person_id} rootId={id} a={a} />)}
            </ul>
          ) : (
            <EmptyState icon={Users} title="No known associates" hint="This person has no recorded co-accused links." />
          )}
        </Panel>

        <Panel icon={GitBranch} title="Association graph" bodyClassName="p-0">
          {ego.isPending ? (
            <Skeleton className="h-[440px] w-full" />
          ) : ego.data && ego.data.nodes.length > 1 ? (
            <ForceGraph nodes={ego.data.nodes} edges={ego.data.edges} height={440} nodeScale={0.78} onNodeClick={(pid) => pid !== id && navigate(`/person/${pid}`)} />
          ) : (
            <EmptyState icon={GitBranch} title="No network" hint="No co-accused links to graph." />
          )}
        </Panel>
      </div>
    </div>
  );
}

function BackLink() {
  return (
    <Link to="/network" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-white">
      <ArrowLeft size={15} /> Back to network
    </Link>
  );
}

function Chip({ icon: Icon, children }: { icon: any; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface-2/50 px-2.5 py-1 text-xs text-white/80">
      <Icon size={13} className="text-muted" /> {children}
    </span>
  );
}
