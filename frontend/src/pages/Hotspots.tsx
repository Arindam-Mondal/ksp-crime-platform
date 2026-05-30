import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { api } from "../lib/api";
import Panel from "../components/Panel";

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
    });
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
            "heatmap-radius": 30,
            "heatmap-opacity": 0.7,
          },
        });
      }
    };
    if (map.isStyleLoaded()) draw();
    else map.once("load", draw);
  }, [cells.data]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Geospatial Hotspots</h1>
      <Panel title="Crime density across Karnataka">
        <div ref={mapEl} style={{ height: 460, borderRadius: 8, overflow: "hidden" }} />
      </Panel>
      <Panel title="Incidents by hour of day">
        <div style={{ height: 240 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={byHour.data?.items ?? []}>
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <YAxis tick={{ fontSize: 11, fill: "#9ca3af" }} />
              <Tooltip contentStyle={{ background: "#141d2e", border: "1px solid #ffffff20" }} />
              <Bar dataKey="count" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}
