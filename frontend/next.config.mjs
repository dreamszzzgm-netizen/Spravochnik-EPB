/** @type {import('next').NextConfig} */
const nextConfig = {
  // Performance optimizations
  env: {
    NEXT_TELEMETRY_DISABLED: "1",
    SWC_CACHE: "1",
    WEBPACK_CACHE: "memory",
  },
  async rewrites() {
    const backendOrigin = process.env.BACKEND_ORIGIN || "http://127.0.0.1:8000";
    if (!/^https?:\/\/[^/]+$/i.test(backendOrigin)) {
      throw new Error("BACKEND_ORIGIN must be an HTTP(S) origin without a path");
    }
    return [{ source: "/backend/:path*", destination: `${backendOrigin}/:path*` }];
  },
  async headers() {
    return [
      {
        // Apply to all pages in the app
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'self';",
          },
          // NOTE: X-Frame-Options is legacy and does not support a wildcard;
          // if your platform injects X-Frame-Options: SAMEORIGIN you may need
          // to remove/override it via platform settings.
        ],
      },
    ];
  },
  distDir: ".next",
  // Build optimization
  experimental: {
    // Modern experimental features for Next.js 15
  },
  // Cache optimization
  onDemandEntries: {
    maxInactiveAge: 60 * 1000,
    pagesBufferLength: 2,
  },
  images: {
    // Disable remote patterns
    remotePatterns: [],
  },
};

export default nextConfig;
