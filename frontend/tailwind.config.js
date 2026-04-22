/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        fair: {
          green: "#147d64",
          yellow: "#d97706",
          red: "#b42318",
          ink: "#102a43",
          surface: "#fffef8",
        },
      },
      boxShadow: {
        glow: "0 20px 50px rgba(16, 42, 67, 0.12)",
      },
      fontFamily: {
        heading: ["Sora", "sans-serif"],
        body: ["Sora", "sans-serif"],
        mono: ["IBM Plex Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
