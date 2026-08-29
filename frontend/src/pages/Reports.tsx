import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  FileText, Sparkles, Download, Loader2, Siren, Radar, Crosshair, Users, ShieldCheck,
} from "lucide-react";
import { api, IntelReport } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";
import { useLang, useT, useTDynamic, type TranslationKey } from "../i18n";
import { translateParams, useDataLabel } from "../i18n/data";

type Scope = "state" | "district" | "person";

const SCOPE_KEY: Record<Scope, TranslationKey> = {
  state: "report.scope.state",
  district: "report.scope.district",
  person: "report.scope.person",
};

export default function Reports() {
  const [scope, setScope] = useState<Scope>("state");
  const [districtId, setDistrictId] = useState("");
  const [personId, setPersonId] = useState("");
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta });
  const t = useT();
  const tD = useTDynamic();
  const d = useDataLabel();
  const { lang } = useLang();

  const gen = useMutation<IntelReport, Error, void>({
    mutationFn: () =>
      api.report(
        scope,
        scope === "district" ? districtId : scope === "person" ? personId : undefined,
        lang
      ),
  });

  const canGenerate = scope === "state" || (scope === "district" && districtId) || (scope === "person" && personId.trim());
  const r = gen.data;

  return (
    <div className="space-y-7">
      <div className="no-print space-y-7">
        <PageHeader
          icon={FileText}
          eyebrow={t("report.eyebrow")}
          title={t("report.title")}
          subtitle={t("report.subtitle")}
        />

        <Panel icon={Sparkles} title={t("report.scopePanel")}>
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">
                {t("report.scope")}
              </label>
              <div className="flex items-center rounded-lg border border-line p-0.5">
                {(["state", "district", "person"] as Scope[]).map((s) => (
                  // `capitalize` dropped: the labels are now properly-cased in both
                  // languages, and the utility is a no-op on Kannada anyway.
                  <button key={s} onClick={() => setScope(s)}
                    className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${scope === s ? "bg-surface-2 text-white" : "text-muted hover:text-white/80"}`}>
                    {t(SCOPE_KEY[s])}
                  </button>
                ))}
              </div>
            </div>

            {scope === "district" && (
              <div>
                <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">
                  {t("common.district")}
                </label>
                {/* The option *value* stays the English district name — it is the id the
                    report endpoint filters on; only the visible text is translated. */}
                <select value={districtId} onChange={(e) => setDistrictId(e.target.value)}
                  className="rounded-lg border border-line bg-bg/60 px-3 py-2 text-sm text-white/90 outline-none focus:border-accent">
                  <option value="">{t("report.selectDistrict")}</option>
                  {(meta.data?.districts ?? []).map((name) => (
                    <option key={name} value={name}>{d("district", name)}</option>
                  ))}
                </select>
              </div>
            )}

            {scope === "person" && (
              <div>
                <label className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-muted">
                  {t("report.personId")}
                </label>
                <input value={personId} onChange={(e) => setPersonId(e.target.value)}
                  placeholder={t("report.personIdPlaceholder")}
                  className="rounded-lg border border-line bg-bg/60 px-3 py-2 text-sm text-white/90 outline-none placeholder:text-muted focus:border-accent" />
              </div>
            )}

            <button
              onClick={() => gen.mutate()}
              disabled={!canGenerate || gen.isPending}
              className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white shadow-glow transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50">
              {gen.isPending ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {gen.isPending ? t("report.generating") : t("report.generate")}
            </button>

            {r && (
              <button onClick={() => window.print()}
                className="inline-flex items-center gap-2 rounded-xl border border-line px-4 py-2.5 text-sm font-medium text-white/90 transition-colors hover:border-line-strong">
                <Download size={15} /> {t("report.downloadPdf")}
              </button>
            )}
          </div>
          {gen.isError && <p className="mt-3 text-sm text-danger">{gen.error.message}</p>}
        </Panel>
      </div>

      {!r && !gen.isPending && (
        <Panel>
          <EmptyState icon={FileText} title={t("report.emptyTitle")} hint={t("report.emptyHint")} />
        </Panel>
      )}

      {/* The printable report sheet */}
      {r && (
        <div className="print-sheet rounded-2xl border border-line bg-surface/80 p-7 shadow-card">
          {/* letterhead */}
          <div className="flex items-start justify-between border-b border-line pb-4">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-accent-soft print-muted">
                {t("report.letterhead")}
              </div>
              <h2 className="mt-1 text-2xl font-bold tracking-tight text-white">{t("report.heading")}</h2>
              {/* A district subject translates; a person's name never does. */}
              <div className="mt-1 text-sm text-muted print-muted">
                {r.subject_kind === "district"
                  ? d("district", r.subject)
                  : r.subject_kind === "state"
                  ? t("report.stateWide")
                  : r.subject}
              </div>
            </div>
            <div className="text-right text-xs text-muted print-muted">
              <div>{t("report.generatedAt", { at: r.generated_at })}</div>
              <div className="mt-1">
                {t("report.modelLine", { provider: r.provider, model: r.model })}
              </div>
            </div>
          </div>

          {/* narrative */}
          <div className="mt-5">
            <SectionTitle icon={Sparkles}>{t("report.executiveSummary")}</SectionTitle>
            <p className="mt-2 text-sm leading-relaxed text-white/85">{r.narrative}</p>
          </div>

          {/* KPIs */}
          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {r.kpis.map((k) => (
              <div key={k.label} className="rounded-xl border border-line px-3 py-2.5">
                <div className="text-[10px] uppercase tracking-wider text-muted print-muted">
                  {k.label_key ? tD(k.label_key, undefined, k.label) : k.label}
                </div>
                <div className="tabular mt-0.5 text-lg font-semibold text-white">{k.value}</div>
              </div>
            ))}
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            {/* hotspots */}
            <div>
              <SectionTitle icon={Crosshair}>{t("report.topHotspots")}</SectionTitle>
              <table className="mt-2 w-full text-sm">
                <tbody>
                  {r.hotspots.map((h) => (
                    <tr key={h.district} className="border-b border-line/60">
                      <td className="py-1.5 font-medium text-white/90">{d("district", h.district)}</td>
                      <td className="tabular py-1.5 text-right text-white/70">{h.cases.toLocaleString()}</td>
                      <td className="py-1.5 pl-3 text-right">
                        <Badge variant="warning">{t("report.riskBadge", { score: h.risk_score })}</Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* offenders */}
            <div>
              <SectionTitle icon={Users}>{t("report.keyOffenders")}</SectionTitle>
              <table className="mt-2 w-full text-sm">
                <tbody>
                  {r.offenders.map((o) => (
                    <tr key={o.person_id} className="border-b border-line/60">
                      <td className="py-1.5 font-medium text-white/90">{o.name}</td>
                      <td className="tabular py-1.5 text-muted print-muted">{o.person_id}</td>
                      <td className="tabular py-1.5 text-right text-white/70">
                        {t("report.firCount", { count: o.cases })}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* alerts */}
          {r.alerts.length > 0 && (
            <div className="mt-6">
              <SectionTitle icon={Siren}>{t("report.activeAlerts")}</SectionTitle>
              <ul className="mt-2 space-y-1.5 text-sm">
                {r.alerts.map((a) => (
                  <li key={`${a.district}-${a.sub_head}`} className="flex items-center gap-2">
                    {/* The English severity stays the variant lookup key. */}
                    <Badge variant={a.severity === "Critical" ? "danger" : "warning"}>
                      {d("severity", a.severity)}
                    </Badge>
                    <span className="text-white/85">
                      {t("report.alertLine", {
                        subHead: d("crimeSubHead", a.sub_head),
                        ratio: a.ratio,
                        district: d("district", a.district),
                      })}
                    </span>
                    <span className="ml-auto tabular-nums text-muted print-muted">
                      {t("report.recentIn30d", { count: a.recent })}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* anomalies */}
          {r.anomalies.length > 0 && (
            <div className="mt-6">
              <SectionTitle icon={Radar}>{t("report.anomalies")}</SectionTitle>
              <ul className="mt-2 space-y-1.5 text-sm text-white/85">
                {r.anomalies.map((a, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <Badge variant="info">{a.z}σ</Badge>
                    <span>
                      {a.template
                        ? tD(a.template, translateParams(a.params, d), a.description)
                        : a.description}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mt-6 flex items-center gap-1.5 border-t border-line pt-3 text-[11px] text-muted print-muted">
            <ShieldCheck size={12} /> {t("report.footer")}
          </div>
        </div>
      )}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: any; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-accent-soft print-muted">
      <Icon size={13} /> {children}
    </div>
  );
}
