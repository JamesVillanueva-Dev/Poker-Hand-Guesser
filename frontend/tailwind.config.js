export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        felt: {
          50: "#eff9ff",
          500: "#38bdf8",
          700: "#0369a1",
          900: "#0c4a6e"
        },
        ink: "#102033",
        copper: "#2563eb"
      }
    },
  },
  plugins: [],
};
