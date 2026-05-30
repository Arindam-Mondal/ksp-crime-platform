import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, AskResponse } from "../lib/api";
import Panel from "../components/Panel";

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const ask = useMutation<AskResponse, Error, string>({ mutationFn: (q) => api.ask(q) });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Ask the Data</h1>
      <Panel title="Natural-language query (QuickML RAG in Phase 4)">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (question.trim()) ask.mutate(question.trim());
          }}
          className="flex gap-2"
        >
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Which districts have rising chain snatching?"
            className="flex-1 rounded bg-ksp-bg border border-white/10 px-3 py-2 text-sm outline-none focus:border-ksp-accent"
          />
          <button className="rounded bg-ksp-accent px-4 py-2 text-sm font-medium" disabled={ask.isPending}>
            {ask.isPending ? "Asking…" : "Ask"}
          </button>
        </form>

        {ask.data && (
          <div className="mt-4 space-y-3">
            <div className="rounded bg-ksp-bg border border-white/10 p-3 text-sm">
              {ask.data.answer}
              <div className="mt-2 text-xs text-white/40">
                provider: {ask.data.provider} · model: {ask.data.model}
              </div>
            </div>
            {ask.data.grounded_on.length > 0 && (
              <div>
                <div className="text-xs text-white/50 mb-1">Grounded on</div>
                <ul className="space-y-1 text-xs text-white/60">
                  {ask.data.grounded_on.map((g, i) => (
                    <li key={i} className="rounded bg-white/5 px-2 py-1">{g}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
        {ask.isError && <p className="mt-3 text-sm text-ksp-danger">{ask.error.message}</p>}
      </Panel>
    </div>
  );
}
