import type { NextConfig } from "next";

const lanOrigin = process.env.NAMECRAFT_LAN_ORIGIN;

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: false,
  allowedDevOrigins: ["127.0.0.1", ...(lanOrigin ? [new URL(lanOrigin).hostname] : [])],
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};

export default nextConfig;
