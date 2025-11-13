# 🎯 IPAM Frontend Architecture Plan
## Production-Ready Next.js Application with Bun

---

## 📋 Executive Summary

This document outlines the complete frontend architecture for the **IPAM (IP Address Management)** system, a hierarchical IP allocation platform managing the `10.X.Y.Z` private IPv4 address space. The frontend will be built with **Next.js 14+**, styled with **Tailwind CSS + shadcn/ui**, and scaffolded using **Bun** for maximum performance.

### Key Features
- **Hierarchical IP Management**: Continent → Country → Region → Host visualization
- **Real-time Utilization Dashboards**: Interactive charts and capacity monitoring
- **Advanced Search & Filtering**: Multi-criteria search with pagination
- **Batch Operations**: Bulk host creation and release
- **Audit Trail Visualization**: Complete history tracking
- **Theme System**: Emotion-inspired themes (violet, emerald, sunset, etc.)
- **Role-Based Access Control**: Permission-aware UI components

---

## 🏗️ Technology Stack

### Core Framework
| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Framework** | Next.js 14+ (App Router) | Modern SSR + CSR hybrid |
| **Runtime** | Bun | Ultra-fast package manager & runtime |
| **UI System** | Tailwind CSS + shadcn/ui | Utility-first styling + composable components |
| **Theme Engine** | next-themes + custom tokens | Emotion-inspired color palettes |
| **State Management** | Zustand | Lightweight global state |
| **Data Fetching** | TanStack Query (React Query) | Server-state caching & syncing |
| **Forms** | React Hook Form + Zod | Type-safe validation |
| **Charts** | Recharts | Utilization & analytics visualization |
| **Tables** | TanStack Table | Advanced data grids with sorting/filtering |
| **Icons** | Lucide React | Modern icon set |
| **Animations** | Framer Motion | Fluid transitions |

---

## 📁 Project Structure

```
submodules/IPAM/
├── app/                          # Next.js App Router
│   ├── layout.tsx                # Root layout with providers
│   ├── page.tsx                  # Dashboard home
│   ├── (auth)/                   # Auth routes (login/signup)
│   │   ├── login/
│   │   └── signup/
│   ├── (dashboard)/              # Protected dashboard routes
│   │   ├── layout.tsx            # Dashboard layout with sidebar
│   │   ├── countries/            # Country management
│   │   │   ├── page.tsx          # List countries
│   │   │   └── [country]/        # Country details & utilization
│   │   ├── regions/              # Region management
│   │   │   ├── page.tsx          # List regions
│   │   │   ├── create/           # Create region
│   │   │   └── [regionId]/       # Region details & hosts
│   │   ├── hosts/                # Host management
│   │   │   ├── page.tsx          # List hosts
│   │   │   ├── create/           # Create host
│   │   │   ├── batch/            # Batch create
│   │   │   └── [hostId]/         # Host details
│   │   ├── search/               # Advanced search
│   │   ├── analytics/            # Utilization analytics
│   │   ├── audit/                # Audit history
│   │   └── settings/             # User settings & quotas
│   └── api/                      # API route handlers (if needed)
├── components/
│   ├── ui/                       # shadcn/ui components
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── form.tsx
│   │   └── ...
│   ├── core/                     # Layout components
│   │   ├── navbar.tsx
│   │   ├── sidebar.tsx
│   │   ├── breadcrumbs.tsx
│   │   └── footer.tsx
│   ├── ipam/                     # IPAM-specific components
│   │   ├── country-card.tsx
│   │   ├── region-card.tsx
│   │   ├── host-card.tsx
│   │   ├── ip-hierarchy-tree.tsx
│   │   ├── utilization-chart.tsx
│   │   ├── capacity-gauge.tsx
│   │   ├── allocation-timeline.tsx
│   │   └── audit-log-viewer.tsx
│   ├── forms/                    # Form components
│   │   ├── region-create-form.tsx
│   │   ├── host-create-form.tsx
│   │   ├── batch-host-form.tsx
│   │   └── search-form.tsx
│   └── theme/                    # Theme components
│       ├── theme-provider.tsx
│       ├── theme-toggle.tsx
│       └── theme-palette-picker.tsx
├── lib/
│   ├── api/                      # API client
│   │   ├── client.ts             # Axios instance with interceptors
│   │   ├── countries.ts          # Country endpoints
│   │   ├── regions.ts            # Region endpoints
│   │   ├── hosts.ts              # Host endpoints
│   │   ├── search.ts             # Search endpoints
│   │   ├── audit.ts              # Audit endpoints
│   │   └── auth.ts               # Auth endpoints
│   ├── hooks/                    # Custom hooks
│   │   ├── use-auth.ts
│   │   ├── use-theme.ts
│   │   ├── use-countries.ts
│   │   ├── use-regions.ts
│   │   ├── use-hosts.ts
│   │   ├── use-search.ts
│   │   └── use-pagination.ts
│   ├── store/                    # Zustand stores
│   │   ├── auth-store.ts
│   │   ├── ui-store.ts
│   │   └── theme-store.ts
│   ├── themes/                   # Theme definitions
│   │   ├── index.ts
│   │   ├── violet.ts
│   │   ├── emerald.ts
│   │   ├── sunset.ts
│   │   ├── amber.ts
│   │   └── dusk.ts
│   ├── utils/                    # Utility functions
│   │   ├── cn.ts                 # Class name merger
│   │   ├── format.ts             # Formatters (IP, date, etc.)
│   │   ├── validation.ts         # Validators
│   │   └── constants.ts          # Constants
│   └── types/                    # TypeScript types
│       ├── ipam.ts               # IPAM domain types
│       ├── api.ts                # API response types
│       └── theme.ts              # Theme types
├── styles/
│   ├── globals.css               # Global styles + CSS variables
│   └── themes.css                # Theme-specific styles
├── public/
│   ├── icons/
│   └── images/
├── providers.tsx                 # App-level providers
├── middleware.ts                 # Auth middleware
├── next.config.js
├── tailwind.config.ts
├── tsconfig.json
├── package.json
└── bun.lockb
```

