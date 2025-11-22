import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Routes that require authentication
const protectedRoutes = ['/dashboard', '/chat', '/documents', '/tools', '/settings'];

// Routes that should redirect to dashboard if already authenticated
const authRoutes = ['/auth/login', '/auth/signup'];

// Routes that don't require server configuration
const publicRoutes = ['/server-setup', '/download'];

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Allow public routes
    if (publicRoutes.some(route => pathname.startsWith(route))) {
        return NextResponse.next();
    }

    // Since we're using localStorage for auth and server config (client-side only),
    // we can't check authentication or server config in middleware (server-side)
    // The components will handle the redirects if not authenticated or server not configured

    // Just allow all routes through - client-side guards will handle auth and server config
    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         * - public files (images, etc.)
         */
        '/((?!api|_next/static|_next/image|favicon.ico|.*\\.svg|.*\\.png|.*\\.jpg).*)',
    ],
};
