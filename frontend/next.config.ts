import type { NextConfig } from "next";

/**
 * Static export: the frontend is a pure client of the FastAPI backend, so it
 * deploys to any static host. Dynamic data lives behind NEXT_PUBLIC_API_BASE_URL.
 *
 * Note: `cacheComponents` / `partialPrefetching` (enabled by the scaffold) need a
 * Node.js server runtime and are intentionally not used with `output: "export"`.
 */
// GitHub Pages serves project sites under /<repo>/, so the base path is injected at build time.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || undefined;

const nextConfig: NextConfig = {
  output: "export",
  basePath,
  trailingSlash: true,
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
