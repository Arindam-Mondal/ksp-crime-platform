import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Share2, Search, Users, GitBranch, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";
import Avatar from "../components/Avatar";
import ForceGraph from "../components/network/ForceGraph";
import { ListSkeleton } from "../components/Skeleton";

export default function Network() {
  const [selected, setSelected] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const navigate = useNavigate();

  const offenders = useQuery({ queryKey: ["topOffenders"], queryFn: api.topOffenders });
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
        eyebrow="Criminological Analysis"
        title="Network & Link Analysis"
        subtitle="Co-accused associations across FIRs — identities resolved from the Accused table"
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Panel
          icon={Users}
          title="Repeat offenders"
          subtitle={items.length ? `${items.length} ranked by activity` : undefined}
          bodyClassName="p-3"
        >
          <div className="relative mb-3">
            <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter offenders…"
              className="w-full rounded-lg border border-line bg-bg/60 py-2 pl-9 pr-3 text-sm text-white/90 outline-none transition-colors placeholder:text-muted focus:border-accent"
            />
          </div>

          {offenders.isPending ? (
            <ListSkeleton rows={9} />
          ) : (
            <ul className="max-h-[520px] space-y-1 overflow-auto pr-1">
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
                        <span className="tabular block text-[11px] text-muted">
                          {o.person_id} · {o.districts} district{o.districts === 1 ? "" : "s"} · {o.arrests} arrest{o.arrests === 1 ? "" : "s"}
                        </span>
                      </span>
                      <Badge variant={active ? "accent" : "neutral"}>{o.cases}</Badge>
                    </button>
                  </li>
                );
              })}
              {filtered.length === 0 && (
                <li className="px-3 py-8 text-center text-sm text-muted">No offenders match “{filter}”.</li>
              )}
            </ul>
          )}
        </Panel>

        <div className="lg:col-span-2">
          <Panel
            icon={GitBranch}
            title={selectedName ? `Association graph — ${selectedName}` : "Association graph"}
            subtitle={selected ? selected : undefined}
            bodyClassName="p-0"
            actions={
              stats && selected ? (
                <div className="hidden items-center gap-2 sm:flex">
                  <Badge variant="accent">{stats.associates} associates</Badge>
                  <Badge variant="neutral">{stats.links} links</Badge>
                  {stats.strongest > 1 && <Badge variant="info">×{stats.strongest} strongest</Badge>}
                </div>
              ) : undefined
            }
          >
            {!selected ? (
              <EmptyState
                icon={Share2}
                title="No offender selected"
                hint="Pick a repeat offender from the list to map their co-offending network. Click any node to open that person's full profile."
              />
            ) : ego.isPending ? (
              <div className="grid h-[520px] place-items-center">
                <span className="flex items-center gap-2 text-sm text-muted">
                  <RefreshCw size={14} className="animate-spin" /> Building graph…
                </span>
              </div>
            ) : ego.data && ego.data.nodes.length > 1 ? (
              <div className="relative">
                <ForceGraph
                  nodes={ego.data.nodes}
                  edges={ego.data.edges}
                  height={520}
                  onNodeClick={(id) => navigate(`/person/${id}`)}
                />
                <div className="pointer-events-none absolute bottom-3 left-3 z-10 rounded-xl border border-line bg-surface/85 px-3.5 py-2.5 text-[11px] backdrop-blur-md">
                  <div className="flex items-center gap-4">
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-danger" /> Focus offender
                    </span>
                    <span className="flex items-center gap-1.5 text-white/80">
                      <span className="h-2.5 w-2.5 rounded-full bg-accent" /> Associate
                    </span>
                  </div>
                  <div className="mt-1.5 flex items-center gap-2 text-muted">
                    <span className="h-[3px] w-7 rounded-full bg-gradient-to-r from-[#28344f] to-accent" />
                    edge thickness = shared FIRs
                  </div>
                </div>
                <div className="pointer-events-none absolute bottom-3 right-3 z-10 text-[11px] text-muted">
                  click a node → full profile · hover to isolate
                </div>
              </div>
            ) : (
              <EmptyState
                icon={GitBranch}
                title="No co-offenders found"
                hint={`${selectedName ?? "This person"} has no recorded co-offending links. Open their profile to see their crime history.`}
              >
                <button
                  onClick={() => selected && navigate(`/person/${selected}`)}
                  className="rounded-lg border border-line bg-surface-2/60 px-3.5 py-1.5 text-xs text-white/80 transition-colors hover:border-accent/40 hover:text-white"
                >
                  Open profile →
                </button>
              </EmptyState>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
