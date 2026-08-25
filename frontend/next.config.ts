import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  distDir: process.env.NEXT_DIST_DIR || ".next",
  output: process.env.NEXT_OUTPUT_STANDALONE === "1" ? "standalone" : undefined,
  agentRules: false,
};

module.exports = nextConfig;
