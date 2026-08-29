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
import ChartFrame from "../components/charts/ChartFrame";
import ChartLegend from "../components/charts/ChartLegend";
import { truncatedTick, useCharsFor, catAxisWidth } from "../components/charts/AxisTick";
import { useT } from "../i18n";
import { useDataLabel } from "../i18n/data";
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
  const t = useT();
  const d = useDataLabel();
  const charsFor = useCharsFor();

  // Category-axis labels are translated in the data; the counts and colour lookups
  // below still key off the untouched English fields (`crime_head`).
  const topDistricts = (byDistrict.data?.items ?? [])
    .slice(0, 12)
    .map((x) => ({ ...x, district: d("district", x.district) }));
  const subHeads = (bySubHead.data?.items ?? [])
    .slice(0, 14)
    .map((x) => ({ ...x, sub_head: d("crimeSubHead", x.sub_head) }));
  const stages = funnel.data?.stages ?? [];
  const maxStage = stages.reduce((m, x) => Math.max(m, x.count), 1);

  const headLegend = Object.entries(HEAD_COLORS)
    .filter(([k]) => k !== "Other" && k !== "Others")
    .map(([head, color]) => ({ label: d("crimeHead", head), color }));

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Activity}
        eyebrow={t("dashboard.eyebrow")}
        title={t("dashboard.title")}
        subtitle={t("dashboard.subtitle")}
      />

      {/* Emerging-trend spike alerts */}
      <Panel
        icon={Siren}
        title={t("dashboard.spikes")}
        subtitle={t("dashboard.spikesSubtitle")}
        actions={
          spikes.data ? (
            <Link to="/hotspots">
              <Badge variant={spikes.data.count ? "danger" : "success"} dot>
                {t("dashboard.spikesActive", { count: spikes.data.count })}
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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("dashboard.registeredCases")}
          value={s ? s.total_cases.toLocaleString() : t("common.none")}
          icon={Layers}
          caption={
            s
              ? t("dashboard.registeredCaption", {
                  firs: s.fir_cases.toLocaleString(),
                  districts: s.districts,
                  stations: s.police_stations,
                })
              : t("common.loading")
          }
        />
        <StatCard
          label={t("dashboard.chargesheetRate")}
          value={s ? `${s.chargesheet_rate}%` : t("common.none")}
          icon={Gavel}
          accent="success"
          caption={t("dashboard.chargesheetCaption")}
          delta={
            s
              ? {
                  value: t("dashboard.convictedDelta", { rate: s.conviction_rate }),
                  direction: "up",
                  tone: "good",
                }
              : undefined
          }
        />
        <StatCard
          label={t("dashboard.cyberShare")}
          value={s ? `${s.cyber_share}%` : t("common.none")}
          icon={Wifi}
          accent="info"
          caption={t("dashboard.ofAllCases")}
          delta={s ? { value: t("dashboard.rising"), direction: "up", tone: "bad" } : undefined}
        />
        <StatCard
          label={t("dashboard.topHotspot")}
          value={s ? d("district", s.top_district) : t("common.none")}
          icon={Crosshair}
          accent="danger"
          caption={
            s
              ? t("dashboard.caseCount", { count: s.top_district_count.toLocaleString() })
              : t("common.loading")
          }
        />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("dashboard.heinous")}
          value={s ? `${s.heinous_share}%` : t("common.none")}
          icon={Scale}
          accent="danger"
          caption={t("dashboard.heinousCaption")}
        />
        <StatCard
          label={t("dashboard.arrests")}
          value={s ? s.arrests_total.toLocaleString() : t("common.none")}
          icon={Lock}
          accent="warning"
          caption={t("dashboard.arrestsCaption")}
        />
        <StatCard
          label={t("dashboard.pendency")}
          value={s ? `${s.pendency_rate}%` : t("common.none")}
          icon={Hourglass}
          accent="warning"
          caption={s ? t("dashboard.pendencyCaption", { days: s.median_days_to_chargesheet }) : undefined}
        />
        <StatCard
          label={t("dashboard.repeatOffenders")}
          value={s ? s.repeat_offenders.toLocaleString() : t("common.none")}
          icon={Users}
          accent="info"
          caption={t("dashboard.repeatOffendersCaption")}
        />
      </div>

      {/* Monthly trend by crime head */}
      <Panel icon={TrendingUp} title={t("dashboard.trend")} subtitle={t("dashboard.trendSubtitle")}>
        <div className="h-[240px] sm:h-[280px] lg:h-[300px]">
          {byMonth.isPending ? (
            <ChartSkeleton />
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
                {(byMonth.data?.heads ?? []).map((h) => (
                  // `dataKey` must stay the English head — it indexes into each month
                  // row and feeds gradId(). `name` is what the tooltip prints.
                  <Area
                    key={h}
                    type="monotone"
                    dataKey={h}
                    name={d("crimeHead", h)}
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
        <ChartLegend
          items={(byMonth.data?.heads ?? []).map((h) => ({
            label: d("crimeHead", h),
            color: HEAD_COLORS[h] ?? CHART.accent,
          }))}
        />
      </Panel>

      {/* Investigation funnel + top sections */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          icon={Filter}
          title={t("dashboard.funnel")}
          subtitle={t("dashboard.funnelSubtitle")}
        >
          {funnel.isPending ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <div className="space-y-3">
              {stages.map((st, i) => (
                <div key={st.stage}>
                  <div className="mb-1 flex items-baseline justify-between text-xs">
                    <span className="font-medium text-white/85">{d("funnelStage", st.stage)}</span>
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
                    {d("funnelLeakage", l.label)} · {l.count.toLocaleString()}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </Panel>

        <Panel
          icon={BookOpenText}
          title={t("dashboard.sections")}
          subtitle={t("dashboard.sectionsSubtitle")}
        >
          <ChartFrame className="h-[280px] sm:h-[320px]">
            {(w) =>
              topSections.isPending ? (
                <ChartSkeleton />
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
                      tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                      tickLine={false}
                      axisLine={false}
                      width={catAxisWidth(w)}
                    />
                    <Tooltip
                      contentStyle={tooltipStyle}
                      labelStyle={tooltipLabelStyle}
                      itemStyle={tooltipItemStyle}
                      cursor={cursorFill}
                      // Act/Section labels ("IPC 302") and the statutory description
                      // stay English in both languages — that is how they are cited.
                      formatter={(v: any, _n: any, p: any) => [
                        `${v} — ${p?.payload?.description ?? ""}`,
                        t("dashboard.sectionsTooltipLabel"),
                      ]}
                    />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16} fill={CHART.accent} />
                  </BarChart>
                </ResponsiveContainer>
              )
            }
          </ChartFrame>
        </Panel>
      </div>

      {/* District + sub-head breakdowns */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={BarChart3} title={t("dashboard.byDistrict")} subtitle={t("dashboard.byDistrictSubtitle")}>
          <ChartFrame className="h-[300px] sm:h-[340px] lg:h-[360px]">
            {(w) => {
              if (byDistrict.isPending) return <ChartSkeleton />;
              // Rotated labels need horizontal room per band. Below this the
              // bars are so narrow that even truncated names collide, so the
              // chart turns on its side and the names read left-aligned.
              const horizontal = w > 0 && w < 560;
              const bars = horizontal ? topDistricts.slice(0, 8) : topDistricts;
              const gradient = (
                <defs>
                  <linearGradient
                    id={CHART.gradientId}
                    x1="0"
                    y1="0"
                    x2={horizontal ? "1" : "0"}
                    y2={horizontal ? "0" : "1"}
                  >
                    <stop offset="0%" stopColor={CHART.accentSoft} stopOpacity={0.95} />
                    <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.35} />
                  </linearGradient>
                </defs>
              );

              return (
                <ResponsiveContainer width="100%" height="100%">
                  {horizontal ? (
                    <BarChart data={bars} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                      {gradient}
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                      <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                      <YAxis
                        type="category"
                        dataKey="district"
                        tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                        tickLine={false}
                        axisLine={false}
                        width={catAxisWidth(w)}
                      />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                      <Bar dataKey="cases" radius={[0, 4, 4, 0]} maxBarSize={18}>
                        {bars.map((_, i) => (
                          <Cell key={i} fill={`url(#${CHART.gradientId})`} />
                        ))}
                      </Bar>
                    </BarChart>
                  ) : (
                    <BarChart data={bars} margin={{ left: 4, right: 8, top: 8, bottom: 72 }}>
                      {gradient}
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                      <XAxis
                        dataKey="district"
                        interval={0}
                        height={72}
                        tickLine={false}
                        axisLine={{ stroke: CHART.grid }}
                        tick={truncatedTick(12, { angle: -40, fontSize: 11 })}
                      />
                      <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={40} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                      <Bar dataKey="cases" radius={[5, 5, 0, 0]} maxBarSize={40}>
                        {bars.map((_, i) => (
                          <Cell key={i} fill={`url(#${CHART.gradientId})`} />
                        ))}
                      </Bar>
                    </BarChart>
                  )}
                </ResponsiveContainer>
              );
            }}
          </ChartFrame>
        </Panel>

        <Panel icon={ListChecks} title={t("dashboard.bySubHead")} subtitle={t("dashboard.bySubHeadSubtitle")}>
          <ChartFrame className="h-[300px] sm:h-[340px] lg:h-[360px]">
            {(w) =>
              bySubHead.isPending ? (
                <ChartSkeleton />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={subHeads} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                    <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                    <YAxis
                      type="category"
                      dataKey="sub_head"
                      tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                      tickLine={false}
                      axisLine={false}
                      width={catAxisWidth(w)}
                    />
                    <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={18}>
                      {subHeads.map((c, i) => (
                        <Cell key={i} fill={HEAD_COLORS[c.crime_head] ?? CHART.accent} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )
            }
          </ChartFrame>
          <ChartLegend items={headLegend} />
        </Panel>
      </div>

      {/* Status + composition donuts — 3-up only at 2xl, where each panel is
          still wide enough for a ring plus a readable legend beside it */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 2xl:grid-cols-3">
        {/* Each donut keeps the English value as `name` so the *_COLORS lookups still
            resolve, and paints `label`. */}
        <Panel icon={PieIcon} title={t("dashboard.caseStatus")} subtitle={t("dashboard.caseStatusSubtitle")}>
          {byStatus.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byStatus.data?.items ?? []).map((i) => ({
                name: i.status,
                label: d("caseStatus", i.status),
                value: i.count,
              }))}
              colors={(n) => STATUS_COLORS[n] ?? CHART.accent}
              centerValue={`${byStatus.data?.chargesheet_rate ?? 0}%`}
              centerLabel={t("dashboard.chargesheetedCenter")}
            />
          )}
        </Panel>

        <Panel icon={PieIcon} title={t("dashboard.caseCategory")} subtitle={t("dashboard.caseCategorySubtitle")}>
          {byCategory.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byCategory.data?.items ?? []).map((i) => ({
                name: i.category,
                label: d("category", i.category),
                value: i.count,
              }))}
              colors={(n) => CATEGORY_COLORS[n] ?? CHART.accent}
              centerValue={s ? s.total_cases.toLocaleString() : ""}
              centerLabel={t("dashboard.casesCenter")}
            />
          )}
        </Panel>

        <Panel icon={PieIcon} title={t("dashboard.gravity")} subtitle={t("dashboard.gravitySubtitle")}>
          {byGravity.isPending ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={(byGravity.data?.items ?? []).map((i) => ({
                name: i.gravity,
                label: d("gravity", i.gravity),
                value: i.count,
              }))}
              colors={(n) => GRAVITY_COLORS[n] ?? CHART.accent}
              centerValue={s ? `${s.heinous_share}%` : ""}
              centerLabel={t("dashboard.heinousCenter")}
            />
          )}
        </Panel>
      </div>

      {/* Crime head composition */}
      <Panel icon={PieIcon} title={t("dashboard.composition")} subtitle={t("dashboard.compositionSubtitle")}>
        {byCrimeHead.isPending ? (
          <Skeleton className="h-[220px] w-full" />
        ) : (
          <DonutChart
            data={(byCrimeHead.data?.items ?? []).map((i) => ({
              name: i.crime_head,
              label: d("crimeHead", i.crime_head),
              value: i.count,
            }))}
            colors={(n) => HEAD_COLORS[n] ?? CHART.accent}
            centerValue={s ? s.total_cases.toLocaleString() : ""}
            centerLabel={t("dashboard.casesCenter")}
          />
        )}
      </Panel>
    </div>
  );
}
