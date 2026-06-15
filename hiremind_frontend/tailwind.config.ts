import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#060b14",
        surface: "#0d1623",
        card: "#101e30",
        border: "#1a2f47",
        accent: "#00d4ff",
        gold: "#f0b429",
        green: "#00e5a0",
        red: "#ff4e6a",
        purple: "#9d7aff",
        muted: "#6b8299",
      },
      fontFamily: {
        sans: ["var(--font-syne)", "system-ui", "sans-serif"],
        mono: ["var(--font-dm-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
