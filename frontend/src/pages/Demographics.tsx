import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";
import { Users, Crosshair, Swords, Clock3, Building2, Venus, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import { Skeleton } from "../components/Skeleton";
import DonutChart from "../components/charts/DonutChart";
import {
  CHART,
  tooltipStyle,
  tooltipLabelStyle,
  tooltipItemStyle,
  cursorFill,
  SEVERITY_COLORS,
  GENDER_COLORS,
  PALETTE,
} from "../components/charts/theme";

export default function Demographics() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const demo = useQuery({ queryKey: ["demographics"], queryFn: api.demographics });
  const severity = useQuery({ queryKey: ["bySeverity"], queryFn: api.bySeverity });

  const s = summary.data;
  const d = demo.data;

  // Merge victim & offender age-group histograms into one grouped series.
  const ageData =
    d &&
    d.victim_age_groups.map((v, i) => ({
      group: v.group,
      Victims: v.count,
      Offenders: d.offender_age_groups[i]?.count ?? 0,
    }));

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Users}
        eyebrow="Demographic Intelligence"
        title="Victim & Offender Profiles"
        subtitle="Age, gender, severity and urbanisation across all reported incidents"
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Weapon involved"
          value={s ? `${s.weapon_share}%` : "—"}
          icon={Swords}
          accent="danger"
          caption="Of all incidents"
        />
        <StatCard
          label="Severe cases"
          value={s ? `${s.severe_share}%` : "—"}
          icon={ShieldAlert}
          accent="warning"
          caption="Murder & kidnapping"
        />
        <StatCard
          label="Avg FIR delay"
          value={s ? `${s.avg_fir_delay}d` : "—"}
          icon={Clock3}
          accent="info"
          caption="Event to report"
        />
        <StatCard
          label="Top crime"
          value={s?.top_crime ?? "—"}
          icon={Crosshair}
          caption={s ? `${s.top_crime_count.toLocaleString()} cases` : "Loading…"}
        />
      </div>

      {/* Age distribution: victim vs offender */}
      <Panel
        icon={Users}
        title="Age distribution — victims vs offenders"
        subtitle="Offenders skew 18–35; victims span a wider, older range"
      >
        <div style={{ height: 320 }}>
          {demo.isPending || !ageData ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ageData} margin={{ left: 4, right: 8, top: 8, bottom: 4 }} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                <XAxis dataKey="group" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={44} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} iconType="circle" />
                <Bar dataKey="Victims" fill="#38bdf8" radius={[4, 4, 0, 0]} maxBarSize={40} />
                <Bar dataKey="Offenders" fill="#f472b6" radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {/* Gender splits */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Venus} title="Victim gender" subtitle="Reported victims by gender">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.victim_gender.map((g) => ({ name: g.gender, value: g.count }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
        <Panel icon={Venus} title="Offender gender" subtitle="Accused persons by gender (incident-weighted)">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.offender_gender.map((g) => ({ name: g.gender, value: g.count }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
      </div>

      {/* Severity + urbanisation */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={ShieldAlert} title="Severity profile" subtitle="Incidents by severity tier">
          <div style={{ height: 240 }}>
            {severity.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={severity.data?.items ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="severity" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                  <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={44} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Bar dataKey="count" radius={[5, 5, 0, 0]} maxBarSize={64}>
                    {(severity.data?.items ?? []).map((it) => (
                      <Cell key={it.severity} fill={SEVERITY_COLORS[it.severity] ?? CHART.accent} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel icon={Building2} title="Urbanisation" subtitle="Where incidents occur">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.urban_rural.map((g) => ({ name: g.group, value: g.count }))}
              colors={(_, i) => PALETTE[i % PALETTE.length]}
            />
          )}
        </Panel>
      </div>
    </div>
  );
}
