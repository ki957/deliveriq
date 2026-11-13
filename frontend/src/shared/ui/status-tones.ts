import type { components } from "@/shared/api/generated/schema";
import type { StatusTone } from "./status-badge";

type S = components["schemas"];

// One mapping per state machine, shared by every portal, so a status reads the same everywhere.
const RUN: Record<S["RunSummaryOut"]["status"], [StatusTone, string]> = {
  queued: ["neutral", "Queued"],
  running: ["info", "Running"],
  succeeded: ["success", "Succeeded"],
  completed_with_quarantine: ["warning", "Completed with quarantine"],
  failed: ["danger", "Failed"],
  cancelled: ["neutral", "Cancelled"],
};

const RECIPE: Record<S["RecipeStatus"], [StatusTone, string]> = {
  DRAFT: ["neutral", "Draft"],
  PENDING_VALIDATION: ["info", "Pending validation"],
  VALIDATED: ["info", "Validated"],
  ACTIVE: ["success", "Active"],
  REJECTED: ["danger", "Rejected"],
  SUPERSEDED: ["neutral", "Superseded"],
  DISABLED: ["neutral", "Disabled"],
  QUARANTINED_DUPLICATE_CANDIDATE: ["warning", "Quarantined duplicate"],
};

const MENU: Record<S["Publication"], [StatusTone, string]> = {
  DRAFT: ["neutral", "Draft"],
  READY_FOR_PUBLICATION: ["info", "Ready for publication"],
  PUBLISHED: ["success", "Published"],
  TEMPORARILY_UNAVAILABLE: ["warning", "Temporarily unavailable"],
  RETIRED: ["neutral", "Retired"],
};

const STAGE: Record<string, [StatusTone, string]> = {
  pending: ["neutral", "Pending"],
  running: ["info", "Running"],
  succeeded: ["success", "Succeeded"],
  failed: ["danger", "Failed"],
  skipped: ["neutral", "Skipped"],
  cancelled: ["neutral", "Cancelled"],
};

export const runStatus = (s: S["RunSummaryOut"]["status"]) => RUN[s];
export const recipeStatus = (s: S["RecipeStatus"]) => RECIPE[s];
export const menuStatus = (s: S["Publication"]) => MENU[s];
export const stageStatus = (s: string): [StatusTone, string] => STAGE[s] ?? ["neutral", s];
export const ACTIVE_RUN_STATUSES: ReadonlySet<string> = new Set(["queued", "running"]);
