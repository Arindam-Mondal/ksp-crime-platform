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
  Radar, MoveRight,
} from "lucide-react";
import { api, Associate, CrimeRow, MoMatch } from "../lib/api";
import Panel from "../components/Panel";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";
import Avatar from "../components/Avatar";
import EmptyState from "../components/EmptyState";
import { Skeleton, TableSkeleton } from "../components/Skeleton";
import DonutChart from "../components/charts/DonutChart";
import ForceGraph from "../components/network/ForceGraph";
import { useResponsiveHeight } from "../lib/useResponsiveHeight";
import {
  CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle, cursorFill,
  HEAD_COLORS, PALETTE,
} from "../components/charts/theme";
import { useT, type TranslationKey } from "../i18n";
import { useDataLabel } from "../i18n/data";

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
// Dates stay `en-GB` in both languages by design: Karnataka Police records use Western
// numerals and short English month names, and `kn-IN` would render Kannada digits
// (೧೨೩), breaking both the tabular alignment and the convention officers read.
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

/** ERD gender codes -> catalog keys. */
const GENDER_KEY: Record<string, TranslationKey> = {
  F: "person.gender.female",
  T: "person.gender.transgender",
  M: "person.gender.male",
};

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

function CrimeMap({ crimes }: { crimes: CrimeRow[] }) {
  const t = useT();
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

  if (pts.length === 0)
    return <EmptyState icon={MapPin} title={t("person.noGeocoded")} hint={t("person.noGeocodedHint")} />;
  return <div ref={el} className="h-[clamp(300px,52svh,420px)] w-full overflow-hidden rounded-b-2xl" />;
}

