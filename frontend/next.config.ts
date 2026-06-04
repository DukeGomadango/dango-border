import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  assetPrefix: process.env.VERCEL ? undefined : "/ui",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