---

## 🎨 Theme System (Emotion-Inspired)

### Design Philosophy
Themes represent **moods and energy states**, inspired by the emotion_tracker design:
- **Violet** → Calm, creative, focused
- **Emerald** → Balanced, growth, stability
- **Sunset** → Warm, energetic, optimistic
- **Amber** → Bright, alert, productive
- **Dusk** → Deep, contemplative, sophisticated

### Theme Structure

```typescript
// lib/themes/index.ts
export interface ThemeTokens {
  name: string;
  mode: 'light' | 'dark';
  colors: {
    // Semantic tokens
    background: string;
    foreground: string;
    card: string;
    cardForeground: string;
    popover: string;
    popoverForeground: string;
    primary: string;
    primaryForeground: string;
    secondary: string;
    secondaryForeground: string;
    muted: string;
    mutedForeground: string;
    accent: string;
    accentForeground: string;
    destructive: string;
    destructiveForeground: string;
    border: string;
    input: string;
    ring: string;
    // IPAM-specific tokens
    regionActive: string;
    regionReserved: string;
    regionRetired: string;
    hostActive: string;
    hostReleased: string;
    utilizationLow: string;      // < 50%
    utilizationMedium: string;   // 50-80%
    utilizationHigh: string;     // > 80%
  };
  shadows: {
    sm: string;
    md: string;
    lg: string;
  };
  radius: {
    sm: string;
    md: string;
    lg: string;
  };
}

// Example: Violet theme
export const violetTheme: ThemeTokens = {
  name: 'violet',
  mode: 'light',
  colors: {
    background: 'hsl(240 10% 98%)',
    foreground: 'hsl(240 10% 10%)',
    primary: 'hsl(262 83% 58%)',
    primaryForeground: 'hsl(0 0% 100%)',
    // ... rest of tokens
    regionActive: 'hsl(142 76% 36%)',
    regionReserved: 'hsl(48 96% 53%)',
    regionRetired: 'hsl(0 72% 51%)',
    utilizationLow: 'hsl(142 76% 36%)',
    utilizationMedium: 'hsl(48 96% 53%)',
    utilizationHigh: 'hsl(0 72% 51%)',
  },
  // ...
};
```

### Theme Integration

```typescript
// components/theme/theme-provider.tsx
'use client';

import { ThemeProvider as NextThemesProvider } from 'next-themes';
import { useEffect } from 'react';
import { useThemeStore } from '@/lib/store/theme-store';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { currentTheme, applyTheme } = useThemeStore();

  useEffect(() => {
    applyTheme(currentTheme);
  }, [currentTheme, applyTheme]);

  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="violet"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </NextThemesProvider>
  );
}
```

