// @ts-check
import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

// SITE_URL et BASE_PATH sont fournis par le déploiement (voir .github/workflows/deploy.yml).
// En local : http://localhost:4321/
const site = process.env.SITE_URL || "https://example.com";
const base = process.env.BASE_PATH || "/";

export default defineConfig({
  site,
  base,
  trailingSlash: "ignore",
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      // Coloration du code adaptée au thème clair et sombre.
      themes: { light: "github-light", dark: "github-dark-dimmed" },
      wrap: false,
    },
  },
});
