import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";
import {
  Building2, TrendingUp, Crosshair, ShieldAlert, ArrowUpDown, Landmark, Scale,
} from "lucide-react";
import { api, SocioItem } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import Badge from "../components/Badge";
import { Skeleton, TableSkeleton } from "../components/Skeleton";
import { CHART, tooltipStyle } from "../components/charts/theme";
import { useT, type TFunction, type TranslationKey } from "../i18n";
import { useDataLabel } from "../i18n/data";

// Least-squares fit over {x,y} points → endpoints for a trend segment.
function linreg(pts: { x: number; y: number }[]) {
  const n = pts.length;
  if (n < 2) return null;
  const mx = pts.reduce((s, p) => s + p.x, 0) / n;
  const my = pts.reduce((s, p) => s + p.y, 0) / n;
  const sxx = pts.reduce((s, p) => s + (p.x - mx) ** 2, 0);
  if (sxx <= 0) return null;
  const sxy = pts.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0);
  const slope = sxy / sxx;
  const intercept = my - slope * mx;
  const xs = pts.map((p) => p.x);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  return { x0, y0: slope * x0 + intercept, x1, y1: slope * x1 + intercept };
}

/** Returns a catalog key rather than a literal, so the badge variant stays driven by the
 *  number while the wording follows the reader's language. */
function strength(r: number | null): {
  labelKey: TranslationKey;
  variant: "danger" | "warning" | "info" | "neutral";
} {
  if (r == null) return { labelKey: "sociological.strength.na", variant: "neutral" };
  const a = Math.abs(r);
  if (a >= 0.5) return { labelKey: "sociological.strength.strong", variant: "danger" };
  if (a >= 0.3) return { labelKey: "sociological.strength.moderate", variant: "warning" };
  return { labelKey: "sociological.strength.weak", variant: "info" };
}

/** Built from a whole-sentence template per direction — Kannada orders the clause
 *  differently, so "rises with" can't be a swappable middle fragment. */
function reading(t: TFunction, nameKey: TranslationKey, r: number | null): string {
  if (r == null) return t("sociological.reading.noData");
  const a = Math.abs(r);
  const mag = t(
    a >= 0.5
      ? "sociological.magnitude.strongly"
      : a >= 0.3
      ? "sociological.magnitude.moderately"
      : "sociological.magnitude.weakly"
  );
  return t(r >= 0 ? "sociological.reading.rises" : "sociological.reading.falls", {
    mag,
    name: t(nameKey),
    r: r.toFixed(2),
  });
}

const AXIS = { x: { urban: "urban_pct", lit: "literacy_pct", den: "pop_density" } } as const;

/** Correlation factor -> its catalog key, so `strongest` can name itself in either language. */
const FACTOR_KEY = {
  urbanization: "sociological.factor.urbanization",
  literacy: "sociological.factor.literacy",
  density: "sociological.factor.density",
} as const satisfies Record<string, TranslationKey>;

