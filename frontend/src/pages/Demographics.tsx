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
} from "recharts";
import { Users, Crosshair, Clock3, Venus, ShieldAlert, Briefcase, BookUser, Landmark } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { Skeleton } from "../components/Skeleton";
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
  GENDER_COLORS,
  PALETTE,
} from "../components/charts/theme";

export default function Demographics() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const demo = useQuery({ queryKey: ["demographics"], queryFn: api.demographics });
  const timing = useQuery({ queryKey: ["investigation"], queryFn: api.investigation });

  const s = summary.data;
  const d = demo.data;
  const t = useT();
  const dl = useDataLabel();
  const charsFor = useCharsFor();

  // Merge victim & accused age-group histograms into one grouped series.
  // The bar `dataKey`s are the *translated* legend labels so the tooltip reads in the
  // active language; age buckets ("18–25") are numeric and need no translation.
  const victimsKey = t("demographics.victims");
  const accusedKey = t("demographics.accused");
  const ageData =
    d &&
    d.victim_age_groups.map((v, i) => ({
      group: v.group,
      [victimsKey]: v.count,
      [accusedKey]: d.accused_age_groups[i]?.count ?? 0,
    }));

  // Category axes: translate the label the chart paints, keeping the count untouched.
  const occupationData = d?.complainant_occupation.map((o) => ({
    ...o,
    group: dl("occupation", o.group),
  }));
  const delayData = timing.data?.report_delay.map((r) => ({
    ...r,
    sub_head: dl("crimeSubHead", r.sub_head),
  }));

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Users}
        eyebrow={t("demographics.eyebrow")}
        title={t("demographics.title")}
        subtitle={t("demographics.subtitle")}
      />

      {/* KPI row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("demographics.policeVictims")}
          value={d ? d.police_victims.toLocaleString() : t("common.none")}
          icon={ShieldAlert}
          accent="danger"
          caption={t("demographics.policeVictimsCaption")}
        />
        <StatCard
          label={t("demographics.heinousShare")}
          value={s ? `${s.heinous_share}%` : t("common.none")}
          icon={ShieldAlert}
          accent="warning"
          caption={t("demographics.heinousShareCaption")}
        />
        <StatCard
          label={t("demographics.avgDelay")}
          value={s ? t("demographics.avgDelayValue", { days: s.avg_report_delay_days }) : t("common.none")}
          icon={Clock3}
          accent="info"
          caption={t("demographics.avgDelayCaption")}
        />
        <StatCard
          label={t("demographics.topCrime")}
          value={s ? dl("crimeSubHead", s.top_sub_head) : t("common.none")}
          icon={Crosshair}
          caption={
            s
              ? t("demographics.topCrimeCaption", { count: s.top_sub_head_count.toLocaleString() })
              : t("common.loading")
          }
        />
      </div>

      {/* Age distribution: victim vs accused */}
      <Panel
        icon={Users}
        title={t("demographics.ageTitle")}
        subtitle={t("demographics.ageSubtitle")}
      >
        <div className="h-[260px] sm:h-[300px] lg:h-[320px]">
          {demo.isPending || !ageData ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ageData} margin={{ left: 4, right: 8, top: 8, bottom: 4 }} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="group" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                <Bar dataKey={victimsKey} fill="#38bdf8" radius={[4, 4, 0, 0]} maxBarSize={40} />
                <Bar dataKey={accusedKey} fill="#f472b6" radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <ChartLegend
          items={[
            { label: victimsKey, color: "#38bdf8" },
            { label: accusedKey, color: "#f472b6" },
          ]}
        />
      </Panel>

      {/* Gender splits */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* `name` stays the English gender so GENDER_COLORS still resolves; `label` is
            what the ring and legend paint. */}
        <Panel
          icon={Venus}
          title={t("demographics.victimGender")}
          subtitle={t("demographics.victimGenderSubtitle")}
        >
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.victim_gender.map((g) => ({
                name: g.group,
                label: dl("gender", g.group),
                value: g.count,
              }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
        <Panel
          icon={Venus}
          title={t("demographics.accusedGender")}
          subtitle={t("demographics.accusedGenderSubtitle")}
        >
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.accused_gender.map((g) => ({
                name: g.group,
                label: dl("gender", g.group),
                value: g.count,
              }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
      </div>

      {/* Complainant profile */}
      <Panel
        icon={Briefcase}
        title={t("demographics.occupation")}
        subtitle={t("demographics.occupationSubtitle")}
      >
        <ChartFrame className="h-[240px] sm:h-[280px]">
          {(w) =>
            demo.isPending || !occupationData ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={occupationData} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                  <YAxis
                    type="category"
                    dataKey="group"
                    tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                    tickLine={false}
                    axisLine={false}
                    width={catAxisWidth(w)}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16}>
                    {occupationData.map((_, i) => (
                      <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </ChartFrame>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel
          icon={BookUser}
          title={t("demographics.religion")}
          subtitle={t("demographics.religionSubtitle")}
        >
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.complainant_religion.map((g) => ({
                name: g.group,
                label: dl("religion", g.group),
                value: g.count,
              }))}
              colors={(_, i) => PALETTE[i % PALETTE.length]}
            />
          )}
        </Panel>
        <Panel
          icon={BookUser}
          title={t("demographics.caste")}
          subtitle={t("demographics.casteSubtitle")}
        >
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.complainant_caste.map((g) => ({
                name: g.group,
                label: dl("caste", g.group),
                value: g.count,
              }))}
              colors={(_, i) => PALETTE[i % PALETTE.length]}
            />
          )}
        </Panel>
      </div>

      {/* Reporting delay by sub-head */}
      <Panel
        icon={Landmark}
        title={t("demographics.delayTitle")}
        subtitle={t("demographics.delaySubtitle")}
      >
        <ChartFrame className="h-[240px] sm:h-[280px]">
          {(w) =>
            timing.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={delayData ?? []} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} unit="d" />
                  <YAxis
                    type="category"
                    dataKey="sub_head"
                    tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                    tickLine={false}
                    axisLine={false}
                    width={catAxisWidth(w)}
                  />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} formatter={(v: any) => [t("demographics.delayTooltip", { days: v }), t("demographics.delayLabel")]} />
                  <Bar dataKey="avg_days" radius={[0, 4, 4, 0]} maxBarSize={16} fill="#f59e0b" />
                </BarChart>
              </ResponsiveContainer>
            )
          }
        </ChartFrame>
        <p className="mt-3 text-xs leading-relaxed text-muted">{t("demographics.delayNote")}</p>
      </Panel>
    </div>
  );
}
