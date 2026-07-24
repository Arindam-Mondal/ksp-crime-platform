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
import { Users, Crosshair, Clock3, Venus, ShieldAlert, Briefcase, BookUser, Landmark } from "lucide-react";
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
  GENDER_COLORS,
  PALETTE,
} from "../components/charts/theme";

export default function Demographics() {
  const summary = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const demo = useQuery({ queryKey: ["demographics"], queryFn: api.demographics });
  const timing = useQuery({ queryKey: ["investigation"], queryFn: api.investigation });

  const s = summary.data;
  const d = demo.data;

  // Merge victim & accused age-group histograms into one grouped series.
  const ageData =
    d &&
    d.victim_age_groups.map((v, i) => ({
      group: v.group,
      Victims: v.count,
      Accused: d.accused_age_groups[i]?.count ?? 0,
    }));

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Users}
        eyebrow="Demographic Intelligence"
        title="Victim, Accused & Complainant Profiles"
        subtitle="Party demographics straight from the FIR ERD — Victim, Accused and ComplainantDetails tables"
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Police victims"
          value={d ? d.police_victims.toLocaleString() : "—"}
          icon={ShieldAlert}
          accent="danger"
          caption="Victim.VictimPolice = 1"
        />
        <StatCard
          label="Heinous share"
          value={s ? `${s.heinous_share}%` : "—"}
          icon={ShieldAlert}
          accent="warning"
          caption="Of all registered cases"
        />
        <StatCard
          label="Avg reporting delay"
          value={s ? `${s.avg_report_delay_days}d` : "—"}
          icon={Clock3}
          accent="info"
          caption="Incident → info received at PS"
        />
        <StatCard
          label="Top crime"
          value={s?.top_sub_head ?? "—"}
          icon={Crosshair}
          caption={s ? `${s.top_sub_head_count.toLocaleString()} cases` : "Loading…"}
        />
      </div>

      {/* Age distribution: victim vs accused */}
      <Panel
        icon={Users}
        title="Age distribution — victims vs accused"
        subtitle="Accused skew 18–35; victims span a wider, older range"
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
                <Bar dataKey="Accused" fill="#f472b6" radius={[4, 4, 0, 0]} maxBarSize={40} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      {/* Gender splits */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Venus} title="Victim gender" subtitle="Victim.GenderID across all cases">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.victim_gender.map((g) => ({ name: g.group, value: g.count }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
        <Panel icon={Venus} title="Accused gender" subtitle="Accused.GenderID across all cases">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.accused_gender.map((g) => ({ name: g.group, value: g.count }))}
              colors={(n) => GENDER_COLORS[n] ?? CHART.accent}
            />
          )}
        </Panel>
      </div>

      {/* Complainant profile */}
      <Panel
        icon={Briefcase}
        title="Complainant occupation"
        subtitle="OccupationMaster mix, as recorded on the FIR"
      >
        <div style={{ height: 280 }}>
          {demo.isPending || !d ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={d.complainant_occupation} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                <YAxis type="category" dataKey="group" tick={{ ...CHART.axisTick, fontSize: 10 }} tickLine={false} axisLine={false} width={130} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={16}>
                  {d.complainant_occupation.map((_, i) => (
                    <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={BookUser} title="Complainant religion" subtitle="ReligionMaster mix">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.complainant_religion.map((g) => ({ name: g.group, value: g.count }))}
              colors={(_, i) => PALETTE[i % PALETTE.length]}
            />
          )}
        </Panel>
        <Panel icon={BookUser} title="Complainant social category" subtitle="CasteMaster mix">
          {demo.isPending || !d ? (
            <Skeleton className="h-[220px] w-full" />
          ) : (
            <DonutChart
              data={d.complainant_caste.map((g) => ({ name: g.group, value: g.count }))}
              colors={(_, i) => PALETTE[i % PALETTE.length]}
            />
          )}
        </Panel>
      </div>

      {/* Reporting delay by sub-head */}
      <Panel
        icon={Landmark}
        title="Reporting delay by crime"
        subtitle="Average days between the incident and information reaching the police station"
      >
        <div style={{ height: 280 }}>
          {timing.isPending ? (
            <Skeleton className="h-full w-full" />
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={timing.data?.report_delay ?? []} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} unit="d" />
                <YAxis type="category" dataKey="sub_head" tick={{ ...CHART.axisTick, fontSize: 10 }} tickLine={false} axisLine={false} width={172} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} formatter={(v: any) => [`${v} days avg`, "delay"]} />
                <Bar dataKey="avg_days" radius={[0, 4, 4, 0]} maxBarSize={16} fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        <p className="mt-3 text-xs leading-relaxed text-muted">
          Dowry/cruelty and economic offences reach the police weeks after the incident, while
          body offences are reported within a day — a key gap for victim-outreach policy.
        </p>
      </Panel>
    </div>
  );
}
