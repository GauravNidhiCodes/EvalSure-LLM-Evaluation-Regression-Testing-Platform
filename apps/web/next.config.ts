import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enables smaller production images via apps/web/Dockerfile (standalone output).
  // Local `npm run dev` is unchanged.
  output: "standalone",
};

export default nextConfig;
