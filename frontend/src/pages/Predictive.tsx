import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import Panel from "../components/Panel";

export default function Predictive() {
  const risk = useQuery({ queryKey: ["riskScores"], queryFn: api.riskScores });
  const items = risk.data?.items ?? [];
  const max = items.length ? items[0].risk_score : 1;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Predictive & Anomaly</h1>
      <p className="text-xs text-white/40">{risk.data?.method}</p>
      <Panel title="District risk ranking">
        <table className="w-full text-sm">
          <thead className="text-white/50 text-left">
            <tr>
              <th className="py-1">District</th>
              <th>Incidents</th>
              <th>SEI</th>
              <th className="w-1/2">Risk</th>
            </tr>
          </thead>
          <tbody>
            {items.map((r) => (
              <tr key={r.district} className="border-t border-white/5">
                <td className="py-1">{r.district}</td>
                <td>{r.incidents}</td>
                <td>{r.socio_economic_index}</td>
                <td>
                  <div className="flex items-center gap-2">
                    <div className="h-2 rounded bg-ksp-danger" style={{ width: `${(r.risk_score / max) * 100}%` }} />
                    <span className="text-white/60">{r.risk_score}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
