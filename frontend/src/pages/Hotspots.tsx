import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import { AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from "recharts";
import { MapPinned, Clock, Flame } from "lucide-react";
import { api } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import { Skeleton } from "../components/Skeleton";
import { CHART, tooltipStyle, tooltipLabelStyle, tooltipItemStyle, cursorFill } from "../components/charts/theme";

// Free OpenStreetMap raster style — no API key, no Catalyst map service needed.
const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export default function Hotspots() {
  const mapEl = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const cells = useQuery({ queryKey: ["cells"], queryFn: api.cells });
  const byHour = useQuery({ queryKey: ["byHour"], queryFn: () => api.byHour() });

  useEffect(() => {
    if (!mapEl.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: mapEl.current,
      style: OSM_STYLE,
      center: [76.6, 14.5], // Karnataka
      zoom: 5.5,
      attributionControl: { compact: true },
    });
    mapRef.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !cells.data) return;
    const draw = () => {
      const data: GeoJSON.FeatureCollection = {
        type: "FeatureCollection",
        features: cells.data!.items.map((c) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [c.lon, c.lat] },
          properties: { count: c.count },
        })),
      };
      const src = map.getSource("cells") as maplibregl.GeoJSONSource | undefined;
      if (src) {
        src.setData(data);
      } else {
        map.addSource("cells", { type: "geojson", data });
        map.addLayer({
          id: "heat",
          type: "heatmap",
          source: "cells",
          paint: {
            "heatmap-weight": ["interpolate", ["linear"], ["get", "count"], 0, 0, 50, 1],
            "heatmap-intensity": 1.1,
            // low → high density ramp: transparent → indigo → cyan → amber → red
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0, "rgba(10,14,23,0)",
              0.2, "rgba(91,127,255,0.55)",
              0.45, "rgba(56,189,248,0.7)",
              0.7, "rgba(245,158,11,0.85)",
              1, "rgba(239,68,68,0.95)",
            ],
            "heatmap-radius": 32,
            "heatmap-opacity": 0.78,
          },
        });
      }
    };
    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [cells.data]);

  const cellCount = cells.data?.items.length ?? 0;

  return (
    <div className="space-y-7">
      <PageHeader
        icon={MapPinned}
        eyebrow="Geospatial Intelligence"
        title="Crime Hotspots"
        subtitle="Kernel-density concentration of incidents across Karnataka"
      />

      <Panel
        icon={Flame}
        title="Crime density surface"
        subtitle={cells.data ? `${cellCount.toLocaleString()} aggregated grid cells` : "Loading density grid…"}
        bodyClassName="p-0"
      >
        <div className="relative">
          {cells.isPending && (
            <div className="absolute inset-0 z-10 grid place-items-center bg-surface/60 backdrop-blur-sm">
              <Skeleton className="h-full w-full rounded-none" />
            </div>
          )}
          <div ref={mapEl} className="h-[480px] w-full overflow-hidden rounded-b-2xl" />

          {/* Density legend */}
          <div className="pointer-events-none absolute bottom-4 left-4 z-10 rounded-xl border border-line bg-surface/90 px-3.5 py-3 shadow-card backdrop-blur-md">
            <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
              Incident density
            </div>
            <div
              className="h-2 w-40 rounded-full"
              style={{
                background:
                  "linear-gradient(90deg, rgba(91,127,255,0.6), rgba(56,189,248,0.8), rgba(245,158,11,0.9), rgba(239,68,68,1))",
              }}
            />
            <div className="mt-1 flex justify-between text-[10px] text-muted">
              <span>Low</span>
              <span>High</span>
            </div>
          </div>
        </div>
      </Panel>

      <Panel icon={Clock} title="Temporal pattern" subtitle="Incident frequency by hour of day">
        <div style={{ height: 260 }}>
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
                <Tooltip
                  contentStyle={tooltipStyle}
                  labelStyle={tooltipLabelStyle}
                  itemStyle={tooltipItemStyle}
                  cursor={cursorFill}
                  labelFormatter={(h) => `${String(h).padStart(2, "0")}:00`}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke={CHART.accentSoft}
                  strokeWidth={2}
                  fill="url(#hourArea)"
                  dot={false}
                  activeDot={{ r: 4, fill: CHART.accentSoft, stroke: "#0a0e17", strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>
    </div>
  );
}
