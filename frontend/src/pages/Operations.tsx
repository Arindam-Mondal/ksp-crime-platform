import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { Lock, Landmark, UserCog, Timer, Building2, Scale } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";
import { Skeleton, TableSkeleton } from "../components/Skeleton";
import {
  CHART,
  tooltipStyle,
  tooltipLabelStyle,
  tooltipItemStyle,
  cursorFill,
  PALETTE,
} from "../components/charts/theme";

export default function Operations() {
  const arrests = useQuery({ queryKey: ["arrests"], queryFn: api.arrests });
  const officers = useQuery({ queryKey: ["officers"], queryFn: api.officers });
  const courts = useQuery({ queryKey: ["courts"], queryFn: api.courts });
  const timing = useQuery({ queryKey: ["investigation"], queryFn: api.investigation });

  const a = arrests.data;
  const o = officers.data;

  return (
    <div className="space-y-7">
      <PageHeader
        icon={UserCog}
        eyebrow="Investigation Operations"
        title="Arrests, Officers & Courts"
        subtitle="Process analytics from ArrestSurrender, Employee, ChargesheetDetails and Court"
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          label="Arrest / surrender events"
          value={a ? a.total.toLocaleString() : "—"}
          icon={Lock}
          accent="warning"
          caption={a ? `${a.arrests.toLocaleString()} arrests · ${a.surrenders.toLocaleString()} surrenders` : "Loading…"}
        />
        <StatCard
          label="Out-of-state arrests"
          value={a ? a.out_of_state.toLocaleString() : "—"}
          icon={Landmark}
          accent="info"
          caption="Made outside Karnataka"
        />
        <StatCard
          label="Police strength"
          value={o ? o.total_employees.toLocaleString() : "—"}
          icon={UserCog}
          caption={o ? `${o.active_investigators} active investigators` : "Loading…"}
        />
        <StatCard
          label="Courts in pipeline"
          value={courts.data ? String(courts.data.total_courts) : "—"}
          icon={Scale}
          accent="success"
          caption="With at least one committed case"
        />
      </div>

      {/* Arrest trend + days to arrest */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Lock} title="Arrest trend" subtitle="Monthly arrest & surrender events">
          <div style={{ height: 260 }}>
            {arrests.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={a?.by_month ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                  <defs>
                    <linearGradient id="arrTrend" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="month" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} minTickGap={24} />
                  <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                  <Area type="monotone" dataKey="count" stroke="#f59e0b" strokeWidth={2} fill="url(#arrTrend)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>

        <Panel icon={Timer} title="Median days to first arrest" subtitle="From FIR registration, by crime head">
          <div style={{ height: 260 }}>
            {arrests.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={a?.days_to_arrest_by_head ?? []} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} unit="d" />
                  <YAxis type="category" dataKey="crime_head" tick={{ ...CHART.axisTick, fontSize: 10 }} tickLine={false} axisLine={false} width={168} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} formatter={(v: any) => [`${v} days`, "median"]} />
                  <Bar dataKey="median_days_to_arrest" radius={[0, 4, 4, 0]} maxBarSize={16}>
                    {(a?.days_to_arrest_by_head ?? []).map((_, i) => (
                      <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>

      {/* Officer workload */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Panel icon={UserCog} title="Force composition" subtitle="Employees by rank">
          {officers.isPending ? (
            <Skeleton className="h-[300px] w-full" />
          ) : (
            <ul className="space-y-2">
              {(o?.by_rank ?? []).map((r) => {
                const maxN = o?.by_rank[0]?.count || 1;
                return (
                  <li key={r.rank}>
                    <div className="mb-0.5 flex items-baseline justify-between text-xs">
                      <span className="text-white/85">{r.rank}</span>
                      <span className="tabular text-muted">{r.count}</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-bg/80">
                      <div className="h-full rounded-full bg-gradient-to-r from-accent/50 to-accent" style={{ width: `${(r.count / maxN) * 100}%` }} />
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        <div className="xl:col-span-2">
          <Panel
            icon={UserCog}
            title="Top investigating officers"
            subtitle="Chargesheets filed & arrests made (Employee ⋈ ChargesheetDetails ⋈ ArrestSurrender)"
          >
            {officers.isPending ? (
              <TableSkeleton rows={8} />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                      <th className="py-2.5 pr-4">Officer</th>
                      <th className="py-2.5 pr-4">Rank</th>
                      <th className="py-2.5 pr-4">Station</th>
                      <th className="py-2.5 pr-4">Chargesheets</th>
                      <th className="py-2.5 pr-4">Arrests</th>
                      <th className="py-2.5">CS success</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(o?.top ?? []).map((r) => (
                      <tr key={r.employee_id} className="border-b border-line/60 transition-colors hover:bg-white/[0.025]">
                        <td className="py-2.5 pr-4 font-medium text-white/90">{r.name}</td>
                        <td className="py-2.5 pr-4 text-white/70">{r.rank}</td>
                        <td className="py-2.5 pr-4 text-xs text-muted">{r.station}</td>
                        <td className="tabular py-2.5 pr-4 text-white/70">{r.chargesheets}</td>
                        <td className="tabular py-2.5 pr-4 text-white/70">{r.arrests}</td>
                        <td className="py-2.5">
                          <Badge variant={r.chargesheet_success >= 70 ? "success" : r.chargesheet_success >= 50 ? "warning" : "neutral"}>
                            {r.chargesheet_success}%
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>
      </div>

      {/* Court caseload + days to chargesheet */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Panel icon={Scale} title="Court caseload" subtitle="Cases committed to trial, per court">
          {courts.isPending ? (
            <TableSkeleton rows={8} />
          ) : (
            <div className="max-h-[380px] overflow-auto pr-1">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                    <th className="py-2.5 pr-4">Court</th>
                    <th className="py-2.5 pr-4">Cases</th>
                    <th className="py-2.5 pr-4">Pending</th>
                    <th className="py-2.5 pr-4">Convicted</th>
                    <th className="py-2.5">Acquitted</th>
                  </tr>
                </thead>
                <tbody>
                  {(courts.data?.items ?? []).map((c) => (
                    <tr key={c.court} className="border-b border-line/60 transition-colors hover:bg-white/[0.025]">
                      <td className="py-2.5 pr-4 text-xs font-medium text-white/85">{c.court}</td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{c.cases.toLocaleString()}</td>
                      <td className="tabular py-2.5 pr-4 text-warning">{c.pending_trial.toLocaleString()}</td>
                      <td className="tabular py-2.5 pr-4 text-success">{c.convicted}</td>
                      <td className="tabular py-2.5 text-muted">{c.acquitted}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel icon={Building2} title="Median days to chargesheet" subtitle="From registration to A-type final report, by crime head">
          <div style={{ height: 340 }}>
            {timing.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timing.data?.days_to_chargesheet ?? []} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                  <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} unit="d" />
                  <YAxis type="category" dataKey="crime_head" tick={{ ...CHART.axisTick, fontSize: 10 }} tickLine={false} axisLine={false} width={168} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} formatter={(v: any) => [`${v} days`, "median"]} />
                  <Bar dataKey="median_days" radius={[0, 4, 4, 0]} maxBarSize={16} fill="#a78bfa" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
