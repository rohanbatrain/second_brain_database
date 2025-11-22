/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://localhost:8000/api/v1/:path*', // Proxy to FastAPI
            },
            // Also proxy direct calls if needed, depending on how the API is structured
            // The user requested: destination: 'http://localhost:8000/api/v1/:path*'
            // But let's check if the backend prefix is actually /api/v1
            // Looking at main.py, it includes routers directly.
            // Usually main_router has the prefix.
            // Let's assume the user knows what they are talking about, but I should verify if I can.
            // For now, I will follow the plan.
        ]
    },
}

module.exports = nextConfig