### CSS Variables Injection

```css
/* styles/globals.css */
:root {
  /* Injected dynamically by theme system */
  --background: 240 10% 98%;
  --foreground: 240 10% 10%;
  --primary: 262 83% 58%;
  /* ... */
  --region-active: 142 76% 36%;
  --utilization-low: 142 76% 36%;
  --utilization-medium: 48 96% 53%;
  --utilization-high: 0 72% 51%;
}

.dark {
  --background: 240 10% 10%;
  --foreground: 240 10% 98%;
  /* ... */
}
```

---

## 🔐 Authentication & Authorization

### Auth Flow

```typescript
// lib/store/auth-store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  permissions: string[];
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshAccessToken: () => Promise<void>;
  hasPermission: (permission: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      permissions: [],
      isAuthenticated: false,
      
      login: async (credentials) => {
        const response = await apiClient.post('/auth/login', credentials);
        set({
          user: response.data.user,
          accessToken: response.data.access_token,
          refreshToken: response.data.refresh_token,
          permissions: response.data.user.permissions || [],
          isAuthenticated: true,
        });
      },
      
      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          permissions: [],
          isAuthenticated: false,
        });
      },
      
      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) throw new Error('No refresh token');
        
        const response = await apiClient.post('/auth/refresh', {
          refresh_token: refreshToken,
        });
        
        set({ accessToken: response.data.access_token });
      },
      
      hasPermission: (permission) => {
        return get().permissions.includes(permission);
      },
    }),
    {
      name: 'ipam-auth-storage',
      partialize: (state) => ({
        user: state.user,
        refreshToken: state.refreshToken,
        permissions: state.permissions,
      }),
    }
  )
);
```

### Permission-Aware Components

```typescript
// components/core/permission-guard.tsx
import { useAuthStore } from '@/lib/store/auth-store';
import { ReactNode } from 'react';

interface PermissionGuardProps {
  permission: string;
  children: ReactNode;
  fallback?: ReactNode;
}

export function PermissionGuard({ 
  permission, 
  children, 
  fallback = null 
}: PermissionGuardProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission(permission));
  
  if (!hasPermission) return <>{fallback}</>;
  
  return <>{children}</>;
}

// Usage
<PermissionGuard permission="ipam:allocate">
  <Button onClick={createRegion}>Create Region</Button>
</PermissionGuard>
```

### Middleware Protection

```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('ipam-auth-token')?.value;
  
  // Protected routes
  if (request.nextUrl.pathname.startsWith('/dashboard')) {
    if (!token) {
      return NextResponse.redirect(new URL('/login', request.url));
    }
  }
  
  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*'],
};
```

---

## 📡 API Integration Layer

### Axios Client with Interceptors

```typescript
// lib/api/client.ts
import axios from 'axios';
import { useAuthStore } from '@/lib/store/auth-store';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    // Token expired, try refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        await useAuthStore.getState().refreshAccessToken();
        const newToken = useAuthStore.getState().accessToken;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export default apiClient;
```

### API Service Modules

```typescript
// lib/api/regions.ts
import apiClient from './client';
import type { Region, RegionCreateRequest, PaginatedResponse } from '@/lib/types/ipam';

export const regionsApi = {
  list: async (params?: {
    country?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<Region>> => {
    const response = await apiClient.get('/ipam/regions', { params });
    return response.data;
  },
  
  get: async (regionId: string): Promise<Region> => {
    const response = await apiClient.get(`/ipam/regions/${regionId}`);
    return response.data;
  },
  
  create: async (data: RegionCreateRequest): Promise<Region> => {
    const response = await apiClient.post('/ipam/regions', null, {
      params: data,
    });
    return response.data;
  },
  
  update: async (regionId: string, updates: Partial<Region>): Promise<Region> => {
    const response = await apiClient.patch(`/ipam/regions/${regionId}`, null, {
      params: updates,
    });
    return response.data;
  },
  
  retire: async (regionId: string, reason: string, cascade: boolean): Promise<void> => {
    await apiClient.delete(`/ipam/regions/${regionId}`, {
      params: { reason, cascade },
    });
  },
  
  getUtilization: async (regionId: string) => {
    const response = await apiClient.get(`/ipam/regions/${regionId}/utilization`);
    return response.data;
  },
  
  addComment: async (regionId: string, comment: string) => {
    const response = await apiClient.post(`/ipam/regions/${regionId}/comments`, null, {
      params: { comment_text: comment },
    });
    return response.data;
  },
};
```

