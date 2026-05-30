import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import { api } from "../lib/api";
import Panel from "../components/Panel";

export default function Network() {
  const [selected, setSelected] = useState<string | null>(null);
  const offenders = useQuery({ queryKey: ["topOffenders"], queryFn: api.topOffenders });
  const ego = useQuery({
    queryKey: ["ego", selected],
    queryFn: () => api.ego(selected!),
    enabled: !!selected,
  });

  const graphEl = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!graphEl.current || !ego.data) return;
    cyRef.current?.destroy();
    cyRef.current = cytoscape({
      container: graphEl.current,
      elements: [
        ...ego.data.nodes.map((n) => ({
          data: { id: n.id, label: n.name },
        })),
        ...ego.data.edges.map((e) => ({
          data: { id: `${e.source}-${e.target}`, source: e.source, target: e.target, weight: e.weight },
        })),
      ],
      style: [
        { selector: "node", style: { label: "data(label)", "background-color": "#3b82f6", color: "#e5e7eb", "font-size": 9 } },
        { selector: `node[id = "${ego.data.root}"]`, style: { "background-color": "#ef4444", width: 26, height: 26 } },
        { selector: "edge", style: { width: "mapData(weight, 1, 5, 1, 6)", "line-color": "#64748b" } },
      ],
      layout: { name: "cose", animate: false },
    });
    return () => cyRef.current?.destroy();
  }, [ego.data]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Network / Link Analysis</h1>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Panel title="Top repeat offenders">
          <ul className="space-y-1 max-h-[440px] overflow-auto">
            {(offenders.data?.items ?? []).map((o) => (
              <li key={o.person_id}>
                <button
                  onClick={() => setSelected(o.person_id)}
                  className={`w-full text-left rounded px-2 py-1 text-sm ${
                    selected === o.person_id ? "bg-ksp-accent text-white" : "hover:bg-white/5 text-white/80"
                  }`}
                >
                  {o.name} <span className="text-white/40">· {o.incidents} incidents</span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>
        <div className="lg:col-span-2">
          <Panel title={selected ? `Association graph — ${selected}` : "Select an offender to map associations"}>
            <div ref={graphEl} style={{ height: 440, background: "#0b1220", borderRadius: 8 }} />
          </Panel>
        </div>
      </div>
    </div>
  );
}
