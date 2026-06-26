export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        felt: {
          50: "#e9f7f1",
          500: "#1d7c5b",
          700: "#13533f",
          900: "#092f27"
        },
        ink: "#172026",
        copper: "#b6673a"
      }
    },
  },
  plugins: [],
};
