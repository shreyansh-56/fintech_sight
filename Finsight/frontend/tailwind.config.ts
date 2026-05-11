import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: [
    // Color scale - prevent purging of dynamic color classes used in ReportViewer
    { pattern: /^(bg|border|text|shadow)-(blue|indigo|cyan|emerald|violet|fuchsia|rose|amber|teal|green|slate)-(400|300|500)\/(10|20|30)$/ },
    { pattern: /^(bg|border|text|shadow)-(blue|indigo|cyan|emerald|violet|fuchsia|rose|amber|teal|green|slate)-(400|300|500)$/ },
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
      },
      backgroundOpacity: {
        8: "0.08",
        3: "0.03",
      },
    },
  },
  plugins: [],
};
export default config;
