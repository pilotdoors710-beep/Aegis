import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // Static trap arena lives in public/arena; serve clean URLs.
    return [{ source: "/arena", destination: "/arena/index.html" }];
  },
  modularizeImports: {
    "@designcodeio/threeui": {
      transform: "@designcodeio/threeui/components/{{member}}",
      skipDefaultConversion: true,
    },
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        // Let Next.js preserve class exports and scoping for plain CSS modules and third-party packages.
        condition: {
          all: [
            { not: { path: "*.module.css" } },
            { not: { path: "**/node_modules/**" } },
          ],
        },
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
