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
  ShieldCheck,
  Wifi,
  Crosshair,
  BarChart3,
  TrendingUp,
  ListChecks,
  PieChart as PieIcon,
} from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import StatCard from "../components/StatCard";
import PageHeader from "../components/PageHeader";
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
} from "../components/charts/theme";

export default function Dashboard() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const byDistrict = useQuery({ queryKey: ["byDistrict"], queryFn: api.byDistrict });
  const byCrimeType = useQuery({ queryKey: ["byCrimeType"], queryFn: api.byCrimeType });
  const byMonth = useQuery({ queryKey: ["byMonth"], queryFn: api.byMonth });
  const byStatus = useQuery({ queryKey: ["byStatus"], queryFn: api.byStatus });
  const byCrimeHead = useQuery({ queryKey: ["byCrimeHead"], queryFn: api.byCrimeHead });

  const s = summary.data;
  const topDistricts = (byDistrict.data?.items ?? []).slice(0, 12);
  const crimeTypes = byCrimeType.data?.items ?? [];

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Activity}
        eyebrow="Command Overview"
        title="Strategic Intelligence Hub"
        subtitle="Live operational picture across the State Crime Records Bureau"
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Total incidents"
          value={s ? s.total_incidents.toLocaleString() : "—"}
          icon={Layers}
          caption={s ? `Across ${s.districts} districts` : "Loading…"}
        />
        <StatCard
          label="Clearance rate"
          value={s ? `${s.clearance_rate}%` : "—"}
          icon={ShieldCheck}
          accent="success"
          caption="Charge-sheeted or closed"
          delta={s ? { value: `${s.clearance_rate}%`, direction: "up", tone: "good" } : undefined}
        />
        <StatCard
          label="Cybercrime share"
          value={s ? `${s.cyber_share}%` : "—"}
          icon={Wifi}
          accent="info"
          caption="Of all reported incidents"
          delta={s ? { value: "rising", direction: "up", tone: "bad" } : undefined}
        />
        <StatCard
          label="Top hotspot"
          value={s?.top_district ?? "—"}
          icon={Crosshair}
          accent="danger"
          caption={s ? `${s.top_district_count.toLocaleString()} incidents` : "Loading…"}
        />
      </div>

      {/* Monthly trend by crime head */}
      <Panel icon={TrendingUp} title="Incident trend" subtitle="Monthly volume by crime head — note the rising economic-offence line">
        <div style={{ height: 300 }}>
          {byMonth.isPending ? (
            <ChartSkeleton height={300} />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={byMonth.data?.items ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                <defs>
                  {(byMonth.data?.heads ?? []).map((h) => (
                    <linearGradient key={h} id={`g-${h}`} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={HEAD_COLORS[h] ?? CHART.accent} stopOpacity={0.5} />
                      <stop offset="100%" stopColor={HEAD_COLORS[h] ?? CHART.accent} stopOpacity={0.03} />
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
                    strokeWidth={1.5}
                    fill={`url(#g-${h})`}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {/* District + crime-type breakdowns */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={BarChart3} title="Incidents by district" subtitle="Top 12 jurisdictions by volume">
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
                  <Bar dataKey="incidents" radius={[5, 5, 0, 0]} maxBarSize={40}>
                    {topDistricts.map((_, i) => (
                      <Cell key={i} fill={`url(#${CHART.gradientId})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel icon={ListChecks} title="Crime-type breakdown" subtitle="Ranked, colored by crime head">
          <div style={{ height: 360 }}>
            {byCrimeType.isPending ? (
              <ChartSkeleton height={360} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={crimeTypes} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="crime_type"
                    tick={{ ...CHART.axisTick, fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={104}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={18}>
                    {crimeTypes.map((c, i) => (
                      <Cell key={i} fill={HEAD_COLORS[c.crime_head] ?? CHART.accent} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5">
            {Object.entries(HEAD_COLORS)
              .filter(([k]) => k !== "Other")
              .map(([head, color]) => (
                <span key={head} className="flex items-center gap-1.5 text-[11px] text-muted">
                  <span className="h-2 w-2 rounded-sm" style={{ background: color }} />
                  {head}
                </span>
              ))}
          </div>
        </Panel>
      </div>

      {/* Status + crime head composition */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={PieIcon} title="Case status" subtitle="Investigation pipeline & clearance">
          {byStatus.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byStatus.data?.items ?? []).map((i) => ({ name: i.status, value: i.count }))}
              colors={(n) => STATUS_COLORS[n] ?? CHART.accent}
              centerValue={`${byStatus.data?.clearance_rate ?? 0}%`}
              centerLabel="cleared"
            />
          )}
        </Panel>

        <Panel icon={PieIcon} title="Crime composition" subtitle="Share by crime head">
          {byCrimeHead.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byCrimeHead.data?.items ?? []).map((i) => ({ name: i.crime_head, value: i.count }))}
              colors={(n) => HEAD_COLORS[n] ?? CHART.accent}
              centerValue={s ? s.total_incidents.toLocaleString() : ""}
              centerLabel="incidents"
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