export default function Sociological() {
  const socio = useQuery({ queryKey: ["socioeconomic"], queryFn: api.socioeconomic });
  const items = socio.data?.items ?? [];
  const corr = socio.data?.correlations;
  const t = useT();
  const dl = useDataLabel();

  // Statewide rate (population-weighted), and the biggest "hidden hotspot" mover.
  const totals = useMemo(() => {
    const cases = items.reduce((s, i) => s + i.cases, 0);
    const pop = items.reduce((s, i) => s + i.population, 0);
    const rate = pop ? (cases / pop) * 100_000 : 0;
    const hidden = [...items].sort((a, b) => b.rank_shift - a.rank_shift)[0];
    return { rate, hidden };
  }, [items]);

  const strongest = useMemo(() => {
    if (!corr) return null;
    const entries: [keyof typeof FACTOR_KEY, number | null][] = [
      ["urbanization", corr.urbanization], ["literacy", corr.literacy], ["density", corr.density],
    ];
    return entries
      .filter((e) => e[1] != null)
      .sort((a, b) => Math.abs(b[1]!) - Math.abs(a[1]!))[0] ?? null;
  }, [corr]);

  // Districts whose per-capita rank is materially worse than their volume rank.
  const hidden = useMemo(
    () => [...items].filter((i) => i.rank_shift >= 3).sort((a, b) => b.rank_shift - a.rank_shift),
    [items]
  );

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Building2}
        eyebrow={t("sociological.eyebrow")}
        title={t("sociological.title")}
        subtitle={t("sociological.subtitle")}
        actions={
          strongest ? (
            <Badge variant={strength(strongest[1]).variant} dot>
              {t("sociological.strongestCorrelate", { factor: t(FACTOR_KEY[strongest[0]]) })}
            </Badge>
          ) : undefined
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label={t("sociological.stateRate")}
          value={socio.data ? totals.rate.toFixed(1) : t("common.none")}
          icon={Scale}
          caption={t("sociological.stateRateCaption")}
        />
        <StatCard
          label={t("sociological.highestRate")}
          value={items[0] ? dl("district", items[0].district) : t("common.none")}
          icon={Crosshair}
          accent="danger"
          caption={
            items[0]
              ? t("sociological.highestRateCaption", {
                  rate: items[0].per_100k,
                  cases: items[0].cases.toLocaleString(),
                })
              : undefined
          }
        />
        <StatCard
          label={t("sociological.urbanCrime")}
          value={corr?.urbanization != null ? `r ${corr.urbanization.toFixed(2)}` : t("common.none")}
          icon={TrendingUp}
          accent="info"
          caption={t("sociological.correlationCaption", {
            strength: t(strength(corr?.urbanization ?? null).labelKey),
          })}
        />
        <StatCard
          label={t("sociological.underrated")}
          value={totals.hidden ? dl("district", totals.hidden.district) : t("common.none")}
          icon={ShieldAlert}
          accent="warning"
          caption={
            totals.hidden
              ? t("sociological.underratedCaption", { shift: totals.hidden.rank_shift })
              : undefined
          }
        />
      </div>

      {/* Signature: the reordering — volume rank vs per-capita rank */}
      <Panel
        icon={ArrowUpDown}
        title={t("sociological.rankShift")}
        subtitle={t("sociological.rankShiftSubtitle")}
      >
        {socio.isPending ? (
          <TableSkeleton rows={6} />
        ) : hidden.length === 0 ? (
          <p className="py-4 text-sm text-muted">{t("sociological.noShift")}</p>
        ) : (
          <ul className="space-y-2">
            {hidden.slice(0, 8).map((d) => (
              <li key={d.district} className="flex items-center gap-4 rounded-xl border border-line bg-bg/30 px-4 py-2.5">
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-white/90">
                  {dl("district", d.district)}
                </span>
                {/* rank movement */}
                <div className="flex items-center gap-2 text-xs tabular-nums">
                  <span className="text-muted">{t("sociological.volRank", { rank: d.volume_rank })}</span>
                  <span className="text-warning">→</span>
                  <span className="font-semibold text-white/90">
                    {t("sociological.rateRank", { rank: d.rate_rank })}
                  </span>
                </div>
                <div className="hidden w-40 items-center gap-2 sm:flex">
                  <span className="w-16 text-right text-xs tabular-nums text-muted">
                    {t("sociological.per100k", { rate: d.per_100k })}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg/80">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-warning/50 to-warning"
                      style={{ width: `${Math.min(100, (d.per_100k / (items[0]?.per_100k || 1)) * 100)}%` }}
                    />
                  </div>
                </div>
                <Badge variant="warning" dot>+{d.rank_shift}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Correlation scatters */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <ScatterPanel
          title={t("sociological.scatterUrban")}
          xKey={AXIS.x.urban}
          xLabel={t("sociological.axis.urban")}
          items={items}
          r={corr?.urbanization ?? null}
          loading={socio.isPending}
          readingText={reading(t, "sociological.factor.urbanization", corr?.urbanization ?? null)}
        />
        <ScatterPanel
          title={t("sociological.scatterLiteracy")}
          xKey={AXIS.x.lit}
          xLabel={t("sociological.axis.literacy")}
          items={items}
          r={corr?.literacy ?? null}
          loading={socio.isPending}
          readingText={reading(t, "sociological.factor.literacy", corr?.literacy ?? null)}
        />
        <ScatterPanel
          title={t("sociological.scatterDensity")}
          xKey={AXIS.x.den}
          xLabel={t("sociological.axis.density")}
          items={items}
          r={corr?.density ?? null}
          loading={socio.isPending}
          readingText={reading(t, "sociological.factor.density", corr?.density ?? null)}
        />
      </div>

      {/* Per-capita ranking table */}
      <Panel
        icon={Landmark}
        title={t("sociological.rankingTitle")}
        // `method` is free-form English prose from the analytics layer; shown only where
        // it can be read, same treatment as the risk model description on Predictive.
        subtitle={socio.data?.method}
      >
        {socio.isPending ? (
          <TableSkeleton rows={10} />
        ) : (
          <div className="table-scroll">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs font-semibold uppercase tracking-wider text-muted">
                  <th className="py-2.5 pr-4">{t("sociological.col.rank")}</th>
                  <th className="py-2.5 pr-4">{t("common.district")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.cases")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.population")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.rate")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.urban")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.literacy")}</th>
                  <th className="py-2.5 pr-4">{t("sociological.col.density")}</th>
                  <th className="py-2.5">{t("sociological.col.vsVolume")}</th>
                </tr>
              </thead>
              <tbody>
                {items.map((d, i) => (
                  <tr key={d.district} className="border-b border-line/60 transition-colors hover:bg-white/[0.025]">
                    <td className="tabular py-2.5 pr-4 text-muted">{String(i + 1).padStart(2, "0")}</td>
                    <td className="py-2.5 pr-4 font-medium text-white/90">{dl("district", d.district)}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{d.cases.toLocaleString()}</td>
                    <td className="tabular py-2.5 pr-4 text-white/60">{d.population.toLocaleString()}</td>
                    <td className="tabular py-2.5 pr-4 font-semibold text-white/90">{d.per_100k}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{d.urban_pct}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{d.literacy_pct}</td>
                    <td className="tabular py-2.5 pr-4 text-white/70">{d.pop_density.toLocaleString()}</td>
                    <td className="py-2.5">
                      {d.rank_shift > 0 ? (
                        <span className="tabular text-xs text-warning">▲ {d.rank_shift}</span>
                      ) : d.rank_shift < 0 ? (
                        <span className="tabular text-xs text-info">▼ {Math.abs(d.rank_shift)}</span>
                      ) : (
                        <span className="text-xs text-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs leading-relaxed text-muted">{t("sociological.tableNote")}</p>
          </div>
        )}
      </Panel>
    </div>
  );
}

function ScatterPanel({
  title, xKey, xLabel, items, r, loading, readingText,
}: {
  title: string;
  xKey: "urban_pct" | "literacy_pct" | "pop_density";
  xLabel: string;
  items: SocioItem[];
  r: number | null;
  loading: boolean;
  readingText: string;
}) {
  const t = useT();
  const dl = useDataLabel();
  const pts = items.map((d) => ({ x: d[xKey], y: d.per_100k, district: dl("district", d.district) }));
  const fit = linreg(pts);
  const s = strength(r);

  return (
    <Panel
      icon={TrendingUp}
      title={title}
      actions={
        <Badge variant={s.variant}>
          {r != null ? `r ${r.toFixed(2)}` : t("sociological.strength.na")} · {t(s.labelKey)}
        </Badge>
      }
    >
      <div className="h-[200px] sm:h-[220px]">
        {loading ? (
          <Skeleton className="h-full w-full" />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ left: 4, right: 12, top: 8, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
              <XAxis
                type="number" dataKey="x" name={xLabel}
                tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }}
                label={{ value: xLabel, position: "insideBottom", offset: -8, fill: "#8a94ad", fontSize: 10 }}
              />
              <YAxis
                type="number" dataKey="y" name={t("sociological.axis.rate")}
                tick={CHART.axisTick} tickLine={false} axisLine={false} width={34}
              />
              <ZAxis range={[50, 50]} />
              <Tooltip
                cursor={{ strokeDasharray: "3 3", stroke: CHART.grid }}
                content={({ payload }) => {
                  const p = payload?.[0]?.payload as any;
                  if (!p) return null;
                  return (
                    <div style={tooltipStyle as any}>
                      <div style={{ color: "#b6c0d8", fontWeight: 600 }}>{p.district}</div>
                      {/* Inline style, so the Kannada face has to be named here too. */}
                      <div
                        style={{
                          color: "#e6eaf2",
                          fontFamily: "JetBrains Mono, 'Noto Sans Kannada', monospace",
                        }}
                      >
                        {t("sociological.tooltip", { rate: p.y, axis: xLabel, value: p.x })}
                      </div>
                    </div>
                  );
                }}
              />
              {fit && (
                <ReferenceLine
                  segment={[{ x: fit.x0, y: fit.y0 }, { x: fit.x1, y: fit.y1 }]}
                  stroke={CHART.accentSoft} strokeDasharray="5 4" strokeWidth={1.5} ifOverflow="extendDomain"
                />
              )}
              <Scatter data={pts} fill={CHART.accent}>
                {pts.map((_, i) => <Cell key={i} fill={CHART.accent} fillOpacity={0.75} />)}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        )}
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">{readingText}</p>
    </Panel>
  );
}
