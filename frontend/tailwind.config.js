/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        // App surfaces — layered dark "command surface"
        bg: "#0a0e17",
        surface: { DEFAULT: "#111726", 2: "#19223a" },
        line: { DEFAULT: "#1e2840", strong: "#2c3a5c" },
        muted: "#8a94ad",
        // Accent ramp (indigo-blue) + semantic signals
        accent: { DEFAULT: "#5b7fff", soft: "#869bff", hover: "#4965e6" },
        success: "#10b981",
        warning: "#f59e0b",
        danger: "#ef4444",
        info: "#38bdf8",
        // Back-compat aliases (legacy ksp.* references map to new tokens)
        ksp: { bg: "#0a0e17", panel: "#111726", accent: "#5b7fff", danger: "#ef4444" },
      },
      borderRadius: { xl: "0.75rem", "2xl": "1rem" },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,0.35), 0 8px 28px -14px rgba(0,0,0,0.55)",
        "card-hover": "0 2px 6px rgba(0,0,0,0.4), 0 18px 44px -18px rgba(0,0,0,0.65)",
        glow: "0 0 0 1px rgba(91,127,255,0.35), 0 0 26px -4px rgba(91,127,255,0.45)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.4", transform: "scale(0.85)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out both",
        "fade-in-up": "fade-in-up 0.5s cubic-bezier(0.22, 1, 0.36, 1) both",
        "pulse-dot": "pulse-dot 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
