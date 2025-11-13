# 🌐 IPAM Frontend

**Production-Ready IP Address Management System**

A modern, scalable frontend for hierarchical IP allocation management built with Next.js 14, Bun, and TypeScript.

---

## 🎯 Overview

IPAM (IP Address Management) is a comprehensive system for managing the `10.X.Y.Z` private IPv4 address space with a hierarchical structure:

```
Continent → Country → Region (/24) → Host (individual IP)
```

### Key Features

✨ **Hierarchical IP Management** - Visual tree structure for IP allocation  
📊 **Real-time Analytics** - Utilization dashboards and capacity monitoring  
🔍 **Advanced Search** - Multi-criteria search with filters  
⚡ **Batch Operations** - Bulk host creation and management  
📝 **Audit Trail** - Complete history tracking with change visualization  
🎨 **Emotion-Inspired Themes** - Violet, Emerald, Sunset, Amber, Dusk  
🔐 **Role-Based Access** - Permission-aware UI components  
📱 **Responsive Design** - Mobile-first approach  

---

## 🚀 Quick Start

### Prerequisites

- **Bun** >= 1.0.0 ([Install](https://bun.sh))
- **Node.js** >= 18.0.0
- **Backend API** running on `http://localhost:8000`

### Installation

```bash
# Clone and navigate
cd submodules/IPAM

# Follow the quick start guide
cat QUICKSTART.md

# Or run directly
bun create next-app . --typescript --tailwind --app
bun install
bun run dev
```

### Environment Setup

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=IPAM
NEXT_PUBLIC_APP_VERSION=1.0.0
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [**FRONTEND_ARCHITECTURE_PLAN.md**](./FRONTEND_ARCHITECTURE_PLAN.md) | Complete architecture, tech stack, and design patterns |
| [**QUICKSTART.md**](./QUICKSTART.md) | Step-by-step setup guide |
| [**IMPLEMENTATION_CHECKLIST.md**](./IMPLEMENTATION_CHECKLIST.md) | Detailed task breakdown with progress tracking |

---

## 🏗️ Architecture

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | Next.js 14 (App Router) |
| **Runtime** | Bun |
| **Language** | TypeScript (strict mode) |
| **Styling** | Tailwind CSS + shadcn/ui |
| **State** | Zustand |
| **Data Fetching** | TanStack Query |
| **Forms** | React Hook Form + Zod |
| **Charts** | Recharts |
| **Icons** | Lucide React |

### Project Structure

```
submodules/IPAM/
├── app/                    # Next.js App Router
│   ├── (auth)/            # Authentication routes
│   ├── (dashboard)/       # Protected dashboard
│   └── layout.tsx         # Root layout
├── components/
│   ├── ui/                # shadcn/ui components
│   ├── core/              # Layout components
│   ├── ipam/              # IPAM-specific components
│   ├── forms/             # Form components
│   └── theme/             # Theme components
├── lib/
│   ├── api/               # API client & services
│   ├── hooks/             # Custom React hooks
│   ├── store/             # Zustand stores
│   ├── themes/            # Theme definitions
│   ├── utils/             # Utility functions
│   └── types/             # TypeScript types
├── styles/                # Global styles
└── public/                # Static assets
```

---

## 🎨 Theme System

Emotion-inspired themes with semantic color tokens:

- **Violet** 💜 - Calm, creative, focused
- **Emerald** 💚 - Balanced, growth, stability
- **Sunset** 🧡 - Warm, energetic, optimistic
- **Amber** 💛 - Bright, alert, productive
- **Dusk** 🌆 - Deep, contemplative, sophisticated

Each theme includes:
- Light/dark mode variants
- IPAM-specific tokens (region status, utilization levels)
- Consistent shadows, borders, and radii

---

## 🔐 Authentication

- **JWT-based** authentication with access/refresh tokens
- **Permission-aware** UI components
- **Protected routes** via middleware
- **Auto token refresh** on expiration

---

## 📡 API Integration

### Endpoints Covered

| Resource | Endpoints |
|----------|-----------|
| **Countries** | List, Get, Utilization |
| **Regions** | List, Create, Get, Update, Retire, Comments, Utilization |
| **Hosts** | List, Create, Batch Create, Get, Update, Release, Bulk Release, Lookup |
| **Search** | Advanced multi-criteria search |
| **Audit** | History, Changes, Export |
| **Analytics** | Utilization, Capacity, Velocity |

### API Client Features

- Axios-based with interceptors
- Automatic token injection
- Token refresh on 401
- Request/response logging
- Error handling

---

## 🧪 Testing

```bash
# Unit tests
bun test

# E2E tests
bun run test:e2e

# Coverage
bun run test:coverage
```

### Test Coverage Goals

- **Unit Tests**: > 80%
- **Integration Tests**: Critical flows
- **E2E Tests**: User journeys

---

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| **First Contentful Paint** | < 1.5s |
| **Largest Contentful Paint** | < 2.5s |
| **Time to Interactive** | < 3.5s |
| **Cumulative Layout Shift** | < 0.1 |
| **Bundle Size** | < 500KB (gzipped) |

---

## 🚢 Deployment

### Vercel (Recommended)

```bash
vercel --prod
```

### Docker

```bash
docker build -t ipam-frontend .
docker run -p 3000:3000 ipam-frontend
```

### Environment Variables

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_APP_NAME=IPAM
```

---

## 🛠️ Development

### Commands

```bash
bun run dev          # Start dev server
bun run build        # Build for production
bun run start        # Start production server
bun run lint         # Run ESLint
bun run format       # Format with Prettier
bun run type-check   # TypeScript check
```

### Code Quality

- **ESLint** - Code linting
- **Prettier** - Code formatting
- **TypeScript** - Type safety
- **Husky** - Git hooks
- **lint-staged** - Pre-commit checks

---

## 📈 Roadmap

### Phase 1: Foundation (Week 1-2)
- ✅ Project setup
- ✅ Authentication
- ✅ Theme system

### Phase 2: Core Features (Week 3-4)
- 🔄 Country management
- 🔄 Region management
- 🔄 Host management

### Phase 3: Advanced Features (Week 5-6)
- ⏳ Search & analytics
- ⏳ Audit & history
- ⏳ User settings

### Phase 4: Polish (Week 7-8)
- ⏳ Performance optimization
- ⏳ Testing
- ⏳ Documentation

---

## 🤝 Contributing

1. Follow the [Implementation Checklist](./IMPLEMENTATION_CHECKLIST.md)
2. Write tests for new features
3. Follow the code style guide
4. Update documentation
5. Submit pull request

---

## 📝 License

This project is part of the Second Brain Database system.

---

## 🔗 Related Projects

- [Second Brain Database Backend](../../) - FastAPI backend
- [Emotion Tracker](../emotion_tracker/) - Theme inspiration

---

## 📞 Support

For issues, questions, or contributions:
- Check [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
- Review [FRONTEND_ARCHITECTURE_PLAN.md](./FRONTEND_ARCHITECTURE_PLAN.md)
- Open an issue in the main repository

---

**Built with ❤️ using Next.js, Bun, and TypeScript**
