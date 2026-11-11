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
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
