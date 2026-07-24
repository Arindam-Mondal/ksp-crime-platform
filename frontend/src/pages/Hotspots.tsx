import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer, Cell,
} from "recharts";
import { MapPinned, Clock, Flame, Building2, Siren, X } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import Badge from "../components/Badge";
import { Skeleton } from "../components/Skeleton";
import { CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle, cursorFill } from "../components/charts/theme";

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

type View = "heat" | "districts";
type Metric = "risk" | "cs";

export default function Hotspots() {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [view, setView] = useState<View>("districts");
  const [metric, setMetric] = useState<Metric>("risk");
  const [selected, setSelected] = useState<string | null>(null);

  const cells = useQuery({ queryKey: ["cells"], queryFn: api.cells });
  const districts = useQuery({ queryKey: ["districts"], queryFn: api.districts });
  const spikes = useQuery({ queryKey: ["spikes"], queryFn: api.spikes });
  const byHour = useQuery({ queryKey: ["byHour"], queryFn: () => api.byHour() });
  const station = useQuery({
    queryKey: ["stations", selected],
    queryFn: () => api.stations(selected!),
    enabled: !!selected,
  });

  // --- init map once ---
  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: mapEl.current,
      style: OSM_STYLE,
      center: [76.6, 14.9],
      zoom: 5.6,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
  }, []);

  // --- heatmap layer from cells ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !cells.data) return;
    const draw = () => {
      const data: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: cells.data!.items.map((c) => ({
          type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] }, properties: { count: c.count },
        })),
      };
      if (map.getSource("cells")) (map.getSource("cells") as maplibregl.GeoJSONSource).setData(data);
      else {
        map.addSource("cells", { type: "geojson", data });
        map.addLayer({
          id: "heat", type: "heatmap", source: "cells",
          layout: { visibility: view === "heat" ? "visible" : "none" },
          paint: {
            "heatmap-weight": ["interpolate", ["linear"], ["get", "count"], 0, 0, 50, 1],
            "heatmap-intensity": 1.1,
            "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"],
              0, "rgba(10,14,23,0)", 0.2, "rgba(91,127,255,0.55)", 0.45, "rgba(56,189,248,0.7)",
              0.7, "rgba(245,158,11,0.85)", 1, "rgba(239,68,68,0.95)"],
            "heatmap-radius": 32, "heatmap-opacity": 0.78,
          },
        });
      }
    };
    if (map.isStyleLoaded()) draw(); else map.once("load", draw);
  }, [cells.data, view]);

  // --- district choropleth circles ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !districts.data) return;
    const items = districts.data.items.filter((d) => d.lat != null && d.lon != null);
    const maxInc = Math.max(1, ...items.map((d) => d.cases));
    const draw = () => {
      const data: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: items.map((d) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [d.lon!, d.lat!] },
          properties: { district: d.district, cases: d.cases, risk: d.risk_score, cs: d.chargesheet_rate },
        })),
      };
      if (map.getSource("districts")) (map.getSource("districts") as maplibregl.GeoJSONSource).setData(data);
      else {
        map.addSource("districts", { type: "geojson", data });
        map.addLayer({
          id: "district-circles", type: "circle", source: "districts",
          layout: { visibility: view === "districts" ? "visible" : "none" },
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["get", "cases"], 0, 7, maxInc, 34],
            "circle-color": colorExpr(metric),
            "circle-opacity": 0.82,
            "circle-stroke-width": 1.5,
            "circle-stroke-color": "#0a0e17",
          },
        });
        map.on("click", "district-circles", (e) => {
          const p = e.features?.[0]?.properties as any;
          if (p?.district) { setSelected(p.district); map.flyTo({ center: (e.features![0].geometry as any).coordinates, zoom: 8, duration: 700 }); }
        });
        map.on("mouseenter", "district-circles", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "district-circles", () => (map.getCanvas().style.cursor = ""));
      }
    };
    if (map.isStyleLoaded()) draw(); else map.once("load", draw);
  }, [districts.data, view, metric]);

  // --- toggle layer visibility on view change ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (map.getLayer("heat")) map.setLayoutProperty("heat", "visibility", view === "heat" ? "visible" : "none");
      if (map.getLayer("district-circles")) map.setLayoutProperty("district-circles", "visibility", view === "districts" ? "visible" : "none");
    };
    if (map.isStyleLoaded()) apply(); else map.once("load", apply);
  }, [view]);

  // --- recolor circles on metric change ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("district-circles")) return;
    map.setPaintProperty("district-circles", "circle-color", colorExpr(metric));
  }, [metric]);

  // --- pulsing alert markers (red-zone) ---
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !spikes.data) return;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    spikes.data.items
      .filter((a) => a.lat != null && a.lon != null)
      .slice(0, 12)
      .forEach((a) => {
        const el = document.createElement("div");
        el.className = "map-pulse" + (a.severity === "Critical" ? "" : " warning");
        el.title = `${a.sub_head} ↑ ${a.ratio}× · ${a.district}`;
        const popup = new maplibregl.Popup({ offset: 14, closeButton: false }).setHTML(
          `<div style="font-family:Manrope,sans-serif"><b>${a.sub_head}</b> ↑ ${a.ratio}×<br/>${a.district} · ${a.recent} in 30d</div>`
        );
        const mk = new maplibregl.Marker({ element: el }).setLngLat([a.lon!, a.lat!]).setPopup(popup).addTo(map);
        markersRef.current.push(mk);
      });
  }, [spikes.data]);

  const selectedStat = useMemo(
    () => districts.data?.items.find((d) => d.district === selected),
    [districts.data, selected]
  );

  return (
    <div className="space-y-7">
      <PageHeader
        icon={MapPinned}
        eyebrow="Geospatial Intelligence"
        title="Crime Hotspots"
        subtitle="District choropleth, kernel-density heat, and emerging-trend red zones"
        actions={
          spikes.data ? (
            <Badge variant={spikes.data.count ? "danger" : "success"} dot>
              <Siren size={12} /> {spikes.data.count} spikes
            </Badge>
          ) : undefined
        }
      />

      <Panel
        icon={view === "heat" ? Flame : Building2}
        title={view === "heat" ? "Crime density surface" : "District overview"}
        subtitle={view === "heat" ? "Kernel-density of case locations (CaseMaster GPS)" : "Sized by volume, shaded by " + (metric === "risk" ? "risk" : "chargesheet rate")}
        bodyClassName="p-0"
        actions={
          <div className="flex items-center gap-2">
            {view === "districts" && (
              <div className="hidden items-center rounded-lg border border-line p-0.5 sm:flex">
                {(["risk", "cs"] as Metric[]).map((m) => (
                  <button key={m} onClick={() => setMetric(m)}
                    className={`rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${metric === m ? "bg-surface-2 text-white" : "text-muted hover:text-white/80"}`}>
                    {m === "risk" ? "Risk" : "CS rate"}
                  </button>
                ))}
              </div>
            )}
            <div className="flex items-center rounded-lg border border-line p-0.5">
              {([["districts", "Districts", Building2], ["heat", "Heat", Flame]] as const).map(([v, label, Icon]) => (
                <button key={v} onClick={() => setView(v as View)}
                  className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${view === v ? "bg-surface-2 text-white" : "text-muted hover:text-white/80"}`}>
                  <Icon size={13} /> {label}
                </button>
              ))}
            </div>
          </div>
        }
      >
        <div className="relative">
          {(cells.isPending || districts.isPending) && (
            <div className="absolute inset-0 z-10 grid place-items-center bg-surface/60 backdrop-blur-sm">
              <Skeleton className="h-full w-full rounded-none" />
            </div>
          )}
          <div ref={mapEl} className="h-[480px] w-full overflow-hidden rounded-b-2xl" />

          {/* Legend */}
          <div className="pointer-events-none absolute bottom-4 left-4 z-10 rounded-xl border border-line bg-surface/90 px-3.5 py-3 shadow-card backdrop-blur-md">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              {view === "heat" ? "Case density" : metric === "risk" ? "Risk score" : "Chargesheet rate"}
            </div>
            <div className="h-2 w-40 rounded-full" style={{ background: legendGradient(view, metric) }} />
            <div className="mt-1 flex justify-between text-[10px] text-muted">
              <span>{view === "heat" ? "Low" : metric === "risk" ? "Low" : "Weak"}</span>
              <span>{view === "heat" ? "High" : metric === "risk" ? "High" : "Strong"}</span>
            </div>
            <div className="mt-2 flex items-center gap-1.5 text-[10px] text-muted">
              <span className="h-2.5 w-2.5 rounded-full bg-danger" /> emerging-trend spike
            </div>
          </div>
        </div>
      </Panel>

      {/* District drill-down OR statewide temporal pattern */}
      {selected ? (
        <Panel
          icon={Building2}
          title={`${selected} — drill-down`}
          subtitle={selectedStat ? `${selectedStat.cases.toLocaleString()} cases · ${selectedStat.heinous_share}% heinous · ${selectedStat.chargesheet_rate}% chargesheeted` : undefined}
          actions={
            <button onClick={() => setSelected(null)} className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition-colors hover:text-white">
              <X size={13} /> Clear
            </button>
          }
        >
          {station.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Top stations</div>
                <div style={{ height: 260 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={(station.data?.stations ?? []).slice(0, 8)} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                      <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                      <YAxis type="category" dataKey="station" tick={{ ...CHART.axisTick, fontSize: 10 }} tickLine={false} axisLine={false} width={120} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                      <Bar dataKey="cases" radius={[0, 4, 4, 0]} maxBarSize={18}>
                        {(station.data?.stations ?? []).slice(0, 8).map((_, i) => <Cell key={i} fill={CHART.accent} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">Hourly pattern</div>
                <div style={{ height: 200 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={station.data?.by_hour ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                      <defs>
                        <linearGradient id="drillHour" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={CHART.accentSoft} stopOpacity={0.45} />
                          <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.02} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                      <XAxis dataKey="hour" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                      <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={32} />
                      <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} labelFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
                      <Area type="monotone" dataKey="count" stroke={CHART.accentSoft} strokeWidth={2} fill="url(#drillHour)" dot={false} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {(station.data?.by_type ?? []).slice(0, 5).map((t) => (
                    <Badge key={t.name} variant="neutral">{t.name} · {t.count}</Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Panel>
      ) : (
        <Panel icon={Clock} title="Temporal pattern" subtitle="Statewide incident frequency by hour — click a district above to drill in">
          <div style={{ height: 240 }}>
            {byHour.isPending ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={byHour.data?.items ?? []} margin={{ left: 4, right: 8, top: 8, bottom: 4 }}>
                  <defs>
                    <linearGradient id="hourArea" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART.accentSoft} stopOpacity={0.45} />
                      <stop offset="100%" stopColor={CHART.accent} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} vertical={false} />
                  <XAxis dataKey="hour" tick={CHART.axisTick} tickLine={false} axisLine={{ stroke: CHART.grid }} />
                  <YAxis tick={CHART.axisTick} tickLine={false} axisLine={false} width={40} />
                  <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} labelFormatter={(h) => `${String(h).padStart(2, "0")}:00`} />
                  <Area type="monotone" dataKey="count" stroke={CHART.accentSoft} strokeWidth={2} fill="url(#hourArea)" dot={false} activeDot={{ r: 4, fill: CHART.accentSoft, stroke: "#0a0e17", strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}

// circle-color paint expression by metric
function colorExpr(metric: Metric): any {
  if (metric === "cs") {
    // chargesheet rate (%): low = red (weak investigation outcomes), high = green
    return ["interpolate", ["linear"], ["get", "cs"],
      30, "#ef4444", 45, "#f59e0b", 60, "#38bdf8", 75, "#10b981"];
  }
  return ["interpolate", ["linear"], ["get", "risk"],
    0, "#10b981", 0.25, "#38bdf8", 0.45, "#f59e0b", 0.7, "#ef4444"];
}

function legendGradient(view: View, metric: Metric): string {
  if (view === "heat") return "linear-gradient(90deg, rgba(91,127,255,0.6), rgba(56,189,248,0.8), rgba(245,158,11,0.9), rgba(239,68,68,1))";
  if (metric === "cs") return "linear-gradient(90deg, #ef4444, #f59e0b, #38bdf8, #10b981)";
  return "linear-gradient(90deg, #10b981, #38bdf8, #f59e0b, #ef4444)";
}
