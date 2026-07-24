import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  AreaChart,
  Area,
  Legend,
} from "recharts";
import {
  Activity,
  Layers,
  Gavel,
  Wifi,
  Crosshair,
  BarChart3,
  TrendingUp,
  ListChecks,
  PieChart as PieIcon,
  Siren,
  Scale,
  Lock,
  Hourglass,
  Users,
  Filter,
  BookOpenText,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import StatCard from "../components/StatCard";
import PageHeader from "../components/PageHeader";
import AlertsFeed from "../components/AlertsFeed";
import Badge from "../components/Badge";
import { ChartSkeleton, Skeleton } from "../components/Skeleton";
import DonutChart from "../components/charts/DonutChart";
import {
  CHART,
  tooltipStyle,
  tooltipLabelStyle,
  tooltipItemStyle,
  cursorFill,
  HEAD_COLORS,
  STATUS_COLORS,
  CATEGORY_COLORS,
  GRAVITY_COLORS,
} from "../components/charts/theme";

// SVG gradient ids must be reference-safe: crime-head names contain spaces and "&",
// which break the url(#…) fill reference and make the area render black.
const gradId = (head: string) => "trend-" + head.replace(/[^a-zA-Z0-9]/g, "");

export default function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const byDistrict = useQuery({ queryKey: ["byDistrict"], queryFn: api.byDistrict });
  const bySubHead = useQuery({ queryKey: ["bySubHead"], queryFn: api.bySubHead });
  const byMonth = useQuery({ queryKey: ["byMonth"], queryFn: api.byMonth });
  const byStatus = useQuery({ queryKey: ["byStatus"], queryFn: api.byStatus });
  const byCrimeHead = useQuery({ queryKey: ["byCrimeHead"], queryFn: api.byCrimeHead });
  const byCategory = useQuery({ queryKey: ["byCategory"], queryFn: api.byCategory });
  const byGravity = useQuery({ queryKey: ["byGravity"], queryFn: api.byGravity });
  const funnel = useQuery({ queryKey: ["caseFunnel"], queryFn: api.caseFunnel });
  const topSections = useQuery({ queryKey: ["topSections"], queryFn: api.topSections });
  const spikes = useQuery({ queryKey: ["spikes"], queryFn: api.spikes });

  const s = summary.data;
  const topDistricts = (byDistrict.data?.items ?? []).slice(0, 12);
  const subHeads = (bySubHead.data?.items ?? []).slice(0, 14);
  const stages = funnel.data?.stages ?? [];
  const maxStage = stages.reduce((m, x) => Math.max(m, x.count), 1);

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Activity}
        eyebrow="Command Overview"
        title="Strategic Intelligence Hub"
        subtitle="Live operational picture over the Police FIR System — CaseMaster and linked ERD tables"
      />

      {/* Emerging-trend spike alerts */}
      <Panel
        icon={Siren}
        title="Active spike alerts"
        subtitle="Crime sub-heads surging above their historical baseline"
        actions={
          spikes.data ? (
            <Link to="/hotspots">
              <Badge variant={spikes.data.count ? "danger" : "success"} dot>
                {spikes.data.count} active
              </Badge>
            </Link>
          ) : undefined
        }
      >
        {spikes.isPending ? (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : (
          <AlertsFeed items={spikes.data?.items ?? []} limit={6} />
        )}
      </Panel>

      {/* KPI rows */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Registered cases"
          value={s ? s.total_cases.toLocaleString() : "—"}
          icon={Layers}
          caption={s ? `${s.fir_cases.toLocaleString()} FIRs · ${s.districts} districts · ${s.police_stations} stations` : "Loading…"}
        />
        <StatCard
          label="Chargesheet rate"
          value={s ? `${s.chargesheet_rate}%` : "—"}
          icon={Gavel}
          accent="success"
          caption="A-type final reports"
          delta={s ? { value: `${s.conviction_rate}% convicted`, direction: "up", tone: "good" } : undefined}
        />
        <StatCard
          label="Cyber-crime share"
          value={s ? `${s.cyber_share}%` : "—"}
          icon={Wifi}
          accent="info"
          caption="Of all registered cases"
          delta={s ? { value: "rising", direction: "up", tone: "bad" } : undefined}
        />
        <StatCard
          label="Top hotspot"
          value={s?.top_district ?? "—"}
          icon={Crosshair}
          accent="danger"
          caption={s ? `${s.top_district_count.toLocaleString()} cases` : "Loading…"}
        />
      </div>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Heinous offences"
          value={s ? `${s.heinous_share}%` : "—"}
          icon={Scale}
          accent="danger"
          caption="GravityOffence = Heinous"
        />
        <StatCard
          label="Arrests & surrenders"
          value={s ? s.arrests_total.toLocaleString() : "—"}
          icon={Lock}
          accent="warning"
          caption="ArrestSurrender events"
        />
        <StatCard
          label="Investigation pendency"
          value={s ? `${s.pendency_rate}%` : "—"}
          icon={Hourglass}
          accent="warning"
          caption={s ? `median ${s.median_days_to_chargesheet}d to chargesheet` : undefined}
        />
        <StatCard
          label="Repeat offenders"
          value={s ? s.repeat_offenders.toLocaleString() : "—"}
          icon={Users}
          accent="info"
          caption="Accused linked to 2+ FIRs"
        />
      </div>

      {/* Monthly trend by crime head */}
      <Panel icon={TrendingUp} title="Case trend" subtitle="Monthly registrations by crime head — note the rising cyber-crime band">
        <div style={{ height: 300 }}>
          {byMonth.isPending ? (
            <ChartSkeleton height={300} />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={byMonth.data?.items ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                <defs>
                  {(byMonth.data?.heads ?? []).map((h) => (
                    <linearGradient key={h} id={gradId(h)} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={HEAD_COLORS[h] ?? CHART.accent} stopOpacity={0.45} />
                      <stop offset="100%" stopColor={HEAD_COLORS[h] ?? CHART.accent} stopOpacity={0.02} />
                    </linearGradient>
                  ))}
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="month" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} minTickGap={24} />
                <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={40} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" />
                {(byMonth.data?.heads ?? []).map((h) => (
                  <Area
                    key={h}
                    type="monotone"
                    dataKey={h}
                    stackId="1"
                    stroke={HEAD_COLORS[h] ?? CHART.accent}
                    strokeWidth={2}
                    fill={`url(#${gradId(h)})`}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {/* Investigation funnel + top sections */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          icon={Filter}
          title="Investigation funnel"
          subtitle="Registration → final report → chargesheet → trial → conviction"
        >
          {funnel.isPending ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <div className="space-y-3">
              {stages.map((st, i) => (
                <div key={st.stage}>
                  <div className="mb-1 flex items-baseline justify-between text-xs">
                    <span className="font-medium text-white/85">{st.stage}</span>
                    <span className="tabular text-muted">
                      {st.count.toLocaleString()}
                      {i > 0 && maxStage ? ` · ${Math.round((st.count / maxStage) * 100)}%` : ""}
                    </span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-bg/80">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-accent/50 to-accent"
                      style={{ width: `${Math.max(1.5, (st.count / maxStage) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
              <div className="mt-4 flex flex-wrap gap-1.5 border-t border-line pt-3">
                {(funnel.data?.leakage ?? []).map((l) => (
                  <Badge key={l.label} variant="neutral">
                    {l.label} · {l.count.toLocaleString()}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel
          icon={BookOpenText}
          title="Most-invoked act & sections"
          subtitle="From ActSectionAssociation across all FIRs"
        >
          <div style={{ height: 320 }}>
            {topSections.isPending ? (
              <ChartSkeleton height={320} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={(topSections.data?.items ?? []).slice(0, 12)}
                  layout="vertical"
                  margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="label"
                    tick={{ ...CHART.axisTick, fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={92}
                  />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    labelStyle={tooltipLabelStyle}
                    itemStyle={tooltipItemStyle}
                    cursor={cursorFill}
                    formatter={(v: any, _n: any, p: any) => [`${v} — ${p?.payload?.description ?? ""}`, "cases"]}
                  />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16} fill={CHART.accent} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>

      {/* District + sub-head breakdowns */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={BarChart3} title="Cases by district" subtitle="Top 12 jurisdictions by volume">
          <div style={{ height: 360 }}>
            {byDistrict.isPending ? (
              <ChartSkeleton height={360} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topDistricts} margin={{ left: 4, right: 8, top: 8, bottom: 64 }}>
                  <defs>
                    <linearGradient id={CHART.gradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.accentSoft} stopOpacity={0.95} />
                      <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.35} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="district" angle={-40} textAnchor="end" interval={0} tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                  <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Bar dataKey="cases" radius={[5, 5, 0, 0]} maxBarSize={40}>
                    {topDistricts.map((_, i) => (
                      <Cell key={i} fill={`url(#${CHART.gradientId})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel icon={ListChecks} title="Crime sub-head breakdown" subtitle="Ranked, colored by parent crime head">
          <div style={{ height: 360 }}>
            {bySubHead.isPending ? (
              <ChartSkeleton height={360} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={subHeads} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="sub_head"
                    tick={{ ...CHART.axisTick, fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={148}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={18}>
                    {subHeads.map((c, i) => (
                      <Cell key={i} fill={HEAD_COLORS[c.crime_head] ?? CHART.accent} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {Object.entries(HEAD_COLORS)
              .filter(([k]) => k !== "Other" && k !== "Others")
              .map(([head, color]) => (
                <span key={head} className="flex items-center gap-1.5 text-[11px] text-muted">
                  <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
                  {head}
                </span>
              ))}
          </div>
        </Panel>
      </div>

      {/* Status + composition donuts */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel icon={PieIcon} title="Case status" subtitle="CaseStatusMaster pipeline">
          {byStatus.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byStatus.data?.items ?? []).map((i) => ({ name: i.status, value: i.count }))}
              colors={(n) => STATUS_COLORS[n] ?? CHART.accent}
              centerValue={`${byStatus.data?.chargesheet_rate ?? 0}%`}
              centerLabel="chargesheeted"
            />
          )}
        </Panel>

        <Panel icon={PieIcon} title="Case category" subtitle="FIR · Zero FIR · UDR · PAR">
          {byCategory.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byCategory.data?.items ?? []).map((i) => ({ name: i.category, value: i.count }))}
              colors={(n) => CATEGORY_COLORS[n] ?? CHART.accent}
              centerValue={s ? s.total_cases.toLocaleString() : ""}
              centerLabel="cases"
            />
          )}
        </Panel>

        <Panel icon={PieIcon} title="Offence gravity" subtitle="Heinous vs non-heinous">
          {byGravity.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byGravity.data?.items ?? []).map((i) => ({ name: i.gravity, value: i.count }))}
              colors={(n) => GRAVITY_COLORS[n] ?? CHART.accent}
              centerValue={s ? `${s.heinous_share}%` : ""}
              centerLabel="heinous"
            />
          )}
        </Panel>
      </div>

      {/* Crime head composition */}
      <Panel icon={PieIcon} title="Crime composition" subtitle="Share by ERD crime head (CrimeHead master)">
        {byCrimeHead.isPending ? (
          <Skeleton className="h-[220px] w-full" />
        ) : (
          <DonutChart
            data={(byCrimeHead.data?.items ?? []).map((i) => ({ name: i.crime_head, value: i.count }))}
            colors={(n) => HEAD_COLORS[n] ?? CHART.accent}
            centerValue={s ? s.total_cases.toLocaleString() : ""}
            centerLabel="cases"
          />
        )}
      </Panel>
    </div>
  );
}
