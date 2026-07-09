/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,jsx,ts,tsx}", "./components/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#122033",
        muted: "#667085",
        line: "#d9e2ec",
        page: "#eef3f7",
        accent: "#0f766e",
        accentSoft: "#d9f2ee",
        blue: "#234e70",
      },
      boxShadow: {
        soft: "0 18px 48px rgba(18, 32, 51, 0.12)",
      },
    },
  },
  plugins: [],
};