### React Query Hooks

```typescript
// lib/hooks/use-regions.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { regionsApi } from '@/lib/api/regions';
import { toast } from 'sonner';

export function useRegions(filters?: {
  country?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ['regions', filters],
    queryFn: () => regionsApi.list(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

export function useRegion(regionId: string) {
  return useQuery({
    queryKey: ['regions', regionId],
    queryFn: () => regionsApi.get(regionId),
    enabled: !!regionId,
  });
}

export function useCreateRegion() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: regionsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['regions'] });
      toast.success('Region created successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.message || 'Failed to create region');
    },
  });
}

export function useUpdateRegion() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ regionId, updates }: { regionId: string; updates: any }) =>
      regionsApi.update(regionId, updates),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['regions', variables.regionId] });
      queryClient.invalidateQueries({ queryKey: ['regions'] });
      toast.success('Region updated successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.message || 'Failed to update region');
    },
  });
}

export function useRetireRegion() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ regionId, reason, cascade }: { 
      regionId: string; 
      reason: string; 
      cascade: boolean;
    }) => regionsApi.retire(regionId, reason, cascade),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['regions'] });
      toast.success('Region retired successfully');
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.message || 'Failed to retire region');
    },
  });
}
```

---

## 🎯 Key UI Components

### 1. IP Hierarchy Tree Visualization

```typescript
// components/ipam/ip-hierarchy-tree.tsx
'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ChevronRight, Globe, MapPin, Server, Monitor } from 'lucide-react';

interface HierarchyNode {
  level: 'continent' | 'country' | 'region' | 'host';
  name: string;
  cidr?: string;
  status?: string;
  utilization?: number;
  children?: HierarchyNode[];
}

export function IPHierarchyTree({ data }: { data: HierarchyNode }) {
  const getIcon = (level: string) => {
    switch (level) {
      case 'continent': return <Globe className="h-4 w-4" />;
      case 'country': return <MapPin className="h-4 w-4" />;
      case 'region': return <Server className="h-4 w-4" />;
      case 'host': return <Monitor className="h-4 w-4" />;
    }
  };
  
  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'Active': return 'bg-green-500';
      case 'Reserved': return 'bg-yellow-500';
      case 'Retired': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };
  
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2">
        {getIcon(data.level)}
        <span className="font-medium">{data.name}</span>
        {data.cidr && (
          <Badge variant="outline" className="font-mono text-xs">
            {data.cidr}
          </Badge>
        )}
        {data.status && (
          <Badge className={getStatusColor(data.status)}>
            {data.status}
          </Badge>
        )}
        {data.utilization !== undefined && (
          <Badge variant="secondary">
            {data.utilization.toFixed(1)}% utilized
          </Badge>
        )}
      </div>
      
      {data.children && data.children.length > 0 && (
        <div className="ml-6 mt-2 space-y-2 border-l-2 border-border pl-4">
          {data.children.map((child, idx) => (
            <IPHierarchyTree key={idx} data={child} />
          ))}
        </div>
      )}
    </Card>
  );
}
```

### 2. Utilization Chart

```typescript
// components/ipam/utilization-chart.tsx
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  Cell 
} from 'recharts';

interface UtilizationData {
  name: string;
  allocated: number;
  available: number;
  utilization: number;
}

export function UtilizationChart({ data }: { data: UtilizationData[] }) {
  const getColor = (utilization: number) => {
    if (utilization < 50) return 'hsl(var(--utilization-low))';
    if (utilization < 80) return 'hsl(var(--utilization-medium))';
    return 'hsl(var(--utilization-high))';
  };
  
  return (
    <Card>
      <CardHeader>
        <CardTitle>Capacity Utilization</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="allocated" stackId="a" fill="hsl(var(--primary))">
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getColor(entry.utilization)} />
              ))}
            </Bar>
            <Bar dataKey="available" stackId="a" fill="hsl(var(--muted))" />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
```

