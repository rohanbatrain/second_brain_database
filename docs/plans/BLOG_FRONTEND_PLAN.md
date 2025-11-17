# 🎨 Multi-Tenant Blog Frontend Implementation Plan

This document outlines the frontend implementation plan for the multi-tenant blog system. The frontend handles all UI/UX, theming, branding, and presentation aspects that consume the backend APIs.

## Table of Contents
- [Frontend Architecture](#frontend-architecture)
- [Theming System](#theming-system)
- [Branding & Customization](#branding--customization)
- [UI Components](#ui-components)
- [Frontend API Integration](#frontend-api-integration)
- [Responsive Design](#responsive-design)
- [Performance Optimization](#performance-optimization)
- [Frontend Deployment](#frontend-deployment)

---

## 🏗️ Frontend Architecture

### Technology Stack
- **Framework**: Next.js 14+ with App Router
- **Styling**: Tailwind CSS with custom theme system
- **State Management**: Zustand for global state
- **API Integration**: React Query for data fetching
- **Authentication**: NextAuth.js integration
- **Components**: Radix UI primitives with custom styling

### Multi-Tenant Frontend Structure
```
Multi-Tenant Frontend Architecture
┌─────────────────────────────────────────────────────┐
│                 User Dashboard                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │  Website A  │ │  Website B  │ │  Website C  │  │
│  │   Management│ │   Management│ │   Management│  │
│  └─────────────┘ └─────────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────┐
│            Website-Specific Frontend                │
│  ┌─────────────────────────────────────────────────┐│
│  │         Dynamic Theme Engine                    ││
│  │    ┌──────────────┐ ┌──────────────────────┐   ││
│  │    │    Theme     │ │       Content        │   ││
│  │    │  Renderer    │ │      Renderer        │   ││
│  │    └──────────────┘ └──────────────────────┘   ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

---

## 🎨 Theming System

### Theme Configuration Model
```typescript
interface WebsiteTheme {
  // Brand Colors
  primary: string;
  secondary: string;
  accent: string;
  
  // Neutral Colors
  background: string;
  surface: string;
  text: {
    primary: string;
    secondary: string;
    muted: string;
  };
  
  // Typography
  fonts: {
    heading: string;
    body: string;
    code: string;
  };
  
  // Layout
  layout: 'modern' | 'classic' | 'minimal' | 'magazine';
  headerStyle: 'centered' | 'left' | 'split' | 'minimal';
  
  // Spacing & Sizing
  borderRadius: 'none' | 'small' | 'medium' | 'large';
  spacing: 'tight' | 'normal' | 'relaxed';
  
  // Custom CSS
  customCSS?: string;
}
```

### Dynamic Theme System
```typescript
// Theme Provider Component
export const WebsiteThemeProvider = ({ 
  children, 
  theme, 
  websiteId 
}: {
  children: React.ReactNode;
  theme: WebsiteTheme;
  websiteId: string;
}) => {
  // Generate CSS custom properties from theme
  const cssVariables = generateCSSVariables(theme);
  
  return (
    <div 
      className="website-theme-root" 
      style={cssVariables}
      data-website-id={websiteId}
    >
      {children}
    </div>
  );
};

// Theme Hook
export const useWebsiteTheme = () => {
  const { websiteId } = useParams();
  const { data: theme } = useQuery({
    queryKey: ['website-theme', websiteId],
    queryFn: () => fetchWebsiteTheme(websiteId),
  });
  
  return theme;
};
```

---

## 🎯 Branding & Customization

### Website Branding Models
```typescript
interface WebsiteBranding {
  // Logo & Identity
  logo: {
    url?: string;
    text: string;
    showText: boolean;
    position: 'left' | 'center' | 'right';
  };
  
  // Favicon
  favicon?: string;
  
  // Social Media
  socialImage?: string; // Open Graph image
  
  // Custom Assets
  backgroundImage?: string;
  customIcons: Record<string, string>;
  
  // Brand Guidelines
  brandColors: {
    primary: string;
    secondary: string;
    accent: string;
  };
}
```

### Custom Domain Handling
```typescript
// Domain Resolution Component
export const DomainResolver = ({ children }: { children: React.ReactNode }) => {
  const hostname = useHostname();
  const { data: website } = useQuery({
    queryKey: ['website-by-domain', hostname],
    queryFn: () => resolveWebsiteByDomain(hostname),
    enabled: !!hostname,
  });
  
  if (!website) {
    return <NotFoundPage />;
  }
  
  return (
    <WebsiteProvider websiteId={website.id}>
      {children}
    </WebsiteProvider>
  );
};
```

---

## 🧩 UI Components

### Layout Components
```typescript
// Header Component
export const WebsiteHeader = ({ layout }: { layout: HeaderLayout }) => {
  const { branding, theme } = useWebsiteContext();
  
  switch (layout) {
    case 'centered':
      return <CenteredHeader branding={branding} theme={theme} />;
    case 'left':
      return <LeftAlignedHeader branding={branding} theme={theme} />;
    case 'split':
      return <SplitHeader branding={branding} theme={theme} />;
    default:
      return <MinimalHeader branding={branding} theme={theme} />;
  }
};

// Post Card Component
export const PostCard = ({ 
  post, 
  layout = 'card' 
}: { 
  post: BlogPost; 
  layout?: 'card' | 'list' | 'featured' | 'grid';
}) => {
  const theme = useWebsiteTheme();
  
  return (
    <article className={`post-card post-card--${layout}`}>
      {post.featured_image && (
        <PostImage src={post.featured_image} alt={post.title} />
      )}
      <PostContent post={post} theme={theme} />
    </article>
  );
};
```

### Admin Components
```typescript
// Theme Editor Component
export const ThemeEditor = ({ websiteId }: { websiteId: string }) => {
  const [theme, setTheme] = useState<WebsiteTheme>();
  const updateThemeMutation = useUpdateWebsiteTheme(websiteId);
  
  return (
    <div className="theme-editor">
      <ColorPalette theme={theme} onChange={setTheme} />
      <TypographySettings theme={theme} onChange={setTheme} />
      <LayoutSettings theme={theme} onChange={setTheme} />
      <PreviewPane theme={theme} />
      <SaveButton 
        onSave={() => updateThemeMutation.mutate(theme)}
        loading={updateThemeMutation.isPending}
      />
    </div>
  );
};

// Branding Manager Component
export const BrandingManager = ({ websiteId }: { websiteId: string }) => {
  const [branding, setBranding] = useState<WebsiteBranding>();
  
  return (
    <div className="branding-manager">
      <LogoUpload branding={branding} onChange={setBranding} />
      <FaviconUpload branding={branding} onChange={setBranding} />
      <SocialImageUpload branding={branding} onChange={setBranding} />
      <ColorPaletteManager branding={branding} onChange={setBranding} />
    </div>
  );
};
```

---

## 🔌 Frontend API Integration

### API Client Setup
```typescript
// Website-scoped API client
export class WebsiteBlogAPI {
  constructor(private websiteId: string) {}
  
  // Posts
  async getPosts(params?: PostListParams) {
    return api.get(`/blog/${this.websiteId}/posts`, { params });
  }
  
  async getPost(slug: string) {
    return api.get(`/blog/${this.websiteId}/posts/${slug}`);
  }
  
  // Categories  
  async getCategories() {
    return api.get(`/blog/${this.websiteId}/categories`);
  }
  
  // Comments
  async getComments(postId: string) {
    return api.get(`/blog/${this.websiteId}/posts/${postId}/comments`);
  }
  
  async createComment(postId: string, data: CreateCommentData) {
    return api.post(`/blog/${this.websiteId}/posts/${postId}/comments`, data);
  }
}

// React Query Hooks
export const useBlogAPI = (websiteId: string) => {
  return useMemo(() => new WebsiteBlogAPI(websiteId), [websiteId]);
};

export const useWebsitePosts = (websiteId: string, params?: PostListParams) => {
  const api = useBlogAPI(websiteId);
  return useQuery({
    queryKey: ['posts', websiteId, params],
    queryFn: () => api.getPosts(params),
  });
};
```

### Theme & Branding API
```typescript
// Theme Management
export const useWebsiteTheme = (websiteId: string) => {
  return useQuery({
    queryKey: ['website-theme', websiteId],
    queryFn: () => api.get(`/blog/websites/${websiteId}/theme`),
  });
};

export const useUpdateWebsiteTheme = (websiteId: string) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (theme: WebsiteTheme) => 
      api.put(`/blog/websites/${websiteId}/theme`, theme),
    onSuccess: () => {
      queryClient.invalidateQueries(['website-theme', websiteId]);
    },
  });
};

// Branding Management
export const useWebsiteBranding = (websiteId: string) => {
  return useQuery({
    queryKey: ['website-branding', websiteId],
    queryFn: () => api.get(`/blog/websites/${websiteId}/branding`),
  });
};
```

---

## 📱 Responsive Design

### Responsive Theme System
```typescript
interface ResponsiveTheme extends WebsiteTheme {
  responsive: {
    breakpoints: {
      sm: string; // 640px
      md: string; // 768px
      lg: string; // 1024px
      xl: string; // 1280px
    };
    
    layout: {
      mobile: LayoutConfig;
      tablet: LayoutConfig;
      desktop: LayoutConfig;
    };
    
    typography: {
      mobile: TypographyScale;
      desktop: TypographyScale;
    };
  };
}

// Responsive Layout Component
export const ResponsivePostGrid = ({ posts }: { posts: BlogPost[] }) => {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {posts.map(post => (
        <PostCard key={post.id} post={post} layout="card" />
      ))}
    </div>
  );
};
```

---

## ⚡ Performance Optimization

### Frontend Caching Strategy
```typescript
// Static Generation for Blog Posts
export async function generateStaticParams() {
  const websites = await getStaticWebsites();
  
  return websites.flatMap(website => 
    website.posts.map(post => ({
      websiteId: website.id,
      slug: post.slug,
    }))
  );
}

// Incremental Static Regeneration
export const revalidate = 3600; // Revalidate every hour

// Image Optimization
export const OptimizedImage = ({ src, alt, ...props }: ImageProps) => {
  return (
    <Image
      src={src}
      alt={alt}
      loading="lazy"
      placeholder="blur"
      sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
      {...props}
    />
  );
};
```

### Code Splitting
```typescript
// Dynamic imports for admin components
const ThemeEditor = dynamic(() => import('./ThemeEditor'), {
  loading: () => <ThemeEditorSkeleton />,
  ssr: false,
});

const BrandingManager = dynamic(() => import('./BrandingManager'), {
  loading: () => <BrandingManagerSkeleton />,
  ssr: false,
});
```

---

## 🚀 Frontend Deployment

### Build Configuration
```typescript
// next.config.js
const nextConfig = {
  // Multi-tenant domain handling
  async rewrites() {
    return [
      // Custom domain routing
      {
        source: '/:path*',
        has: [
          {
            type: 'host',
            value: '(?<domain>(?!admin|www|api).+\\..+)',
          },
        ],
        destination: '/sites/:domain/:path*',
      },
    ];
  },
  
  // Image optimization
  images: {
    domains: ['your-cdn-domain.com'],
    formats: ['image/webp', 'image/avif'],
  },
  
  // Environment-specific config
  env: {
    BACKEND_API_URL: process.env.BACKEND_API_URL,
  },
};
```

### Deployment Strategy
```bash
# Multi-environment deployment
# Development
npm run dev

# Production build
npm run build
npm run start

# Static export for CDN
npm run export
```

---

## 📋 Frontend Implementation Roadmap

### Phase 1: Core Frontend (Weeks 1-2)
- [ ] Set up Next.js with multi-tenant routing
- [ ] Create base theme system with CSS variables
- [ ] Implement website resolution and context providers
- [ ] Build basic layout components (Header, Footer, Navigation)

### Phase 2: Content Display (Weeks 3-4)
- [ ] Create post listing and detail components
- [ ] Implement category and tag filtering
- [ ] Build comment system UI
- [ ] Add search functionality frontend

### Phase 3: Theming & Branding (Weeks 5-6)
- [ ] Build theme editor interface
- [ ] Implement branding management (logo, colors, typography)
- [ ] Create responsive design system
- [ ] Add live preview functionality

### Phase 4: Admin Interface (Weeks 7-8)
- [ ] Build content management dashboard
- [ ] Create post editor with rich text support
- [ ] Implement media management
- [ ] Add analytics dashboard

### Phase 5: Optimization & Polish (Weeks 9-10)
- [ ] Implement performance optimizations
- [ ] Add SEO components and meta tags
- [ ] Create custom domain support
- [ ] Add accessibility features

---

This frontend plan complements the backend implementation and handles all UI, theming, and presentation concerns while consuming the multi-tenant blog APIs.