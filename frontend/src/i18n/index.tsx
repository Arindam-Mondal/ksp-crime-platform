/**
 * Bilingual (English / Kannada) support.
 *
 * Karnataka State Police officers work in Kannada; English is the default and the
 * guaranteed fallback. The governing rule (see the design doc) is that **language is a
 * render-time concern, never a cache key** — the backend keeps serving English-keyed
 * aggregates behind its `@cached` warm set, and translation happens here at paint.
 *
 * Deliberately hand-rolled rather than react-i18next: two static locales, ~250 keys and
 * no plural complexity. `kn` is typed as `Record<TranslationKey, string>`, which turns a
 * missing Kannada string into a `npm run typecheck` failure — the strongest completeness
 * guarantee available in a repo with no frontend test infra.
 */
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { en, TranslationKey } from "./en";
import { kn } from "./kn";

export type Lang = "en" | "kn";

export const LANGS: { code: Lang; label: string; short: string }[] = [
  { code: "en", label: "English", short: "EN" },
  { code: "kn", label: "ಕನ್ನಡ", short: "ಕ" },
];

const CATALOGS: Record<Lang, Record<TranslationKey, string>> = { en, kn };

const STORAGE_KEY = "ksp.lang";

function initialLang(): Lang {
  if (typeof window === "undefined") return "en";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "kn" ? "kn" : "en";
}

/** Interpolate `{{name}}` placeholders. Values are stringified as-is — numerals stay
 *  Western in both languages (police records use Western digits). */
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (match, key: string) =>
    key in params ? String(params[key]) : match
  );
}

export type TFunction = (
  key: TranslationKey,
  params?: Record<string, string | number>
) => string;

interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TFunction;
  /**
   * Translate a key that is only known at runtime — backend `template` fields such as
   * `"anomaly.volume"`. Falls back to `fallback` (the backend's English `description`)
   * when the key is not in the catalog, so an un-templated server response still reads.
   */
  tDynamic: (
    key: string,
    params?: Record<string, string | number>,
    fallback?: string
  ) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);

  // Kannada glyphs need Noto Sans Kannada and a roomier line-height; `.lang-kn` on
  // <html> scopes that (see index.css). `lang` also drives hyphenation and a11y tooling.
  useEffect(() => {
    const root = document.documentElement;
    root.lang = lang;
    root.classList.toggle("lang-kn", lang === "kn");
  }, [lang]);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Private mode / storage disabled — the choice just won't survive a reload.
    }
  }, []);

  const value = useMemo<I18nValue>(() => {
    const catalog = CATALOGS[lang];
    return {
      lang,
      setLang,
      t: (key, params) => interpolate(catalog[key] ?? en[key] ?? key, params),
      tDynamic: (key, params, fallback) => {
        const entry =
          (catalog as Record<string, string>)[key] ?? (en as Record<string, string>)[key];
        if (entry === undefined) return fallback ?? key;
        return interpolate(entry, params);
      },
    };
  }, [lang, setLang]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}

/** The common case: `const t = useT();` then `t("nav.dashboard")`. */
export function useT(): TFunction {
  return useI18n().t;
}

/** For components that need the active language itself (API calls, query keys). */
export function useLang(): { lang: Lang; setLang: (lang: Lang) => void } {
  const { lang, setLang } = useI18n();
  return { lang, setLang };
}

/** For rendering backend-supplied `template` + `params` pairs. */
export function useTDynamic(): I18nValue["tDynamic"] {
  return useI18n().tDynamic;
}

export type { TranslationKey };
