/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    swcMinify: true,
    // Ensure we can proxy to our FastAPI backend easily in dev
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://127.0.0.1:8000/api/:path*' // Proxy to Python FastAPI
            }
        ]
    }
};

export default nextConfig;