function AssociateRow({ rootId, a }: { rootId: string; a: Associate }) {
  const [open, setOpen] = useState(false);
  const t = useT();
  const dl = useDataLabel();
  const rel = useQuery({ queryKey: ["rel", rootId, a.person_id], queryFn: () => api.relationship(rootId, a.person_id), enabled: open });
  return (
    <li className="rounded-lg border border-line/70 bg-bg/30">
      <div className="flex items-center gap-3 px-3 py-2">
        <Avatar id={a.person_id} gender={a.gender} name={a.name} size={34} />
        <Link to={`/person/${a.person_id}`} className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-white/90 hover:text-accent-soft">{a.name}</span>
          <span className="block text-[11px] text-muted">
            {t("person.mostlyCrime", {
              crime: a.top_shared_crime ? dl("crimeSubHead", a.top_shared_crime) : t("common.none"),
            })}
          </span>
        </Link>
        <Badge variant="accent">{t("person.sharedCount", { count: a.shared })}</Badge>
        <button onClick={() => setOpen((v) => !v)} className="grid h-7 w-7 place-items-center rounded-md text-muted transition-colors hover:bg-white/5 hover:text-white" aria-label={t("person.toggleShared")}>
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
                  <Badge variant={gravityVariant(s.gravity)}>{dl("gravity", s.gravity)}</Badge>
                  <span className="tabular text-muted">{s.crime_no}</span>
                  <span className="text-white/80">{dl("crimeSubHead", s.sub_head)}</span>
                  <span className="text-muted">· {dl("district", s.district)}</span>
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
  const moq = useQuery({ queryKey: ["mo", id], queryFn: () => api.mo(id), enabled: !!id });

  const [showAll, setShowAll] = useState(false);
  const graphHeight = useResponsiveHeight(440, 300, 0.5);
  const t = useT();
  const dl = useDataLabel();

  if (profile.isError) {
    return (
      <div className="space-y-6">
        <BackLink />
        <EmptyState
          icon={Fingerprint}
          title={t("person.notFound")}
          hint={t("person.notFoundHint", { id })}
        />
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
                {/* The English threat level stays the variant/ring lookup key. */}
                <Badge variant={THREAT_VARIANT[p.threat.level]} dot>
                  {t("person.threat", {
                    level: dl("severity", p.threat.level),
                    score: p.threat.score,
                  })}
                </Badge>
              </div>
              <div className="mt-1 text-sm tabular-nums text-muted">
                {t(
                  p.stats.total_cases === 1
                    ? "person.identityResolved_one"
                    : "person.identityResolved_other",
                  { id: p.person.id, count: p.stats.total_cases }
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <Chip icon={Users}>
                  {t("person.ageChip", {
                    gender: t(GENDER_KEY[p.person.gender] ?? "person.gender.male"),
                    age: p.person.age ?? t("person.ageUnknown"),
                  })}
                </Chip>
                <Chip icon={MapPin}>
                  {p.person.districts.slice(0, 3).map((n) => dl("district", n)).join(", ")}
                  {p.person.districts.length > 3 ? ` +${p.person.districts.length - 3}` : ""}
                </Chip>
                <Chip icon={Clock}>{fmtMonthYear(p.stats.first_seen)} → {fmtMonthYear(p.stats.last_seen)}</Chip>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("person.linkedFirs")}
          value={p ? String(p.stats.total_cases) : t("common.none")}
          icon={Layers}
          accent="danger"
          caption={
            p?.stats.top_crime
              ? t("person.mostly", { crime: dl("crimeSubHead", p.stats.top_crime) })
              : undefined
          }
        />
        <StatCard
          label={t("person.heinousCases")}
          value={p ? String(p.stats.heinous_cases) : t("common.none")}
          icon={ShieldAlert}
          accent="warning"
          caption={p ? t("person.ofTotal", { count: p.stats.total_cases }) : undefined}
        />
        <StatCard
          label={t("person.coAccused")}
          value={p ? String(p.stats.co_accused) : t("common.none")}
          icon={Users}
          accent="info"
          caption={t("person.linkedAssociates")}
        />
        <StatCard
          label={t("person.arrests")}
          value={p ? String(p.stats.arrests + p.stats.surrenders) : t("common.none")}
          icon={Lock}
          accent="success"
          caption={
            p
              ? t("person.arrestCaption", {
                  surrendered: p.stats.surrenders,
                  rate: p.stats.chargesheet_rate,
                })
              : undefined
          }
        />
      </div>

      {/* Timeline */}
      <Panel icon={Activity} title={t("person.timeline")} subtitle={t("person.timelineSubtitle")}>
        <div className="h-[200px] sm:h-[220px]">
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
        <Panel icon={ListChecks} title={t("person.subHeads")}>
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <DonutChart data={p.crime_mix.by_type.map((x) => ({ name: x.name, label: dl("crimeSubHead", x.name), value: x.count }))} colors={(_, i) => PALETTE[i % PALETTE.length]} height={200} />
          )}
        </Panel>
        <Panel icon={ShieldAlert} title={t("person.crimeHeads")}>
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <DonutChart data={p.crime_mix.by_head.map((x) => ({ name: x.name, label: dl("crimeHead", x.name), value: x.count }))} colors={(n) => HEAD_COLORS[n] ?? CHART.accent} height={200} />
          )}
        </Panel>
        {/* Act/Section citations ("IPC 302") stay English in both languages. */}
        <Panel icon={FileText} title={t("person.sections")} subtitle={t("person.sectionsSubtitle")}>
          {profile.isPending || !p ? <Skeleton className="h-[200px] w-full" /> : (
            <div className="flex flex-wrap gap-2">
              {p.top_sections.length ? p.top_sections.map((m) => (
                <span key={m.name} className="rounded-full border border-line bg-surface-2/60 px-3 py-1 text-xs text-white/80">
                  {m.name} <span className="tabular text-muted">×{m.count}</span>
                </span>
              )) : <span className="text-sm text-muted">{t("person.noSections")}</span>}
            </div>
          )}
        </Panel>
      </div>

      {/* Modus operandi */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          icon={Fingerprint}
          title={t("person.mo")}
          subtitle={t("person.moSubtitle")}
          actions={
            moq.data?.signature.dominant_time ? (
              <Badge variant="info">
                <Clock size={11} />{" "}
                {t("person.mostlyTime", {
                  time: dl("timeBucket", moq.data.signature.dominant_time),
                })}
              </Badge>
            ) : undefined
          }
        >
          {moq.isPending ? (
            <Skeleton className="h-56 w-full" />
          ) : moq.data ? (
            <div className="space-y-4">
              {/* top crimes with share bars */}
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {t("person.signatureCrimes")}
                </div>
                <div className="space-y-1.5">
                  {moq.data.signature.top_crimes.map((c) => (
                    <div key={c.name} className="flex items-center gap-3">
                      <span className="w-40 shrink-0 truncate text-xs text-white/85" title={dl("crimeSubHead", c.name)}>
                        {dl("crimeSubHead", c.name)}
                      </span>
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg/80">
                        <div className="h-full rounded-full bg-gradient-to-r from-accent/50 to-accent" style={{ width: `${c.share}%` }} />
                      </div>
                      <span className="tabular w-10 shrink-0 text-right text-[11px] text-muted">{c.share}%</span>
                    </div>
                  ))}
                </div>
              </div>
              {/* time-of-day profile */}
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {t("person.whenTheyStrike")}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {moq.data.signature.time_profile.map((tp) => {
                    const max = Math.max(1, ...moq.data!.signature.time_profile.map((x) => x.count));
                    const on = tp.bucket === moq.data!.signature.dominant_time;
                    return (
                      <div key={tp.bucket} className="rounded-lg border border-line bg-bg/30 px-2 py-2 text-center">
                        <div className="mx-auto flex h-12 items-end justify-center">
                          <div className={`w-4 rounded-t ${on ? "bg-accent" : "bg-surface-2"}`} style={{ height: `${Math.max(8, (tp.count / max) * 100)}%` }} />
                        </div>
                        <div className={`mt-1 text-[10px] ${on ? "text-white/85" : "text-muted"}`}>
                          {dl("timeBucket", tp.bucket)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
              {/* sections + jurisdiction spread */}
              <div className="flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-line pt-3">
                <div>
                  <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                    {t("person.legalFingerprint")}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {moq.data.signature.top_sections.length ? moq.data.signature.top_sections.map((s) => (
                      <span key={s} className="rounded-full border border-line bg-surface-2/60 px-2.5 py-1 text-[11px] text-white/80">{s}</span>
                    )) : <span className="text-xs text-muted">{t("person.noSections")}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs tabular-nums text-muted">
                  <MapPin size={13} />
                  {t(
                    moq.data.signature.jurisdictions.length === 1
                      ? "person.operatesAcross_one"
                      : "person.operatesAcross_other",
                    { count: moq.data.signature.jurisdictions.length }
                  )}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState icon={Fingerprint} title={t("person.noMo")} hint={t("person.noMoHint")} />
          )}
        </Panel>

        <Panel
          icon={Radar}
          title={t("person.sameMo")}
          subtitle={t("person.sameMoSubtitle")}
        >
          {moq.isPending ? (
            <TableSkeleton rows={5} />
          ) : moq.data && moq.data.matches.length ? (
            <ul className="max-h-[440px] space-y-2 overflow-auto pr-1">
              {moq.data.matches.map((m) => <MoMatchRow key={m.person_id} m={m} />)}
            </ul>
          ) : (
            <EmptyState icon={Radar} title={t("person.noMatches")} hint={t("person.noMatchesHint")} />
          )}
        </Panel>
      </div>

      {/* Arrest history */}
      <Panel icon={Lock} title={t("person.arrestHistory")} subtitle={t("person.arrestHistorySubtitle")}>
        {profile.isPending ? (
          <TableSkeleton rows={3} />
        ) : p && p.arrest_history.length ? (
          <ul className="space-y-2">
            {p.arrest_history.map((a, i) => (
              <li key={i} className="flex flex-wrap items-center gap-2.5 rounded-xl border border-line bg-bg/30 px-4 py-2.5 text-sm">
                {/* The English arrest type stays the variant lookup key. */}
                <Badge variant={a.type === "Surrender" ? "info" : "warning"}>
                  {dl("arrestType", a.type)}
                </Badge>
                <span className="tabular text-white/85">{fmtDate(a.date)}</span>
                <span className="text-muted">· {dl("crimeSubHead", a.sub_head)}</span>
                <span className="tabular text-muted">{a.crime_no}</span>
                <span className="ml-auto text-xs text-white/70">
                  {a.state && a.state !== "Karnataka"
                    ? t("person.outOfState", {
                        district: dl("district", a.district),
                        state: dl("state", a.state),
                      })
                    : dl("district", a.district)}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={Lock} title={t("person.noArrests")} hint={t("person.noArrestsHint")} />
        )}
      </Panel>

      {/* Crime map */}
      <Panel icon={MapPin} title={t("person.crimeMap")} subtitle={t("person.crimeMapSubtitle")} bodyClassName="p-0">
        {profile.isPending ? <Skeleton className="h-[clamp(300px,52svh,420px)] w-full" /> : <CrimeMap crimes={crimes} />}
      </Panel>

      {/* Crime history table */}
      <Panel
        icon={ListChecks}
        title={t("person.caseHistory")}
        subtitle={p ? t("person.caseHistorySubtitle", { count: crimes.length }) : undefined}
        actions={crimes.length > 10 ? (
          <button onClick={() => setShowAll((v) => !v)} className="rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition-colors hover:border-line-strong hover:text-white">
            {showAll ? t("person.showTop10") : t("person.showAll", { count: crimes.length })}
          </button>
        ) : undefined}
      >
        {profile.isPending ? (
          <TableSkeleton rows={8} />
        ) : (
          <div className="table-scroll">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                  <th className="py-2.5 pr-4">{t("person.col.crimeNo")}</th>
                  <th className="py-2.5 pr-4">{t("person.col.subHead")}</th>
                  <th className="py-2.5 pr-4">{t("person.col.sections")}</th>
                  <th className="py-2.5 pr-4">{t("person.col.gravity")}</th>
                  <th className="py-2.5 pr-4">{t("common.district")}</th>
                  <th className="py-2.5 pr-4">{t("person.col.date")}</th>
                  <th className="py-2.5">{t("person.col.status")}</th>
                </tr>
              </thead>
              <tbody>
                {visibleCrimes.map((c) => (
                  <tr key={c.id} className="border-b border-line/60 transition-colors hover:bg-white/[0.025]">
                    <td className="tabular py-2.5 pr-4 text-muted">{c.crime_no}</td>
                    <td className="py-2.5 pr-4 font-medium text-white/90">{dl("crimeSubHead", c.sub_head)}</td>
                    <td className="tabular py-2.5 pr-4 text-white/60">{c.sections.join(", ")}</td>
                    <td className="py-2.5 pr-4"><Badge variant={gravityVariant(c.gravity)}>{dl("gravity", c.gravity)}</Badge></td>
                    <td className="py-2.5 pr-4 text-white/70">{dl("district", c.district)}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{fmtDate(c.datetime)}</td>
                    {/* statusVariant() keeps reading the English status. */}
                    <td className="py-2.5"><Badge variant={statusVariant(c.status)}>{dl("caseStatus", c.status)}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Associations + mini graph */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Users} title={t("person.associates")} subtitle={p ? t("person.associatesSubtitle", { count: p.associates.length }) : undefined}>
          {profile.isPending ? (
            <TableSkeleton rows={6} />
          ) : p && p.associates.length ? (
            <ul className="max-h-[440px] space-y-2 overflow-auto pr-1">
              {p.associates.map((a) => <AssociateRow key={a.person_id} rootId={id} a={a} />)}
            </ul>
          ) : (
            <EmptyState icon={Users} title={t("person.noAssociates")} hint={t("person.noAssociatesHint")} />
          )}
        </Panel>

        <Panel icon={GitBranch} title={t("person.graph")} subtitle={ego.data && ego.data.nodes.length > 1 ? t("person.graphSubtitle") : undefined} bodyClassName="p-0">
          {ego.isPending ? (
            <Skeleton className="w-full" style={{ height: graphHeight }} />
          ) : ego.data && ego.data.nodes.length > 1 ? (
            <ForceGraph nodes={ego.data.nodes} edges={ego.data.edges} height={graphHeight} nodeScale={0.78} onNodeClick={(pid) => pid !== id && navigate(`/person/${pid}`)} />
          ) : (
            <EmptyState icon={GitBranch} title={t("person.noNetwork")} hint={t("person.noNetworkHint")} />
          )}
        </Panel>
      </div>
    </div>
  );
}

function MoMatchRow({ m }: { m: MoMatch }) {
  const pct = Math.round(m.similarity * 100);
  const t = useT();
  const dl = useDataLabel();
  const sharedCrimes = m.shared_crimes.map((c) => dl("crimeSubHead", c));
  return (
    <li className="rounded-lg border border-line/70 bg-bg/30 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <Avatar id={m.person_id} gender={m.gender} name={m.name} size={34} />
        <Link to={`/person/${m.person_id}`} className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-white/90 hover:text-accent-soft">{m.name}</span>
          <span className="block text-[11px] tabular-nums text-muted">
            {t("person.firCount", { id: m.person_id, count: m.cases })}
          </span>
        </Link>
        <div className="flex items-center gap-2">
          {m.different_jurisdiction && (
            <Badge variant="warning"><MoveRight size={11} /> {t("person.crossDistrict")}</Badge>
          )}
          {m.is_associate && <Badge variant="neutral">{t("person.knownAssociate")}</Badge>}
          <Badge variant="accent">{t("person.matchPct", { pct })}</Badge>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-3">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg/80">
          <div className="h-full rounded-full bg-gradient-to-r from-accent/50 to-accent" style={{ width: `${pct}%` }} />
        </div>
        <span className="truncate text-[11px] text-muted" title={sharedCrimes.join(", ")}>
          {t("person.shares", {
            what: sharedCrimes.slice(0, 2).join(", ") || t("person.sharesFallback"),
          })}
          {m.shared_sections ? t("person.sharesSections", { count: m.shared_sections }) : ""}
        </span>
      </div>
    </li>
  );
}

function BackLink() {
  const t = useT();
  return (
    <Link to="/network" className="inline-flex items-center gap-1.5 text-sm text-muted transition-colors hover:text-white">
      <ArrowLeft size={15} /> {t("person.back")}
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
