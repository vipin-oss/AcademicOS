import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Frozen design tokens (UX Prototype Spec §1.2): single indigo accent.
        accent: {
          DEFAULT: "#5B5BD6",
          hover: "#4F4FC9",
          subtle: "#EEEEFB",
        },
        ink: {
          primary: "#1A1A1A",
          secondary: "#6B6B6B",
          tertiary: "#9C9C9C",
        },
        line: {
          subtle: "#ECECEC",
          strong: "#DCDCDA",
        },
        surface: {
          app: "#F7F7F5",
          card: "#FFFFFF",
          sunken: "#FBFBFA",
        },
        success: "#18794E",
        warning: "#B25C00",
        danger: "#C0392B",
        info: "#2563EB",
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0,0,0,0.04)",
        md: "0 4px 14px rgba(0,0,0,0.06)",
        lg: "0 16px 40px rgba(0,0,0,0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
