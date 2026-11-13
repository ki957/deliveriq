import { useState, type FormEvent } from "react";
import { MapPin } from "lucide-react";

import { useAddresses, useServiceability, type Serviceability } from "../api";
import { useChosenLocation, type ChosenLocation } from "../location";
import { useMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { StatusBadge } from "@/shared/ui/status-badge";

// CU-01–CU-04: choose a location before browsing; serviceability needs both distance rules.
export function ServiceabilitySummary({ reach }: { reach: Serviceability }) {
  return (
    <div className="text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <StatusBadge
          tone={reach.serviceable ? "success" : "danger"}
          label={reach.serviceable ? "We deliver here" : "Outside delivery area"}
        />
        <span className="text-text-muted">
          {reach.straight_line_km} km straight-line (max {reach.straight_line_max_km}) · {reach.road_km} km by
          road (max {reach.road_max_km}){reach.road_km_estimated ? " · road distance: estimated" : ""}
        </span>
      </p>
      {reach.kitchen_location_is_synthetic ? (
        <p className="mt-1 text-xs text-text-muted">Kitchen location is a synthetic test location.</p>
      ) : null}
    </div>
  );
}

export function LocationPanel({ onChosen }: { onChosen?: (location: ChosenLocation) => void }) {
  const [location, setLocation] = useChosenLocation();
  const [editing, setEditing] = useState(location === null);
  const reach = useServiceability(location);

  if (location && !editing) {
    return (
      <section aria-labelledby="location" className="rounded-panel border border-border bg-surface p-4">
        <h2 id="location" className="flex items-center gap-2 text-lg font-semibold">
          <MapPin className="size-5" aria-hidden="true" /> Delivering to: {location.label}
        </h2>
        <div className="mt-2">{reach.data ? <ServiceabilitySummary reach={reach.data} /> : null}</div>
        {reach.data && !reach.data.serviceable ? (
          <p role="alert" className="mt-2 text-sm">
            We can't deliver to this location yet. The kitchen delivers within{" "}
            {reach.data.straight_line_max_km} km straight-line and {reach.data.road_max_km} km by road of{" "}
            {reach.data.kitchen_name}. Choose another location.
          </p>
        ) : null}
        <Button variant="secondary" className="mt-3" onClick={() => setEditing(true)}>
          Change location
        </Button>
      </section>
    );
  }

  return (
    <LocationChooser
      onCancel={location ? () => setEditing(false) : undefined}
      onChoose={(next) => {
        setLocation(next);
        setEditing(false);
        onChosen?.(next);
      }}
    />
  );
}

function LocationChooser({
  onChoose,
  onCancel,
}: {
  onChoose: (l: ChosenLocation) => void;
  onCancel: (() => void) | undefined;
}) {
  const me = useMe();
  const signedIn = Boolean(me.data);
  const addresses = useAddresses(signedIn);
  const [gpsError, setGpsError] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);

  function locateMe() {
    setGpsError(null);
    if (!navigator.geolocation) {
      setGpsError("This browser cannot share its location. Enter coordinates instead.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        onChoose({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          label: "Current location",
          source: "gps",
        }),
      // Never fabricate a position when location is denied or unavailable.
      () => setGpsError("Location access was denied or unavailable. Enter coordinates instead."),
      { timeout: 10_000 },
    );
  }

  function manual(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const lat = Number(data.get("lat"));
    const lng = Number(data.get("lng"));
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < 6 || lat > 37.5 || lng < 68 || lng > 97.5) {
      setManualError("Enter a latitude and longitude in India, for example 13.0835 and 80.2710.");
      return;
    }
    onChoose({ lat, lng, label: `${lat.toFixed(4)}, ${lng.toFixed(4)}`, source: "manual" });
  }

  return (
    <section aria-labelledby="choose-location" className="rounded-panel border border-border bg-surface p-4">
      <h2 id="choose-location" className="text-lg font-semibold">
        Choose your delivery location
      </h2>
      <p className="mt-1 text-sm text-text-muted">
        We check that the kitchen can deliver to you before showing the menu.
      </p>
      {signedIn && addresses.data && addresses.data.length > 0 ? (
        <div className="mt-3">
          <h3 className="text-sm font-medium">Your saved addresses</h3>
          <ul className="mt-1 flex flex-wrap gap-2">
            {addresses.data.map((a) => (
              <li key={a.id}>
                <Button
                  variant="secondary"
                  onClick={() =>
                    onChoose({ lat: a.lat, lng: a.lng, label: a.label, source: "address", addressId: a.id })
                  }
                >
                  {a.label}
                  {a.is_default ? " (default)" : ""}
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="mt-3">
        <Button onClick={locateMe}>Use my current location</Button>
        {gpsError ? (
          <p role="alert" className="mt-2 text-sm">
            {gpsError}
          </p>
        ) : null}
      </div>
      <form onSubmit={manual} className="mt-4 flex flex-wrap items-end gap-3" noValidate>
        <p className="w-full text-sm text-text-muted">
          Or enter coordinates. Address search and maps are not part of this POC.
        </p>
        <div>
          <label htmlFor="loc-lat" className="block text-sm font-medium">
            Latitude
          </label>
          <input
            id="loc-lat"
            name="lat"
            inputMode="decimal"
            className="mt-1 min-h-11 w-36 rounded-control border border-border bg-surface px-3"
          />
        </div>
        <div>
          <label htmlFor="loc-lng" className="block text-sm font-medium">
            Longitude
          </label>
          <input
            id="loc-lng"
            name="lng"
            inputMode="decimal"
            className="mt-1 min-h-11 w-36 rounded-control border border-border bg-surface px-3"
          />
        </div>
        <Button type="submit" variant="secondary">
          Use these coordinates
        </Button>
        {manualError ? (
          <p role="alert" className="w-full text-sm">
            {manualError}
          </p>
        ) : null}
      </form>
      {onCancel ? (
        <Button variant="ghost" className="mt-3" onClick={onCancel}>
          Cancel
        </Button>
      ) : null}
    </section>
  );
}
