# 🚀 IPAM Frontend Quick Start Guide

## Prerequisites

- **Bun** >= 1.0.0 ([Install Bun](https://bun.sh))
- **Node.js** >= 18.0.0 (for compatibility)
- **Git**

## Step 1: Initialize Project

```bash
cd submodules/IPAM

# Initialize Next.js with Bun
bun create next-app . --typescript --tailwind --app --src-dir --import-alias "@/*"

# Answer prompts:
# ✔ Would you like to use ESLint? … Yes
# ✔ Would you like to use Turbopack? … No
# ✔ Would you like to customize the default import alias? … No
```

## Step 2: Install Dependencies

```bash
# Core dependencies
bun add next@latest react@latest react-dom@latest

# State & Data Fetching
bun add zustand @tanstack/react-query @tanstack/react-query-devtools

# Forms & Validation
bun add react-hook-form @hookform/resolvers zod

# UI Components
bun add @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-select
bun add @radix-ui/react-tabs @radix-ui/react-toast @radix-ui/react-tooltip
bun add @radix-ui/react-progress @radix-ui/react-avatar @radix-ui/react-badge

# Styling & Theming
bun add tailwindcss-animate class-variance-authority clsx tailwind-merge
bun add next-themes

# Charts & Visualization
bun add recharts

# Tables
bun add @tanstack/react-table

# API Client
bun add axios

# Icons
bun add lucide-react

# Utilities
bun add date-fns sonner

# Animations
bun add framer-motion

# Dev Dependencies
bun add -d @types/node @types/react @types/react-dom
bun add -d typescript eslint eslint-config-next
bun add -d prettier prettier-plugin-tailwindcss
bun add -d @playwright/test vitest @testing-library/react @testing-library/jest-dom
```

## Step 3: Initialize shadcn/ui

```bash
# Initialize shadcn/ui
bunx shadcn-ui@latest init

# Answer prompts:
# ✔ Which style would you like to use? › Default
# ✔ Which color would you like to use as base color? › Slate
# ✔ Would you like to use CSS variables for colors? › yes

# Add essential components
bunx shadcn-ui@latest add button
bunx shadcn-ui@latest add card
bunx shadcn-ui@latest add input
bunx shadcn-ui@latest add label
bunx shadcn-ui@latest add select
bunx shadcn-ui@latest add textarea
bunx shadcn-ui@latest add dialog
bunx shadcn-ui@latest add dropdown-menu
bunx shadcn-ui@latest add table
bunx shadcn-ui@latest add tabs
bunx shadcn-ui@latest add toast
bunx shadcn-ui@latest add progress
bunx shadcn-ui@latest add badge
bunx shadcn-ui@latest add avatar
bunx shadcn-ui@latest add skeleton
bunx shadcn-ui@latest add form
```

## Step 4: Project Structure Setup

```bash
# Create directory structure
mkdir -p app/\(auth\)/login
mkdir -p app/\(auth\)/signup
mkdir -p app/\(dashboard\)/countries
mkdir -p app/\(dashboard\)/regions
mkdir -p app/\(dashboard\)/hosts
mkdir -p app/\(dashboard\)/search
mkdir -p app/\(dashboard\)/analytics
mkdir -p app/\(dashboard\)/audit
mkdir -p app/\(dashboard\)/settings

mkdir -p components/core
mkdir -p components/ipam
mkdir -p components/forms
mkdir -p components/theme

mkdir -p lib/api
mkdir -p lib/hooks
mkdir -p lib/store
mkdir -p lib/themes
mkdir -p lib/utils
mkdir -p lib/types

mkdir -p styles
mkdir -p public/icons
```

## Step 5: Configuration Files

### Create `providers.tsx`

```typescript
// providers.tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ThemeProvider } from '@/components/theme/theme-provider';
import { Toaster } from '@/components/ui/sonner';
import { useState } from 'react';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="violet"
        enableSystem
        disableTransitionOnChange
      >
        {children}
        <Toaster />
      </ThemeProvider>
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

### Update `app/layout.tsx`

```typescript
// app/layout.tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { Providers } from '@/providers';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'IPAM - IP Address Management',
  description: 'Hierarchical IP allocation management system',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
```

### Create `.env.local`

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=IPAM
NEXT_PUBLIC_APP_VERSION=1.0.0
```

### Update `tailwind.config.ts`

```typescript
// tailwind.config.ts
import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        region: {
          active: 'hsl(var(--region-active))',
          reserved: 'hsl(var(--region-reserved))',
          retired: 'hsl(var(--region-retired))',
        },
        utilization: {
          low: 'hsl(var(--utilization-low))',
          medium: 'hsl(var(--utilization-medium))',
          high: 'hsl(var(--utilization-high))',
        },
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
};

export default config;
```

## Step 6: Create Core Files

### API Client

```bash
# Create lib/api/client.ts
cat > lib/api/client.ts << 'EOF'
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for auth token
apiClient.interceptors.request.use(
  (config) => {
    // Token will be added by auth store
    return config;
  },
  (error) => Promise.reject(error)
);

export default apiClient;
EOF
```

### Auth Store

```bash
# Create lib/store/auth-store.ts
cat > lib/store/auth-store.ts << 'EOF'
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  user: any | null;
  accessToken: string | null;
  isAuthenticated: boolean;
  login: (credentials: any) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      isAuthenticated: false,
      login: async (credentials) => {
        // TODO: Implement login
        set({ isAuthenticated: true });
      },
      logout: () => {
        set({ user: null, accessToken: null, isAuthenticated: false });
      },
    }),
    {
      name: 'ipam-auth-storage',
    }
  )
);
EOF
```

## Step 7: Run Development Server

```bash
# Start development server
bun run dev

# Open browser
open http://localhost:3000
```

## Step 8: Verify Setup

✅ Check that the development server starts without errors  
✅ Verify Tailwind CSS is working  
✅ Confirm shadcn/ui components are accessible  
✅ Test theme switching (if implemented)  

## Next Steps

1. **Implement Authentication** - Start with login/signup pages
2. **Create API Services** - Build API client modules for each resource
3. **Build Core Components** - Implement IPAM-specific components
4. **Add Routing** - Set up dashboard routes
5. **Integrate Backend** - Connect to FastAPI backend

## Useful Commands

```bash
# Development
bun run dev              # Start dev server
bun run build            # Build for production
bun run start            # Start production server

# Code Quality
bun run lint             # Run ESLint
bun run format           # Format with Prettier
bun run type-check       # TypeScript type checking

# Testing
bun test                 # Run unit tests
bun run test:e2e         # Run E2E tests

# Add shadcn/ui components
bunx shadcn-ui@latest add [component-name]
```

## Troubleshooting

### Bun not found
```bash
curl -fsSL https://bun.sh/install | bash
```

### Port 3000 already in use
```bash
# Use different port
bun run dev -- -p 3001
```

### Module not found errors
```bash
# Clear cache and reinstall
rm -rf node_modules bun.lockb
bun install
```

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [Bun Documentation](https://bun.sh/docs)
- [shadcn/ui Documentation](https://ui.shadcn.com)
- [TanStack Query Documentation](https://tanstack.com/query/latest)
- [Zustand Documentation](https://zustand-demo.pmnd.rs)

---

**Ready to build!** 🚀 Follow the implementation roadmap in `FRONTEND_ARCHITECTURE_PLAN.md` for detailed guidance.
