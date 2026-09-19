import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "var(--canvas)",
        panel: "var(--panel)",
        elevated: "var(--elevated)",
        border: "var(--border)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
      },
    },
  },
  plugins: [],
} satisfies Config;
