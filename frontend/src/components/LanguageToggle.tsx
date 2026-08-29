import { LANGS, useLang, useT } from "../i18n";
import Tooltip from "./Tooltip";

/**
 * EN ⇄ ಕನ್ನಡ switcher.
 *
 * Two variants, because the sidebar has two widths:
 *  - `segmented` — both options visible, current one highlighted (expanded sidebar,
 *    mobile top bar). A segmented control rather than a dropdown: with exactly two
 *    options, showing the alternative is cheaper than opening a menu, and a Kannada
 *    speaker landing on the English default can see their language without reading it.
 *  - `compact` — one button showing the *other* language, for the collapsed rail.
 */
export default function LanguageToggle({
  variant = "segmented",
  className = "",
}: {
  variant?: "segmented" | "compact";
  className?: string;
}) {
  const { lang, setLang } = useLang();
  const t = useT();

  if (variant === "compact") {
    const other = LANGS.find((l) => l.code !== lang)!;
    return (
      <Tooltip label={t("lang.switchTo", { language: other.label })}>
        <button
          type="button"
          onClick={() => setLang(other.code)}
          aria-label={t("lang.switchTo", { language: other.label })}
          className={`grid h-10 w-full place-items-center rounded-xl border border-line bg-surface-2/60 text-xs font-bold text-white/80 transition-colors hover:border-line-strong hover:text-white ${className}`}
        >
          {other.short}
        </button>
      </Tooltip>
    );
  }

  return (
    <div
      role="group"
      aria-label={t("lang.label")}
      className={`flex items-center gap-0.5 rounded-xl border border-line bg-surface-2/60 p-0.5 ${className}`}
    >
      {LANGS.map((l) => {
        const active = l.code === lang;
        return (
          <button
            key={l.code}
            type="button"
            onClick={() => setLang(l.code)}
            aria-pressed={active}
            aria-label={t("lang.switchTo", { language: l.label })}
            className={`flex-1 rounded-[10px] px-2 py-1.5 text-xs font-semibold transition-colors ${
              active
                ? "bg-accent/15 text-accent-soft"
                : "text-muted hover:bg-white/[0.04] hover:text-white/80"
            }`}
          >
            {l.label}
          </button>
        );
      })}
    </div>
  );
}
