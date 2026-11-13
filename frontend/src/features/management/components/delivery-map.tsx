import "leaflet/dist/leaflet.css";

import { useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip } from "react-leaflet";

import type { Delivery } from "../api";

// DDR-113 (10), DDR-114 (11): the same configurable tile server as the Delivery PWA (public OSM for local
// demo use only). Loaded lazily so Leaflet stays out of the main bundle.
const TILES = import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

type Located = Delivery & { lat: number; lng: number };

export default function DeliveryPositionsMap({ deliveries }: { deliveries: Located[] }) {
  const [tilesFailed, setTilesFailed] = useState(false);
  return (
    <div className="space-y-2">
      <div className="h-80 overflow-hidden rounded-panel border border-border" data-testid="positions-map">
        <MapContainer
          bounds={deliveries.map((d) => [d.lat, d.lng]) as [number, number][]}
          boundsOptions={{ padding: [32, 32], maxZoom: 15 }}
          className="h-full w-full"
          scrollWheelZoom={false}
        >
          <TileLayer
            url={TILES}
            attribution={ATTRIBUTION}
            eventHandlers={{ tileerror: () => setTilesFailed(true) }}
          />
          {deliveries.map((d) => (
            <CircleMarker
              key={d.assignment_id}
              center={[d.lat, d.lng]}
              radius={8}
              pathOptions={{ color: d.simulated ? "#A66BFF" : "#1D4ED8" }}
            >
              <Tooltip>
                {d.agent_name}
                {d.simulated ? " (simulated)" : ""}
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      {tilesFailed ? (
        <p role="status" className="text-sm">
          Map tiles could not be loaded. The positions are listed in the table.
        </p>
      ) : null}
    </div>
  );
}
