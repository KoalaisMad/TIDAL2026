import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  turbopack: {
    // Prevent Next from picking an unrelated workspace root (multiple lockfiles).
    root: process.cwd(),
  },
};

export default nextConfig;
