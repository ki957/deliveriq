import { ImageOff } from "lucide-react";

import type { MenuItem } from "../api";

// DDR-47: no image assets exist; a neutral, labelled "Image unavailable" state is shown instead.
export function DishImage({ item }: { item: Pick<MenuItem, "image_url" | "image_is_placeholder" | "name"> }) {
  if (item.image_url && !item.image_is_placeholder) {
    return <img src={item.image_url} alt={item.name} className="aspect-[4/3] w-full object-cover" />;
  }
  return (
    <div className="flex aspect-[4/3] w-full flex-col items-center justify-center gap-1 bg-muted text-text-muted">
      <ImageOff className="size-6" aria-hidden="true" />
      <span className="text-xs">Image unavailable</span>
    </div>
  );
}

// Veg indicator: text plus symbol, never colour alone (SH-03).
export function VegMark({ isVeg }: { isVeg: boolean | null }) {
  if (isVeg === null) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-control border border-border px-2 py-0.5 text-xs font-semibold">
      <span aria-hidden="true">{isVeg ? "●" : "▲"}</span>
      {isVeg ? "Veg" : "Non-veg"}
    </span>
  );
}
