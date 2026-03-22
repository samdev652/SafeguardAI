/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ['react-leaflet'],
  },
  webpack: (config, { dev }) => {
    if (dev) {
      // Avoid intermittent .next chunk/cache corruption in local dev sessions.
      config.cache = false;
    }
    return config;
  },
};

export default nextConfig;
