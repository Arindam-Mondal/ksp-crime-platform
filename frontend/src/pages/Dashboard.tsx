import { useQuery } from "@tanstack/react-query";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../lib/api";
import Panel from "../components/Panel";

export default function Dashboard() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const byDistrict = useQuery({ queryKey: ["byDistrict"], queryFn: api.byDistrict });

  const top = (byDistrict.data?.items ?? []).slice(0, 12);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Strategic Intelligence Hub</h1>
        <p className="text-white/50 text-sm">
          {health.data
            ? `Data mode: ${health.data.data_mode} · ${health.data.incidents_loaded.toLocaleString()} incidents loaded`
            : "Connecting to API…"}
        </p>
      </header>

      <Panel title="Incidents by district (top 12)">
        <div style={{ height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={top} margin={{ left: 10, right: 10, top: 10, bottom: 60 }}>
              <XAxis dataKey="district" angle={-40} textAnchor="end" interval={0} tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ background: "#141d2e", border: "1px solid #ffffff20" }} />
              <Bar dataKey="incidents" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}
