import { Bell } from "lucide-react";
import { Link } from "react-router";

import { describe, useInbox, useMarkRead } from "../api";
import { actionError } from "@/shared/api/errors";
import { Button } from "@/shared/ui/button";
import { queryState } from "@/shared/ui/query-state";
import { EmptyState } from "@/shared/ui/states";
import { TestBadge } from "@/shared/ui/test-badge";
import { cn } from "@/shared/utils/cn";
import { formatDateTime } from "@/shared/utils/format";

// CU-25, DL-16 (30-day history), KI-23; DDR-115 (10), (11). In-app only: no SMS (DDR-40), no browser push.
export function NotificationsPage() {
  const inbox = useInbox();
  const mark = useMarkRead();
  const state = queryState(inbox, { loading: "Loading notifications…" });
  if (state) return state;
  const box = inbox.data;
  if (!box) return null;
  return (
    <section className="mx-auto max-w-3xl space-y-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Notifications</h1>
          <p className="text-sm text-text-muted" data-testid="notification-channels">
            In-app only, kept for {box.history_days} days. SMS: {box.sms}.
          </p>
        </div>
        {box.unread > 0 ? (
          <Button variant="secondary" onClick={() => mark.mutate(null)} disabled={mark.isPending}>
            Mark all as read
          </Button>
        ) : null}
      </header>
      {mark.isError ? (
        <p role="alert" className="text-sm">
          {actionError(mark.error)}
        </p>
      ) : null}
      {box.rows.length === 0 ? (
        <EmptyState title="No notifications in the last 30 days" />
      ) : (
        <ul className="space-y-2" aria-label="Notifications">
          {box.rows.map((n) => {
            const { text, to } = describe(n);
            const unread = n.read_at === null;
            return (
              <li
                key={n.id}
                className={cn(
                  "rounded-panel border bg-surface p-3",
                  unread ? "border-status-info" : "border-border",
                )}
              >
                <Link
                  to={to}
                  className="block underline-offset-2 hover:underline"
                  onClick={() => unread && mark.mutate([n.id])}
                >
                  <span className="flex flex-wrap items-center gap-2">
                    {unread ? (
                      <span className="text-xs font-semibold text-status-info">
                        <Bell className="mr-1 inline size-3" aria-hidden="true" />
                        New
                      </span>
                    ) : null}
                    <span className="font-medium">{text}</span>
                    {n.is_test_fixture ? <TestBadge label="Test data" /> : null}
                  </span>
                  <span className="block text-xs text-text-muted">{formatDateTime(n.created_at)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

/** Header bell with the unread count; links to the portal's Notifications page. */
export function NotificationsBell({ to }: { to: string }) {
  const inbox = useInbox();
  const unread = inbox.data?.unread ?? 0;
  // The accessible name contains exactly the visible badge text (WCAG 2.5.3 label in name).
  const shown = unread > 99 ? "99+" : String(unread);
  return (
    <Link
      to={to}
      className="relative inline-flex min-h-11 min-w-11 items-center justify-center rounded-control hover:bg-white/10"
      aria-label={unread ? `Notifications, ${shown} unread` : "Notifications"}
      data-testid="notifications-bell"
    >
      <Bell className="size-5" aria-hidden="true" />
      {unread ? (
        <span
          aria-hidden="true"
          className="absolute right-1 top-1 min-w-5 rounded-full bg-status-danger px-1 text-center text-xs font-semibold text-white"
        >
          {shown}
        </span>
      ) : null}
    </Link>
  );
}