### 3. Region Create Form

```typescript
// components/forms/region-create-form.tsx
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { useCreateRegion } from '@/lib/hooks/use-regions';
import { useCountries } from '@/lib/hooks/use-countries';

const regionSchema = z.object({
  country: z.string().min(2, 'Country is required'),
  region_name: z.string().min(2, 'Region name must be at least 2 characters'),
  description: z.string().optional(),
  owner: z.string().optional(),
  tags: z.record(z.string()).optional(),
});

type RegionFormData = z.infer<typeof regionSchema>;

export function RegionCreateForm({ onSuccess }: { onSuccess?: () => void }) {
  const { data: countries } = useCountries();
  const createRegion = useCreateRegion();
  
  const form = useForm<RegionFormData>({
    resolver: zodResolver(regionSchema),
    defaultValues: {
      country: '',
      region_name: '',
      description: '',
      owner: '',
    },
  });
  
  const onSubmit = async (data: RegionFormData) => {
    await createRegion.mutateAsync(data);
    form.reset();
    onSuccess?.();
  };
  
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="country"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Country</FormLabel>
              <Select onValueChange={field.onChange} defaultValue={field.value}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a country" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {countries?.map((country) => (
                    <SelectItem key={country.country} value={country.country}>
                      {country.country} ({country.continent})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <FormField
          control={form.control}
          name="region_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Region Name</FormLabel>
              <FormControl>
                <Input placeholder="e.g., Mumbai DC1" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Description (Optional)</FormLabel>
              <FormControl>
                <Textarea placeholder="Region description..." {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <FormField
          control={form.control}
          name="owner"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Owner (Optional)</FormLabel>
              <FormControl>
                <Input placeholder="Team or owner identifier" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        
        <Button type="submit" disabled={createRegion.isPending}>
          {createRegion.isPending ? 'Creating...' : 'Create Region'}
        </Button>
      </form>
    </Form>
  );
}
```

---

## 📊 Advanced Features

### 1. Advanced Search with Filters

```typescript
// app/(dashboard)/search/page.tsx
'use client';

import { useState } from 'react';
import { useSearch } from '@/lib/hooks/use-search';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { DataTable } from '@/components/ui/data-table';

export default function SearchPage() {
  const [filters, setFilters] = useState({
    ip_address: '',
    hostname: '',
    country: '',
    status: '',
    page: 1,
    page_size: 50,
  });
  
  const { data, isLoading } = useSearch(filters);
  
  return (
    <div className="space-y-6">
      <Card className="p-6">
        <h2 className="text-2xl font-bold mb-4">Advanced Search</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Input
            placeholder="IP Address"
            value={filters.ip_address}
            onChange={(e) => setFilters({ ...filters, ip_address: e.target.value })}
          />
          <Input
            placeholder="Hostname"
            value={filters.hostname}
            onChange={(e) => setFilters({ ...filters, hostname: e.target.value })}
          />
          <Select
            value={filters.status}
            onValueChange={(value) => setFilters({ ...filters, status: value })}
          >
            <option value="">All Statuses</option>
            <option value="Active">Active</option>
            <option value="Reserved">Reserved</option>
            <option value="Retired">Retired</option>
          </Select>
        </div>
        
        <Button className="mt-4" onClick={() => setFilters({ ...filters, page: 1 })}>
          Search
        </Button>
      </Card>
      
      <DataTable
        data={data?.results || []}
        columns={searchColumns}
        pagination={data?.pagination}
        isLoading={isLoading}
      />
    </div>
  );
}
```

### 2. Batch Host Creation

```typescript
// components/forms/batch-host-form.tsx
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { useBatchCreateHosts } from '@/lib/hooks/use-hosts';
import { Progress } from '@/components/ui/progress';

const batchSchema = z.object({
  region_id: z.string(),
  count: z.number().min(1).max(100),
  hostname_prefix: z.string().min(1),
  device_type: z.string().optional(),
  owner: z.string().optional(),
});

export function BatchHostForm() {
  const batchCreate = useBatchCreateHosts();
  const form = useForm({ resolver: zodResolver(batchSchema) });
  
  const onSubmit = async (data: any) => {
    await batchCreate.mutateAsync(data);
  };
  
  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      {/* Form fields */}
      
      {batchCreate.isPending && (
        <div className="space-y-2">
          <Progress value={50} />
          <p className="text-sm text-muted-foreground">Creating hosts...</p>
        </div>
      )}
      
      <Button type="submit" disabled={batchCreate.isPending}>
        Create {form.watch('count')} Hosts
      </Button>
    </form>
  );
}
```

