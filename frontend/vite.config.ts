import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// SPA живёт под /admin/ui/, API — под /admin/* и /auth/*
export default defineConfig({
  plugins: [react()],
  base: "/admin/ui/",
  server: {
    port: 5173,
    proxy: {
      // всё /admin/*, кроме самого SPA
      "^/admin/(?!ui(/|$))": { target: "http://localhost:8002" },
      "/auth": { target: "http://localhost:8002" },
    },
  },
});
