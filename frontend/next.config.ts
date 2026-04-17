import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  turbopack: {
    resolveAlias: {
      "@framework": path.resolve(__dirname, "lib/live2d/framework"),
    },
  },
};

export default nextConfig;
