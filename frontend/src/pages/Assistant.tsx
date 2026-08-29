import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Sparkles, Send, Loader2, MessageSquareText, AlertTriangle, FileText } from "lucide-react";
import { api, AskResponse } from "../lib/api";
import Panel from "../components/Panel";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import Badge from "../components/Badge";
import { useLang, useT, type TranslationKey } from "../i18n";

const EXAMPLE_KEYS: TranslationKey[] = [
  "assistant.example1",
  "assistant.example2",
  "assistant.example3",
];

export default function Assistant() {
  const [question, setQuestion] = useState("");
  const t = useT();
  const { lang } = useLang();
  // The answer is generated, not cached — asking again after a language switch is a
  // fresh call by design, and `lang` rides along so the model replies in Kannada.
  const ask = useMutation<AskResponse, Error, string>({ mutationFn: (q) => api.ask(q, lang) });

  const submit = (q: string) => {
    const trimmed = q.trim();
    if (trimmed) ask.mutate(trimmed);
  };

  return (
    <div className="space-y-7">
      <PageHeader
        icon={Sparkles}
        eyebrow={t("assistant.eyebrow")}
        title={t("assistant.title")}
        subtitle={t("assistant.subtitle")}
      />

      <Panel icon={MessageSquareText} title={t("assistant.panel")}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit(question);
          }}
          className="flex gap-2.5"
        >
          {/* min-w-0: flex items default to min-width:auto, and an <input>'s
              intrinsic size would push the button off a 375px screen */}
          <div className="relative min-w-0 flex-1">
            <Sparkles size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-accent-soft" />
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("assistant.placeholder")}
              className="w-full rounded-xl border border-line bg-bg/60 py-3 pl-10 pr-3 text-sm text-white/90 outline-none transition-colors placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </div>
          <button
            type="submit"
            disabled={ask.isPending || !question.trim()}
            className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-accent px-4 py-3 text-sm font-semibold text-white shadow-glow transition-all hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50 sm:px-5"
          >
            {ask.isPending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            <span className="hidden sm:inline">
              {ask.isPending ? t("assistant.asking") : t("assistant.ask")}
            </span>
            <span className="sr-only sm:hidden">
              {ask.isPending ? t("assistant.asking") : t("assistant.ask")}
            </span>
          </button>
        </form>

        {/* Intro / example prompts */}
        {!ask.data && !ask.isError && !ask.isPending && (
          <div className="mt-5">
            <EmptyState
              icon={MessageSquareText}
              title={t("assistant.emptyTitle")}
              hint={t("assistant.emptyHint")}
            >
              <div className="flex flex-wrap justify-center gap-2">
                {EXAMPLE_KEYS.map((key) => {
                  const ex = t(key);
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        setQuestion(ex);
                        submit(ex);
                      }}
                      className="rounded-full border border-line bg-surface-2/60 px-3.5 py-1.5 text-xs text-white/80 transition-all hover:border-accent/40 hover:text-white"
                    >
                      {ex}
                    </button>
                  );
                })}
              </div>
            </EmptyState>
          </div>
        )}

        {ask.isPending && (
          <div className="mt-5 flex items-center gap-3 rounded-xl border border-line bg-surface-2/40 px-4 py-4 text-sm text-muted">
            <Loader2 size={16} className="animate-spin text-accent-soft" />
            {t("assistant.thinking")}
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
                <Badge variant="neutral">{t("assistant.model", { model: ask.data.model })}</Badge>
              </div>
            </div>

            {ask.data.grounded_on.length > 0 && (
              <div>
                <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
                  <FileText size={13} /> {t("assistant.groundedOn")}
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
