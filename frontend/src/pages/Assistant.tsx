import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles, Send, Loader2, MessageSquareText, AlertTriangle, FileText } from "lucide-react";
import { api, AskResponse } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";

const EXAMPLES = [
  "Which districts have rising chain snatching?",
  "Summarise the top crime hotspots this quarter.",
  "Which repeat offenders are most connected?",
];

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const ask = useMutation<AskResponse, Error, string>({ mutationFn: (q) => api.ask(q) });

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (trimmed) ask.mutate(trimmed);
  };

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Sparkles}
        eyebrow="Natural-Language Intelligence"
        title="Ask the Data"
        subtitle="Query incidents in plain language — grounded answers via QuickML RAG"
      />

      <Panel icon={MessageSquareText} title="Conversational query">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(question);
          }}
          className="flex gap-2.5"
        >
          <div className="relative flex-1">
            <Sparkles size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-accent-soft" />
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask about districts, hotspots, offenders, trends…"
              className="w-full rounded-xl border border-line bg-bg/60 py-3 pl-10 pr-3 text-sm text-white/90 outline-none transition-colors placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </div>
          <button
            type="submit"
            disabled={ask.isPending || !question.trim()}
            className="inline-flex items-center gap-2 rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-glow transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            {ask.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            {ask.isPending ? "Asking…" : "Ask"}
          </button>
        </form>

        {/* Intro / example prompts */}
        {!ask.data && !ask.isError && !ask.isPending && (
          <div className="mt-5">
            <EmptyState
              icon={MessageSquareText}
              title="Start a conversation with the data"
              hint="Ask in natural language. Answers are grounded on precomputed aggregates — try one of these:"
            >
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => {
                      setQuestion(ex);
                      submit(ex);
                    }}
                    className="rounded-full border border-line bg-surface-2/60 px-3.5 py-1.5 text-xs text-white/80 transition-all hover:border-accent/40 hover:text-white"
                  >
                    {ex}
                  </button>
                ))}
              </div>
            </EmptyState>
          </div>
        )}

        {ask.isPending && (
          <div className="mt-5 flex items-center gap-3 rounded-xl border border-line bg-surface-2/40 px-4 py-4 text-sm text-muted">
            <Loader2 size={16} className="animate-spin text-accent-soft" />
            Analysing aggregates and composing a grounded answer…
          </div>
        )}

        {ask.data && (
          <div className="mt-5 space-y-4 animate-fade-in-up">
            <div className="rounded-xl border border-line bg-surface-2/50 p-4">
              <p className="text-sm leading-relaxed text-white/90">{ask.data.answer}</p>
              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                <Badge variant="accent" dot>
                  {ask.data.provider}
                </Badge>
                <Badge variant="neutral">model · {ask.data.model}</Badge>
              </div>
            </div>

            {ask.data.grounded_on.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                  <FileText size={13} /> Grounded on
                </div>
                <div className="flex flex-wrap gap-2">
                  {ask.data.grounded_on.map((g, i) => (
                    <Badge key={i} variant="info">
                      {g}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {ask.isError && (
          <div className="mt-5 flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger animate-fade-in">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" />
            <span>{ask.error.message}</span>
          </div>
        )}
      </Panel>
    </div>
  );
}
