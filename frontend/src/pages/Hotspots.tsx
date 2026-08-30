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
import ChartFrame from "../components/charts/ChartFrame";
import { truncatedTick, useCharsFor, catAxisWidth } from "../components/charts/AxisTick";
import { CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle, cursorFill } from "../components/charts/theme";
import { useT } from "../i18n";
import { useDataLabel } from "../i18n/data";

const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: { type: "raster", tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], tileSize: 256, attribution: "© OpenStreetMap contributors" },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

type View = "heat" | "districts";
type Metric = "risk" | "rate" | "cs";

export default function Hotspots() {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<maplibregl.Marker[]>([]);
  const [view, setView] = useState<View>("districts");
  const [metric, setMetric] = useState<Metric>("risk");
  // `selected` holds the English district name — it is the id the stations endpoint
  // filters on and the value the map feature carries.
  const [selected, setSelected] = useState<string | null>(null);
  const t = useT();
  const dl = useDataLabel();
  const charsFor = useCharsFor();

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
          properties: { district: d.district, cases: d.cases, risk: d.risk_score, cs: d.chargesheet_rate, rate: d.per_100k ?? 0 },
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
        const text = t("hotspots.popup", {
          subHead: dl("crimeSubHead", a.sub_head),
          ratio: a.ratio,
          district: dl("district", a.district),
          recent: a.recent,
        });
        const el = document.createElement("div");
        el.className = "map-pulse" + (a.severity === "Critical" ? "" : " warning");
        el.title = text;
        // Popups render outside the React tree, so the Kannada face has to be named
        // here — the Tailwind `sans` stack never reaches them. Built as a DOM node
        // rather than an HTML string so the interpolated values can't inject markup.
        const content = document.createElement("div");
        content.style.fontFamily = "Manrope, 'Noto Sans Kannada', sans-serif";
        content.textContent = text;
        const popup = new maplibregl.Popup({ offset: 14, closeButton: false }).setDOMContent(content);
        const mk = new maplibregl.Marker({ element: el }).setLngLat([a.lon!, a.lat!]).setPopup(popup).addTo(map);
        markersRef.current.push(mk);
      });
    // Re-render markers when the language changes so popups follow it.
  }, [spikes.data, t, dl]);

  const selectedStat = useMemo(
    () => districts.data?.items.find((d) => d.district === selected),
    [districts.data, selected]
  );

  return (
    <div className="space-y-7">
      <PageHeader
        icon={MapPinned}
        eyebrow={t("hotspots.eyebrow")}
        title={t("hotspots.title")}
        subtitle={t("hotspots.subtitle")}
        actions={
          spikes.data ? (
            <Badge variant={spikes.data.count ? "danger" : "success"} dot>
              <Siren size={12} /> {t("hotspots.spikeCount", { count: spikes.data.count })}
            </Badge>
          ) : undefined
        }
      />

      <Panel
        icon={view === "heat" ? Flame : Building2}
        title={view === "heat" ? t("hotspots.heatTitle") : t("hotspots.districtTitle")}
        subtitle={
          view === "heat"
            ? t("hotspots.heatSubtitle")
            : t("hotspots.districtSubtitle", {
                metric: t(
                  metric === "risk"
                    ? "hotspots.metric.risk"
                    : metric === "rate"
                    ? "hotspots.metric.rate"
                    : "hotspots.metric.cs"
                ),
              })
        }
        bodyClassName="p-0"
        actions={
          <div className="flex flex-wrap items-center justify-end gap-2">
            {view === "districts" && (
              <div className="flex items-center rounded-lg border border-line p-0.5">
                {(["risk", "rate", "cs"] as Metric[]).map((m) => (
                  <button key={m} onClick={() => setMetric(m)} aria-pressed={metric === m}
                    className={`seg-btn rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${metric === m ? "bg-surface-2 text-white" : "text-muted hover:text-white/80"}`}>
                    {t(
                      m === "risk"
                        ? "hotspots.toggle.risk"
                        : m === "rate"
                        ? "hotspots.toggle.rate"
                        : "hotspots.toggle.cs"
                    )}
                  </button>
                ))}
              </div>
            )}
            <div className="flex items-center rounded-lg border border-line p-0.5">
              {(
                [
                  ["districts", "hotspots.view.districts", Building2],
                  ["heat", "hotspots.view.heat", Flame],
                ] as const
              ).map(([v, labelKey, Icon]) => (
                <button key={v} onClick={() => setView(v as View)} aria-pressed={view === v}
                  className={`seg-btn inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${view === v ? "bg-surface-2 text-white" : "text-muted hover:text-white/80"}`}>
                  <Icon size={13} /> {t(labelKey)}
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
          <div ref={mapEl} className="h-[clamp(320px,58svh,480px)] w-full overflow-hidden rounded-b-2xl" />

          {/* Legend — narrower and without the spike row on phones, where it
              would otherwise cover a third of the map */}
          <div className="pointer-events-none absolute bottom-3 left-3 z-overlay rounded-xl border border-line bg-surface/90 px-3 py-2.5 shadow-card backdrop-blur-md sm:bottom-4 sm:left-4 sm:px-3.5 sm:py-3">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              {t(
                view === "heat"
                  ? "hotspots.legend.density"
                  : metric === "risk"
                  ? "hotspots.legend.risk"
                  : metric === "rate"
                  ? "hotspots.legend.rate"
                  : "hotspots.legend.cs"
              )}
            </div>
            <div className="h-2 w-28 rounded-full sm:w-40" style={{ background: legendGradient(view, metric) }} />
            <div className="mt-1 flex justify-between text-[10px] text-muted">
              <span>
                {t(view !== "heat" && metric === "cs" ? "hotspots.legend.weak" : "hotspots.legend.low")}
              </span>
              <span>
                {t(view !== "heat" && metric === "cs" ? "hotspots.legend.strong" : "hotspots.legend.high")}
              </span>
            </div>
            <div className="mt-2 hidden items-center gap-1.5 text-[10px] text-muted sm:flex">
              <span className="h-2.5 w-2.5 rounded-full bg-danger" /> {t("hotspots.legend.spike")}
            </div>
          </div>
        </div>
      </Panel>

      {/* District drill-down OR statewide temporal pattern */}
      {selected ? (
        <Panel
          icon={Building2}
          title={t("hotspots.drilldown", { district: dl("district", selected) })}
          subtitle={
            selectedStat
              ? t("hotspots.drilldownSubtitle", {
                  cases: selectedStat.cases.toLocaleString(),
                  heinous: selectedStat.heinous_share,
                  chargesheeted: selectedStat.chargesheet_rate,
                })
              : undefined
          }
          actions={
            <button onClick={() => setSelected(null)} className="inline-flex items-center gap-1 rounded-lg border border-line px-2.5 py-1 text-xs text-muted transition-colors hover:text-white">
              <X size={13} /> {t("hotspots.clear")}
            </button>
          }
        >
          {station.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <div>
                {/* Station names are ERD unit names — proper nouns that stay English in
                    both languages, like person names and FIR numbers. */}
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {t("hotspots.topStations")}
                </div>
                <ChartFrame className="h-[230px] sm:h-[260px]">
                  {(w) => (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={(station.data?.stations ?? []).slice(0, 8).map((s) => ({
                          ...s,
                          // Station names carry a redundant " PS" suffix, and a few are
                          // disambiguated by a parenthesised district ("Ashok Nagar PS
                          // (Kalaburagi)") that is redundant once drilled into that
                          // district. Strip both so the label fits against the axis.
                          station: s.station
                            .replace(/\s*\([^)]*\)\s*$/, "")
                            .replace(/\s+PS$/, "")
                            .trim(),
                        }))}
                        layout="vertical"
                        margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} horizontal={false} />
                        <XAxis type="number" tick={CHART.axisTick} tickLine={false} axisLine={false} />
                        <YAxis
                          type="category"
                          dataKey="station"
                          tick={truncatedTick(charsFor(catAxisWidth(w) - 8, 10), { fontSize: 10 })}
                          tickLine={false}
                          axisLine={false}
                          width={catAxisWidth(w)}
                        />
                        <Tooltip contentStyle={tooltipStyle} labelStyle={tooltipLabelStyle} itemStyle={tooltipItemStyle} cursor={cursorFill} />
                        <Bar dataKey="cases" radius={[0, 4, 4, 0]} maxBarSize={18}>
                          {(station.data?.stations ?? []).slice(0, 8).map((_, i) => <Cell key={i} fill={CHART.accent} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                </ChartFrame>
              </div>
              <div>
                <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {t("hotspots.hourlyPattern")}
                </div>
                <div className="h-[180px] sm:h-[200px]">
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
                  {(station.data?.by_type ?? []).slice(0, 5).map((bt) => (
                    <Badge key={bt.name} variant="neutral">
                      {dl("crimeSubHead", bt.name)} · {bt.count}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Panel>
      ) : (
        <Panel icon={Clock} title={t("hotspots.temporal")} subtitle={t("hotspots.temporalSubtitle")}>
          <div className="h-[200px] sm:h-[240px]">
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
  if (metric === "rate") {
    // crime rate per 100k residents: low = green, high = red
    return ["interpolate", ["linear"], ["get", "rate"],
      10, "#10b981", 25, "#38bdf8", 40, "#f59e0b", 60, "#ef4444"];
  }
  return ["interpolate", ["linear"], ["get", "risk"],
    0, "#10b981", 0.25, "#38bdf8", 0.45, "#f59e0b", 0.7, "#ef4444"];
}

function legendGradient(view: View, metric: Metric): string {
  if (view === "heat") return "linear-gradient(90deg, rgba(91,127,255,0.6), rgba(56,189,248,0.8), rgba(245,158,11,0.9), rgba(239,68,68,1))";
  if (metric === "cs") return "linear-gradient(90deg, #ef4444, #f59e0b, #38bdf8, #10b981)";
  return "linear-gradient(90deg, #10b981, #38bdf8, #f59e0b, #ef4444)";
}
