import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
  agentRules: false,
  async headers() {
    return [
      { source: "/", headers: [{ key: "Cache-Control", value: "no-store, max-age=0" }] },
      { source: "/contracts", headers: [{ key: "Cache-Control", value: "no-store, max-age=0" }] },
    ];
  },
};

module.exports = nextConfig;