### 3. Audit Log Viewer

```typescript
// components/ipam/audit-log-viewer.tsx
'use client';

import { useAuditHistory } from '@/lib/hooks/use-audit';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { formatDistanceToNow } from 'date-fns';

export function AuditLogViewer({ resourceId }: { resourceId: string }) {
  const { data: auditLog } = useAuditHistory({ resource_id: resourceId });
  
  return (
    <Card className="p-4">
      <h3 className="text-lg font-semibold mb-4">Audit History</h3>
      
      <div className="space-y-3">
        {auditLog?.entries.map((entry) => (
          <div key={entry.audit_id} className="border-l-2 border-primary pl-4">
            <div className="flex items-center gap-2">
              <Badge>{entry.action_type}</Badge>
              <span className="text-sm text-muted-foreground">
                {formatDistanceToNow(new Date(entry.timestamp), { addSuffix: true })}
              </span>
            </div>
            
            <p className="text-sm mt-1">
              by <span className="font-medium">{entry.user_id}</span>
            </p>
            
            {entry.changes.length > 0 && (
              <div className="mt-2 text-xs space-y-1">
                {entry.changes.map((change, idx) => (
                  <div key={idx} className="flex gap-2">
                    <span className="font-medium">{change.field}:</span>
                    <span className="text-red-500">{change.old_value}</span>
                    <span>→</span>
                    <span className="text-green-500">{change.new_value}</span>
                  </div>
                ))}
              </div>
            )}
            
            {entry.reason && (
              <p className="text-sm text-muted-foreground mt-1">
                Reason: {entry.reason}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
```

### 4. Real-time Capacity Monitoring

```typescript
// components/ipam/capacity-gauge.tsx
'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { AlertTriangle } from 'lucide-react';

interface CapacityGaugeProps {
  total: number;
  allocated: number;
  resourceName: string;
}

export function CapacityGauge({ total, allocated, resourceName }: CapacityGaugeProps) {
  const utilization = (allocated / total) * 100;
  const available = total - allocated;
  
  const getStatusColor = () => {
    if (utilization < 50) return 'text-green-600';
    if (utilization < 80) return 'text-yellow-600';
    return 'text-red-600';
  };
  
  const getProgressColor = () => {
    if (utilization < 50) return 'bg-green-500';
    if (utilization < 80) return 'bg-yellow-500';
    return 'bg-red-500';
  };
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>{resourceName}</span>
          {utilization > 80 && (
            <AlertTriangle className="h-5 w-5 text-red-500" />
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Allocated</span>
            <span className={getStatusColor()}>
              {allocated} / {total} ({utilization.toFixed(1)}%)
            </span>
          </div>
          <Progress value={utilization} className={getProgressColor()} />
        </div>
        
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-muted-foreground">Available</p>
            <p className="text-2xl font-bold">{available}</p>
          </div>
          <div>
            <p className="text-muted-foreground">Allocated</p>
            <p className="text-2xl font-bold">{allocated}</p>
          </div>
        </div>
        
        {utilization > 80 && (
          <div className="bg-red-50 dark:bg-red-950 p-3 rounded-md">
            <p className="text-sm text-red-800 dark:text-red-200">
              ⚠️ High utilization detected. Consider expanding capacity.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
```

---

## 🚀 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] **Project Setup**
  - Initialize Next.js project with Bun
  - Configure Tailwind CSS + shadcn/ui
  - Set up TypeScript strict mode
  - Configure ESLint + Prettier
  
- [ ] **Core Infrastructure**
  - Implement auth store with Zustand
  - Create API client with interceptors
  - Set up React Query provider
  - Implement theme system with CSS variables
  
- [ ] **Authentication**
  - Login/signup pages
  - JWT token management
  - Refresh token flow
  - Protected route middleware

### Phase 2: Core Features (Week 3-4)
- [ ] **Country Management**
  - List countries with continent grouping
  - Country details page
  - Utilization visualization
  
