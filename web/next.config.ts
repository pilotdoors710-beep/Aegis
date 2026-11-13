import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Static trap arena lives in public/arena; serve clean URLs.
    return [{ source: "/arena", destination: "/arena/index.html" }];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        // Let Next.js preserve class exports and scoping for plain CSS modules.
        condition: { not: { path: "*.module.css" } },
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
