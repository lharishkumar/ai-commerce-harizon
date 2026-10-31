import type { Config } from "tailwindcss";
const config: Config = { content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"], theme: { extend: { colors: { ink: "#14231f", paper: "#f7f7f2", moss: "#24483e", lime: "#d6f36a" }, fontFamily: { sans: ["Arial", "Helvetica", "sans-serif"] } } }, plugins: [] };
export default config;