- [ ] **Region Management**
  - List regions with filters
  - Create region form
  - Region details page
  - Update region metadata
  - Retire region with cascade
  
- [ ] **Host Management**
  - List hosts with advanced filters
  - Create host form
  - Batch host creation
  - Host details page
  - Release hosts

### Phase 3: Advanced Features (Week 5-6)
- [ ] **Search & Analytics**
  - Advanced search with multi-criteria
  - IP hierarchy visualization
  - Utilization charts and dashboards
  - Capacity monitoring
  
- [ ] **Audit & History**
  - Audit log viewer
  - Change tracking visualization
  - Export audit reports
  
- [ ] **User Experience**
  - Toast notifications
  - Loading states
  - Error boundaries
  - Optimistic updates

### Phase 4: Polish & Optimization (Week 7-8)
- [ ] **Performance**
  - Code splitting
  - Image optimization
  - Bundle size optimization
  - Lazy loading
  
- [ ] **Testing**
  - Unit tests for utilities
  - Integration tests for API hooks
  - E2E tests for critical flows
  
- [ ] **Documentation**
  - Component storybook
  - API integration guide
  - Deployment guide

---

## 🛠️ Development Commands

### Using Bun

```bash
# Install dependencies
bun install

# Development server
bun run dev

# Build for production
bun run build

# Start production server
bun run start

# Run tests
bun test

# Lint
bun run lint

# Format
bun run format

# Type check
bun run type-check
```

### Environment Variables

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=IPAM
NEXT_PUBLIC_APP_VERSION=1.0.0
```

---

## 📦 Package.json

```json
{
  "name": "ipam-frontend",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "format": "prettier --write .",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "next": "^14.2.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.28.0",
    "@tanstack/react-table": "^8.13.0",
    "axios": "^1.6.7",
    "zustand": "^4.5.2",
    "next-themes": "^0.3.0",
    "react-hook-form": "^7.51.0",
    "@hookform/resolvers": "^3.3.4",
    "zod": "^3.22.4",
    "recharts": "^2.12.0",
    "framer-motion": "^11.0.0",
    "lucide-react": "^0.356.0",
    "date-fns": "^3.3.0",
    "sonner": "^1.4.0",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.0",
    "tailwind-merge": "^2.2.0"
  },
  "devDependencies": {
    "@types/node": "^20.11.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.56.0",
    "eslint-config-next": "^14.2.0",
    "prettier": "^3.2.0",
    "prettier-plugin-tailwindcss": "^0.5.0"
  }
}
```

---

## 🎨 Tailwind Configuration

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
        // IPAM-specific colors
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

---

## 🔒 Security Best Practices

### 1. Token Storage
- Store access tokens in memory (Zustand state)
- Store refresh tokens in httpOnly cookies (if backend supports)
- Never store tokens in localStorage for production

### 2. API Security
- Always use HTTPS in production
- Implement CSRF protection
- Validate all user inputs
- Sanitize data before rendering

### 3. Permission Checks
- Verify permissions on both frontend and backend
- Hide UI elements based on permissions
- Show appropriate error messages

### 4. Rate Limiting Awareness
- Display rate limit status to users
- Implement retry logic with exponential backoff
- Show user-friendly messages when limits exceeded

---

## 📈 Performance Optimization

### 1. Code Splitting
```typescript
// Dynamic imports for heavy components
const UtilizationChart = dynamic(() => import('@/components/ipam/utilization-chart'), {
  loading: () => <Skeleton className="h-[300px]" />,
  ssr: false,
});
```

### 2. Image Optimization
```typescript
import Image from 'next/image';

<Image
  src="/logo.png"
  alt="IPAM Logo"
  width={200}
  height={50}
  priority
/>
```

### 3. React Query Optimization
```typescript
// Prefetch data on hover
const queryClient = useQueryClient();

<Link
  href={`/regions/${regionId}`}
  onMouseEnter={() => {
    queryClient.prefetchQuery({
      queryKey: ['regions', regionId],
      queryFn: () => regionsApi.get(regionId),
    });
  }}
>
  View Region
</Link>
```

### 4. Memoization
```typescript
import { useMemo } from 'react';

const sortedRegions = useMemo(() => {
  return regions.sort((a, b) => a.utilization - b.utilization);
}, [regions]);
```

---

## 🧪 Testing Strategy

### Unit Tests (Vitest)
```typescript
// lib/utils/format.test.ts
import { describe, it, expect } from 'vitest';
import { formatIP, formatCIDR } from './format';

