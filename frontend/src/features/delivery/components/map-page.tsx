import "leaflet/dist/leaflet.css";

import { useState } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, Tooltip } from "react-leaflet";

import { useGps } from "../tracker";
import { DeliveryPage, isHeld, NoDelivery } from "./shared";
import { TestBadge } from "@/shared/ui/test-badge";

// DL-G6, DDR-113 (10): Leaflet + OpenStreetMap. The tile server is configurable; the public OSM server is
// for local demo use only. The route is a straight line, labelled "estimated", until road routing (DDR-55).
const TILES = import.meta.env.VITE_MAP_TILE_URL ?? "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

type Place = { lat: number; lng: number };

export default function DeliveryMapPage() {
  return (
    <DeliveryPage title="Map">
      {(work) =>
        isHeld(work) && work.order ? (
          <DeliveryMap
            kitchen={work.order.kitchen}
            kitchenName={work.order.kitchen_name}
            synthetic={work.order.kitchen_location_is_synthetic}
            destination={work.order.destination ?? null}
            address={work.order.delivery_address}
          />
        ) : (
          <NoDelivery />
        )
      }
    </DeliveryPage>
  );
}

function DeliveryMap({
  kitchen,
  kitchenName,
  synthetic,
  destination,
  address,
}: {
  kitchen: Place;
  kitchenName: string;
  synthetic: boolean;
  destination: Place | null;
  address: string | null;
}) {
  const gps = useGps();
  const [tilesFailed, setTilesFailed] = useState(false);
  const me = gps.last;
  const points: Place[] = [kitchen, ...(destination ? [destination] : [])];
  return (
    <div className="space-y-3">
      <p className="flex flex-wrap items-center gap-2 text-sm">
        Route: straight line (estimated, not road routing)
        {gps.mode === "SIMULATED" ? <TestBadge label="Simulated GPS" /> : null}
      </p>
      <div className="h-80 overflow-hidden rounded-panel border border-border" data-testid="delivery-map">
        <MapContainer
          bounds={points.map((p) => [p.lat, p.lng]) as [number, number][]}
          boundsOptions={{ padding: [32, 32] }}
          className="h-full w-full"
          scrollWheelZoom={false}
        >
          <TileLayer
            url={TILES}
            attribution={ATTRIBUTION}
            eventHandlers={{ tileerror: () => setTilesFailed(true) }}
          />
          <CircleMarker center={[kitchen.lat, kitchen.lng]} radius={9} pathOptions={{ color: "#171717" }}>
            <Tooltip permanent>Kitchen</Tooltip>
          </CircleMarker>
          {destination ? (
            <>
              <CircleMarker
                center={[destination.lat, destination.lng]}
                radius={9}
                pathOptions={{ color: "#A66BFF" }}
              >
                <Tooltip permanent>Customer</Tooltip>
              </CircleMarker>
              <Polyline
                positions={[
                  [kitchen.lat, kitchen.lng],
                  [destination.lat, destination.lng],
                ]}
                pathOptions={{ dashArray: "6 6" }}
              />
            </>
          ) : null}
          {me ? (
            <CircleMarker center={[me.lat, me.lng]} radius={7} pathOptions={{ color: "#1D4ED8" }}>
              <Tooltip>{gps.mode === "SIMULATED" ? "You (simulated)" : "You"}</Tooltip>
            </CircleMarker>
          ) : null}
        </MapContainer>
      </div>
      {tilesFailed ? (
        <p role="status" className="text-sm">
          Map tiles could not be loaded. The places are listed below.
        </p>
      ) : null}
      <ul className="space-y-1 text-sm" aria-label="Places">
        <li>
          Kitchen: {kitchenName}
          {synthetic ? " (synthetic test location)" : ""}
        </li>
        <li>Customer: {address ?? "shown after you accept"}</li>
        <li>
          You:{" "}
          {me
            ? `${me.lat.toFixed(5)}, ${me.lng.toFixed(5)}${gps.mode === "SIMULATED" ? " (simulated)" : ""}`
            : "no position yet"}
        </li>
      </ul>
    </div>
  );
}
