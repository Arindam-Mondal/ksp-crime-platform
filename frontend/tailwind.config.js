/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ksp: {
          bg: "#0b1220",
          panel: "#141d2e",
          accent: "#3b82f6",
          danger: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
