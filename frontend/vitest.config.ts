import { defineConfig } from "vitest/config";
import { join } from "path";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
  },
  resolve: {
    alias: {
      "@": join(__dirname, "./src"),
    },
  },
});
