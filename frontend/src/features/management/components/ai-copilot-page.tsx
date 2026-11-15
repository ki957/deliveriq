import { useState } from "react";

import { useAiSettings, useAiStatus, useAskCopilot } from "../api";

export function AiCopilotPage() {
  const status = useAiStatus();
  const settings = useAiSettings();
  const ask = useAskCopilot();
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<{ text: string; simulated: boolean } | null>(null);

  return (
    <main className="space-y-6" aria-labelledby="ai-title">
      <div>
        <h1 id="ai-title" className="text-2xl font-semibold">
          Management AI Copilot
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Read-only operational assistance. It cannot change orders, menu, staff, refunds, or routing.
        </p>
      </div>
      {status.isLoading ? <p role="status">Loading AI status…</p> : null}
      {status.isError ? <p role="alert">AI status is unavailable.</p> : null}
      {status.data ? (
        <section className="rounded-panel border border-border bg-surface p-4" aria-label="AI status">
          <h2 className="font-semibold">AI status</h2>
          <p className="mt-2 text-sm">
            {status.data.enabled ? "Enabled" : "Disabled"} · Knowledge: {status.data.knowledge_status}
          </p>
          <p className="text-sm text-text-muted">
            Conversation memory: {status.data.conversation_turn_limit} turns · request metadata:{" "}
            {status.data.request_metadata_retention_days} days
          </p>
        </section>
      ) : null}
      {settings.data ? (
        <section className="rounded-panel border border-border bg-surface p-4" aria-label="AI model">
          <h2 className="font-semibold">Configured model</h2>
          <p className="mt-2 text-sm">
            {settings.data.logical_model} · provider configuration is managed outside this screen.
          </p>
        </section>
      ) : null}
      <section className="rounded-panel border border-border bg-surface p-4">
        <h2 className="font-semibold">Ask the Copilot</h2>
        <p className="mt-1 text-sm text-text-muted">Simulated data and knowledge remain clearly labelled.</p>
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!question.trim()) return;
            ask.mutate(
              { question },
              { onSuccess: (result) => setAnswer({ text: result.answer, simulated: result.simulated }) },
            );
          }}
        >
          <label htmlFor="ai-question" className="block text-sm font-medium">
            Question
          </label>
          <textarea
            id="ai-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={4}
            maxLength={2000}
            className="w-full rounded-control border border-border bg-surface p-3"
            placeholder="Ask about read-only operations"
          />
          <button
            className="min-h-11 rounded-control bg-primary px-4 text-primary-foreground disabled:opacity-50"
            disabled={ask.isPending || !question.trim()}
          >
            {ask.isPending ? "Asking…" : "Ask Copilot"}
          </button>
        </form>
        {ask.isError ? (
          <p role="alert" className="mt-3">
            The Copilot could not answer.
          </p>
        ) : null}
        {answer ? (
          <div className="mt-4 rounded-control border border-border p-3" aria-live="polite">
            <p className="text-xs text-text-muted">{answer.simulated ? "Simulated data" : "AI response"}</p>
            <p className="mt-1">{answer.text}</p>
          </div>
        ) : null}
      </section>
    </main>
  );
}
