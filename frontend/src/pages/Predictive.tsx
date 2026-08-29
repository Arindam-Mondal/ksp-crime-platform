import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, ShieldAlert, ArrowUpDown, Radar, Clock, BarChart2 } from "lucide-react";
import { api, DistrictStat } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import { TableSkeleton, ListSkeleton } from "../components/Skeleton";
import { useLang, useT, useTDynamic } from "../i18n";
import { translateParams, useDataLabel } from "../i18n/data";

type SortKey = "risk_score" | "cases" | "heinous_share" | "pendency_rate";

/** `label` stays the English tier name: it is the lookup key into the severity map and
 *  the value `highCount` counts on. Translate it only where it is painted. */
function riskTier(score: number, max: number): { label: string; variant: "danger" | "warning" | "success" } {
  const r = max ? score / max : 0;
  if (r >= 0.66) return { label: "High", variant: "danger" };
  if (r >= 0.33) return { label: "Medium", variant: "warning" };
  return { label: "Low", variant: "success" };
}

const SEV_VARIANT: Record<string, "danger" | "warning" | "info"> = {
  High: "danger",
  Medium: "warning",
  Low: "info",
};

export default function Predictive() {
  const risk = useQuery({ queryKey: ["riskScores"], queryFn: api.riskScores });
  const anomalies = useQuery({ queryKey: ["anomalies"], queryFn: api.anomalies });
  const [sort, setSort] = useState<SortKey>("risk_score");
  const t = useT();
  const tD = useTDynamic();
  const d = useDataLabel();
  const { lang } = useLang();

  const items = risk.data?.items ?? [];
  const max = items.reduce((m, r) => Math.max(m, r.risk_score), 0) || 1;

  const sorted = useMemo(
    () => [...items].sort((a: DistrictStat, b: DistrictStat) => (b[sort] as number) - (a[sort] as number)),
    [items, sort]
  );

  const highCount = items.filter((r) => riskTier(r.risk_score, max).label === "High").length;

  // `method` is free-form English prose from the model layer, so there is nothing to
  // key a translation off; Kannada falls back to the static description of the ranking.
  const subtitle = lang === "kn" ? t("predictive.subtitle") : risk.data?.method ?? t("predictive.subtitle");

  const SortBtn = ({ k, children }: { k: SortKey; children: string }) => (
    <button
      onClick={() => setSort(k)}
      className={`seg-btn -mx-1 inline-flex items-center gap-1 rounded px-1 py-1.5 transition-colors ${
        sort === k ? "text-accent-soft" : "text-muted hover:text-white/80"
      }`}
    >
      {children}
      <ArrowUpDown size={12} />
    </button>
  );

  return (
    <div className="space-y-7">
      <PageHeader
        icon={TrendingUp}
        eyebrow={t("predictive.eyebrow")}
        title={t("predictive.title")}
        subtitle={subtitle}
        actions={
          items.length ? (
            <Badge variant="danger" dot>
              {t("predictive.highRisk", { count: highCount })}
            </Badge>
          ) : undefined
        }
      />

      <Panel
        icon={ShieldAlert}
        title={t("predictive.riskTable.title")}
        subtitle={t("predictive.riskTable.subtitle")}
      >
        {risk.isPending ? (
          <TableSkeleton rows={10} />
        ) : (
          <div className="table-scroll">
            <table className="w-full min-w-[880px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                  <th className="py-2.5 pr-4 font-semibold">{t("predictive.col.rank")}</th>
                  <th className="py-2.5 pr-4 font-semibold">{t("common.district")}</th>
                  <th className="py-2.5 pr-4 font-semibold">
                    <SortBtn k="cases">{t("predictive.col.cases")}</SortBtn>
                  </th>
                  <th className="py-2.5 pr-4 font-semibold" title={t("predictive.col.rate100kHint")}>
                    {t("predictive.col.rate100k")}
                  </th>
                  <th className="py-2.5 pr-4 font-semibold">
                    <SortBtn k="heinous_share">{t("predictive.col.heinous")}</SortBtn>
                  </th>
                  <th className="py-2.5 pr-4 font-semibold">
                    <SortBtn k="pendency_rate">{t("predictive.col.pendency")}</SortBtn>
                  </th>
                  <th className="py-2.5 pr-4 font-semibold">{t("predictive.col.chargesheetRate")}</th>
                  <th className="py-2.5 pr-4 font-semibold">{t("predictive.col.recent90d")}</th>
                  <th className="py-2.5 pr-4 font-semibold">{t("predictive.col.tier")}</th>
                  <th className="w-1/4 py-2.5 font-semibold">
                    <SortBtn k="risk_score">{t("predictive.col.riskScore")}</SortBtn>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((r, i) => {
                  const tier = riskTier(r.risk_score, max);
                  return (
                    <tr
                      key={r.district}
                      className="border-b border-line/60 transition-colors hover:bg-white/[0.025]"
                    >
                      <td className="tabular py-2.5 pr-4 text-muted">{String(i + 1).padStart(2, "0")}</td>
                      <td className="py-2.5 pr-4 font-medium text-white/90">
                        {d("district", r.district)}
                      </td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{r.cases.toLocaleString()}</td>
                      <td className="tabular py-2.5 pr-4 text-white/70">
                        {r.per_100k ?? t("common.none")}
                      </td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{r.heinous_share}%</td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{r.pendency_rate}%</td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{r.chargesheet_rate}%</td>
                      <td className="tabular py-2.5 pr-4 text-white/70">{r.recent_90d}</td>
                      <td className="py-2.5 pr-4">
                        <Badge variant={tier.variant}>{d("severity", tier.label)}</Badge>
                      </td>
                      <td className="py-2.5">
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-bg/80">
                            <div
                              className={`h-full rounded-full ${
                                tier.variant === "danger"
                                  ? "bg-gradient-to-r from-danger/60 to-danger"
                                  : tier.variant === "warning"
                                  ? "bg-gradient-to-r from-warning/60 to-warning"
                                  : "bg-gradient-to-r from-success/60 to-success"
                              }`}
                              style={{ width: `${(r.risk_score / max) * 100}%` }}
                            />
                          </div>
                          <span className="tabular w-12 shrink-0 text-right text-white/80">
                            {r.risk_score.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                          </span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* Anomaly call-outs */}
      <Panel
        icon={Radar}
        title={t("predictive.anomalies.title")}
        subtitle={t("predictive.anomalies.subtitle")}
        actions={
          anomalies.data ? (
            <Badge variant="warning" dot>
              {t("predictive.anomalies.flagged", { count: anomalies.data.count })}
            </Badge>
          ) : undefined
        }
      >
        {anomalies.isPending ? (
          <ListSkeleton rows={5} />
        ) : (anomalies.data?.items.length ?? 0) === 0 ? (
          <p className="py-6 text-center text-sm text-muted">{t("predictive.anomalies.none")}</p>
        ) : (
          <ul className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {anomalies.data!.items.map((a, i) => {
              const Icon = a.kind === "temporal" ? Clock : BarChart2;
              return (
                <li key={i} className="flex items-start gap-3 rounded-xl border border-line bg-bg/30 px-4 py-3">
                  <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-surface-2 text-accent-soft">
                    <Icon size={15} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {/* The subject is a district for volume/multivariate anomalies and
                          a crime sub-head for temporal ones. */}
                      <span className="truncate text-sm font-semibold text-white/90">
                        {d(a.kind === "temporal" ? "crimeSubHead" : "district", a.subject)}
                      </span>
                      <Badge variant="neutral">{a.period}</Badge>
                    </div>
                    <p className="mt-0.5 text-xs leading-relaxed text-muted">
                      {a.template
                        ? tD(a.template, translateParams(a.params, d), a.description)
                        : a.description}
                    </p>
                  </div>
                  <Badge variant={SEV_VARIANT[a.severity] ?? "neutral"}>{a.z}σ</Badge>
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}
