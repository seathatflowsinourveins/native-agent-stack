import type { NextConfig } from 'next';

const config: NextConfig = {
  poweredByHeader: false,
  async rewrites() {
    return [{ source: '/api/:path*', destination: 'http://127.0.0.1:18081/:path*' }];
  },
};
export default config;
