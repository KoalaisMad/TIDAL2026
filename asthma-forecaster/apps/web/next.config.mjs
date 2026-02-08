/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    // Prevent Next from picking an unrelated workspace root (multiple lockfiles).
    root: process.cwd(),
  },
};

export default nextConfig;