describe('formatIP', () => {
  it('should format IP address correctly', () => {
    expect(formatIP('10.5.23.45')).toBe('10.5.23.45');
  });
  
  it('should handle invalid IP', () => {
    expect(formatIP('invalid')).toBe('Invalid IP');
  });
});
```

### Integration Tests (React Testing Library)
```typescript
// components/forms/region-create-form.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { RegionCreateForm } from './region-create-form';

describe('RegionCreateForm', () => {
  it('should submit form with valid data', async () => {
    const onSuccess = vi.fn();
    render(<RegionCreateForm onSuccess={onSuccess} />);
    
    fireEvent.change(screen.getByLabelText('Country'), { target: { value: 'India' } });
    fireEvent.change(screen.getByLabelText('Region Name'), { target: { value: 'Mumbai DC1' } });
    fireEvent.click(screen.getByText('Create Region'));
    
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalled();
    });
  });
});
```

### E2E Tests (Playwright)
```typescript
// e2e/region-management.spec.ts
import { test, expect } from '@playwright/test';

test('should create and view region', async ({ page }) => {
  await page.goto('/login');
  await page.fill('[name="username"]', 'testuser');
  await page.fill('[name="password"]', 'password');
  await page.click('button[type="submit"]');
  
  await page.goto('/dashboard/regions/create');
  await page.selectOption('[name="country"]', 'India');
  await page.fill('[name="region_name"]', 'Test Region');
  await page.click('button[type="submit"]');
  
  await expect(page.locator('text=Region created successfully')).toBeVisible();
});
```

---

## 📚 Documentation Structure

```
docs/
├── README.md                     # Overview
├── SETUP.md                      # Setup instructions
├── ARCHITECTURE.md               # Architecture details
├── API_INTEGRATION.md            # API integration guide
├── THEME_SYSTEM.md               # Theme customization
├── COMPONENTS.md                 # Component library
├── DEPLOYMENT.md                 # Deployment guide
└── TROUBLESHOOTING.md            # Common issues
```

---

## 🎯 Success Metrics

### Performance Targets
- **First Contentful Paint (FCP)**: < 1.5s
- **Largest Contentful Paint (LCP)**: < 2.5s
- **Time to Interactive (TTI)**: < 3.5s
- **Cumulative Layout Shift (CLS)**: < 0.1

### User Experience
- **Page Load Time**: < 2s on 3G
- **API Response Time**: < 500ms (p95)
- **Search Results**: < 1s
- **Batch Operations**: Progress feedback every 100ms

### Code Quality
- **Test Coverage**: > 80%
- **TypeScript Strict Mode**: Enabled
- **ESLint Errors**: 0
- **Bundle Size**: < 500KB (gzipped)

---

## 🚢 Deployment

### Vercel (Recommended)
```bash
# Install Vercel CLI
bun add -g vercel

# Deploy
vercel --prod
```

### Docker
```dockerfile
# Dockerfile
FROM oven/bun:1 as builder

WORKDIR /app
COPY package.json bun.lockb ./
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

FROM oven/bun:1-slim
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./

EXPOSE 3000
CMD ["bun", "run", "start"]
```

### Environment-Specific Configs
```typescript
// next.config.js
const nextConfig = {
  env: {
    API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  images: {
    domains: ['your-cdn.com'],
  },
  output: 'standalone', // For Docker
};
```

---

## 🎉 Conclusion

This architecture provides a **production-ready, scalable, and maintainable** frontend for the IPAM system. Key highlights:

✅ **Modern Stack**: Next.js 14 + Bun + TypeScript  
✅ **Type Safety**: End-to-end type safety with Zod validation  
✅ **Performance**: Optimized with code splitting, caching, and lazy loading  
✅ **UX**: Emotion-inspired themes, smooth animations, real-time feedback  
✅ **Security**: JWT auth, permission guards, input sanitization  
✅ **Scalability**: Modular architecture, reusable components  
✅ **Developer Experience**: Hot reload, strict TypeScript, comprehensive testing  

**Next Steps**: Follow the implementation roadmap to build the application incrementally, starting with Phase 1 (Foundation) and progressing through each phase systematically.
