import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Share2, Search, Users, GitBranch, RefreshCw, Boxes } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";
import Avatar from "../components/Avatar";
import ForceGraph from "../components/network/ForceGraph";
import { ListSkeleton } from "../components/Skeleton";
import { useResponsiveHeight } from "../lib/useResponsiveHeight";
import { useT } from "../i18n";
import { useDataLabel } from "../i18n/data";

export default function Network() {
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();
  const graphHeight = useResponsiveHeight(520);
  const t = useT();
  const dl = useDataLabel();

  const offenders = useQuery({ queryKey: ["topOffenders"], queryFn: api.topOffenders });
  const communities = useQuery({ queryKey: ["communities"], queryFn: api.communities });
  const ego = useQuery({
    queryKey: ["ego", selected],
    queryFn: () => api.ego(selected!),
    enabled: !!selected,
  });

  const items = offenders.data?.items ?? [];
  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return q ? items.filter((o) => o.name.toLowerCase().includes(q)) : items;
  }, [items, filter]);

  const selectedName = items.find((o) => o.person_id === selected)?.name;

  const stats = useMemo(() => {
    if (!ego.data) return null;
    return {
      associates: Math.max(0, ego.data.nodes.length - 1),
      links: ego.data.edges.length,
      strongest: ego.data.edges.reduce((m, e) => Math.max(m, e.weight), 0),
    };
  }, [ego.data]);

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Share2}
        eyebrow={t("network.eyebrow")}
        title={t("network.title")}
        subtitle={t("network.subtitle")}
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel
          icon={Users}
          title={t("network.offenders")}
          subtitle={items.length ? t("network.offendersSubtitle", { count: items.length }) : undefined}
          bodyClassName="p-3"
        >
          <div className="relative mb-3">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={t("network.filterPlaceholder")}
              className="w-full rounded-lg border border-line bg-bg/60 py-2 pl-9 pr-3 text-sm text-white/90 outline-none transition-colors placeholder:text-muted focus:border-accent"
            />
          </div>

          {offenders.isPending ? (
            <ListSkeleton rows={9} />
          ) : (
            <ul className="max-h-[40svh] space-y-1 overflow-auto pr-1 lg:max-h-[520px]">
              {filtered.map((o) => {
                const active = selected === o.person_id;
                return (
                  <li key={o.person_id}>
                    <button
                      onClick={() => setSelected(o.person_id)}
                      className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-all duration-150 ${
                        active ? "bg-surface-2 ring-1 ring-accent/40" : "hover:bg-white/[0.04]"
                      }`}
                    >
                      <Avatar id={o.person_id} gender={o.gender} name={o.name} size={34} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-white/90">{o.name}</span>
                        {/* Person names and ids stay verbatim in both languages. */}
                        <span className="block text-[11px] tabular-nums text-muted">
                          {o.person_id} ·{" "}
                          {t(
                            o.districts === 1
                              ? "network.districtCount_one"
                              : "network.districtCount_other",
                            { count: o.districts }
                          )}{" "}
                          ·{" "}
                          {t(
                            o.arrests === 1 ? "network.arrestCount_one" : "network.arrestCount_other",
                            { count: o.arrests }
                          )}
                        </span>
                      </span>
                      <Badge variant={active ? "accent" : "neutral"}>{o.cases}</Badge>
                    </button>
                  </li>
                );
              })}
              {filtered.length === 0 && (
                <li className="px-3 py-8 text-center text-sm text-muted">
                  {t("network.noMatch", { filter })}
                </li>
              )}
            </ul>
          )}
        </Panel>

        <div className="lg:col-span-2">
          <Panel
            icon={GitBranch}
            title={selectedName ? t("network.graphFor", { name: selectedName }) : t("network.graph")}
            subtitle={selected ? selected : undefined}
            bodyClassName="p-0"
            actions={
              stats && selected ? (
                <div className="hidden items-center gap-2 sm:flex">
                  <Badge variant="accent">{t("network.associates", { count: stats.associates })}</Badge>
                  <Badge variant="neutral">{t("network.links", { count: stats.links })}</Badge>
                  {stats.strongest > 1 && (
                    <Badge variant="info">{t("network.strongest", { count: stats.strongest })}</Badge>
                  )}
                </div>
              ) : undefined
            }
          >
            {!selected ? (
              <EmptyState
                icon={Share2}
                title={t("network.noSelection")}
                hint={t("network.noSelectionHint")}
              />
            ) : ego.isPending ? (
              <div className="grid place-items-center" style={{ height: graphHeight }}>
                <span className="flex items-center gap-2 text-sm text-muted">
                  <RefreshCw size={14} className="animate-spin" /> {t("network.building")}
                </span>
              </div>
            ) : ego.data && ego.data.nodes.length > 1 ? (
              <div className="relative">
                <ForceGraph
                  nodes={ego.data.nodes}
                  edges={ego.data.edges}
                  height={graphHeight}
                  onNodeClick={(id) => navigate(`/person/${id}`)}
                />
                <div className="pointer-events-none absolute bottom-3 left-3 z-overlay hidden rounded-xl border border-line bg-surface/85 px-3.5 py-2.5 text-[11px] backdrop-blur-md sm:block">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-danger" /> {t("network.focusOffender")}
                    </span>
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-accent" /> {t("network.associate")}
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-muted">
                    <span className="h-[3px] w-7 rounded-full bg-gradient-to-r from-[#28344f] to-accent" />
                    {t("network.edgeThickness")}
                  </div>
                </div>
                <div className="pointer-events-none absolute bottom-3 right-3 z-overlay hidden text-[11px] text-muted sm:block">
                  {t("network.hintDesktop")}
                </div>
                {/* Touch has no hover, so the desktop hint would be a lie */}
                <div className="pointer-events-none absolute bottom-3 left-3 z-overlay text-[11px] text-muted sm:hidden">
                  {t("network.hintTouch")}
                </div>
              </div>
            ) : (
              <EmptyState
                icon={GitBranch}
                title={t("network.noCoOffenders")}
                hint={t("network.noCoOffendersHint", {
                  name: selectedName ?? t("network.thisPerson"),
                })}
              >
                <button
                  onClick={() => selected && navigate(`/person/${selected}`)}
                  className="rounded-lg border border-line bg-surface-2/60 px-3.5 py-1.5 text-xs text-white/80 transition-colors hover:border-accent/40 hover:text-white"
                >
                  {t("network.openProfile")}
                </button>
              </EmptyState>
            )}
          </Panel>
        </div>
      </div>

      <Panel
        icon={Boxes}
        title={t("network.clusters")}
        subtitle={
          communities.data
            ? t(
                communities.data.total_clusters === 1
                  ? "network.clustersSubtitle_one"
                  : "network.clustersSubtitle_other",
                { count: communities.data.total_clusters }
              )
            : t("network.clustersFallback")
        }
      >
        {communities.isPending ? (
          <ListSkeleton rows={4} />
        ) : communities.isError ? (
          <EmptyState
            icon={Boxes}
            title={t("network.clustersError")}
            hint={t("network.clustersErrorHint")}
          />
        ) : !communities.data || communities.data.clusters.length === 0 ? (
          <EmptyState icon={Boxes} title={t("network.noClusters")} hint={t("network.noClustersHint")} />
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {communities.data.clusters.map((c) => (
              <button
                key={c.id}
                onClick={() => setSelected(c.members[0])}
                className="rounded-xl border border-line bg-surface-2/40 p-3.5 text-left transition-colors hover:border-accent/40 hover:bg-surface-2/70"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-white/90">
                    {t("network.clusterName", { id: c.id })}
                  </span>
                  <Badge variant="accent">{t("network.clusterMembers", { count: c.size })}</Badge>
                </div>
                <div className="mt-1.5 text-[11px] text-muted">
                  {t("network.clusterMeta", {
                    cases: c.total_cases,
                    districts:
                      c.districts.slice(0, 3).map((n) => dl("district", n)).join(", ") +
                      (c.districts.length > 3 ? ` +${c.districts.length - 3}` : ""),
                  })}
                </div>
              </button>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
