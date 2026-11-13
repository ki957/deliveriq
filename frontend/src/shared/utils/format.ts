// Display formats for Indian locale and the kitchen's time zone (Asia/Kolkata, #15 §2).
const DATE_TIME = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium",
  timeStyle: "medium",
  timeZone: "Asia/Kolkata",
});

export function formatDateTime(value: string | null | undefined): string {
  return value ? DATE_TIME.format(new Date(value)) : "—";
}

/** Integer paise, tax-inclusive (CU-15), shown as rupees. */
export function formatPaise(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return "—";
  return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

export function formatDuration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  return ms < 1000 ? `${Math.max(ms, 0)} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** "PENDING_VALIDATION" → "Pending validation". */
export function humanize(code: string): string {
  const words = code.toLowerCase().replace(/[_:]+/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
