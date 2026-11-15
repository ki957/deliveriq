import { api, unwrap } from "@/shared/api/client";

import { useState } from "react";

export function KitchenCopilotPage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{
    answer: string;
    citations: string[];
    retrieval_mode: string;
    simulated: boolean;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!question.trim() || busy) return;
    setBusy(true);
    setError(false);
    try {
      const response = await api.POST("/api/v1/kitchen/ai/copilot", { body: { question } });
      setAnswer(unwrap(response));
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-6" aria-labelledby="kitchen-copilot-title">
      <header>
        <h1 id="kitchen-copilot-title" className="text-2xl font-semibold">
          Kitchen Copilot
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Answers use approved Kitchen guidance and cite their sources. The Copilot cannot change orders,
          recipes, or stock.
        </p>
      </header>
      <section className="rounded-panel border border-border bg-surface p-4" aria-label="Ask Kitchen Copilot">
        <form className="space-y-3" onSubmit={submit}>
          <label htmlFor="kitchen-question" className="block text-sm font-medium">
            Question
          </label>
          <textarea
            id="kitchen-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={2000}
            rows={4}
            className="w-full rounded-control border border-border bg-surface p-3"
          />
          <button
            disabled={busy || !question.trim()}
            className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
          >
            {busy ? "Looking up guidance…" : "Ask Copilot"}
          </button>
        </form>
        {error ? (
          <p role="alert" className="mt-3">
            Kitchen Copilot is unavailable. Please retry.
          </p>
        ) : null}
        {answer ? (
          <div className="mt-4 rounded-control border border-border p-3" aria-live="polite">
            <p>{answer.answer}</p>
            <p className="mt-2 text-sm text-text-muted">
              {answer.simulated ? "Simulated response" : "AI response"} · {answer.retrieval_mode}
            </p>
            {answer.citations.length ? (
              <p className="mt-2 text-sm text-text-muted">
                Sources: {answer.citations.join(", ")} · {answer.retrieval_mode}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>
    </main>
  );
}
