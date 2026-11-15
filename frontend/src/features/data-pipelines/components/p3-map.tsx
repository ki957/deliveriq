import "leaflet/dist/leaflet.css";

import { useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer } from "react-leaflet";

import type { P3Point } from "../api";

export function P3Map({ points }: { points: P3Point[] }) {
  const [tilesFailed, setTilesFailed] = useState(false);
  const first = points[0];
  if (!first) return null;
  const last = points[points.length - 1] ?? first;
  const path = points.map((point): [number, number] => [point.latitude, point.longitude]);
  const start: [number, number] = [first.latitude, first.longitude];
  const end: [number, number] = [last.latitude, last.longitude];
  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">Simulated data · complete GPS track, 61 points</figcaption>
      <div
        className="h-64 overflow-hidden rounded-panel border border-border"
        aria-label="Simulated GPS track map"
      >
        <MapContainer center={start} zoom={16} className="h-full w-full" scrollWheelZoom={false}>
          <TileLayer
            url={import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png"}
            attribution={
              '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }
            eventHandlers={{ tileerror: () => setTilesFailed(true) }}
          />
          <Polyline positions={path} color="#2563eb" />
          <CircleMarker center={start} radius={5} />
          <CircleMarker center={end} radius={5} />
        </MapContainer>
      </div>
      {tilesFailed ? (
        <p role="status">Map tiles could not be loaded. Track coordinates are listed below.</p>
      ) : null}
      <p className="text-xs text-text-muted">
        Start {first.latitude.toFixed(4)}, {first.longitude.toFixed(4)} · End {last.latitude.toFixed(4)},{" "}
        {last.longitude.toFixed(4)}
      </p>
    </figure>
  );
}
