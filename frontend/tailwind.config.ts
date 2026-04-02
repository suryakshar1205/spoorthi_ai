import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111111",
        cream: "#fbf6ef",
        sand: "#e8dac8",
        ember: "#d84e2f",
        ocean: "#0b6e74",
        pine: "#14342b"
      },
      boxShadow: {
        glow: "0 24px 60px rgba(12, 41, 34, 0.12)"
      },
      backgroundImage: {
        grid: "radial-gradient(circle at center, rgba(17,17,17,0.08) 1px, transparent 1px)"
      }
    }
  },
  plugins: []
};

export default config;
