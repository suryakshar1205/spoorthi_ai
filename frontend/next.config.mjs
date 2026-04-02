/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  experimental: {
    optimizePackageImports: ["lucide-react"]
  }
};

export default nextConfig;
