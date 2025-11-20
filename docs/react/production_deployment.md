# Production Deployment & Best Practices

Complete guide for deploying your React frontend with RAG and WebRTC features to production.

## Table of Contents
1. [Environment Configuration](#environment-configuration)
2. [Build Optimization](#build-optimization)
3. [Docker Deployment](#docker-deployment)
4. [CI/CD Pipeline](#cicd-pipeline)
5. [Security Best Practices](#security-best-practices)
6. [Monitoring & Analytics](#monitoring--analytics)
7. [Performance Optimization](#performance-optimization)

## Environment Configuration

### Environment Variables

```bash
# .env.production
REACT_APP_API_URL=https://api.yourproduction.com/api
REACT_APP_WS_URL=wss://api.yourproduction.com
REACT_APP_SENTRY_DSN=https://your-sentry-dsn
REACT_APP_ANALYTICS_ID=your-analytics-id
REACT_APP_ENABLE_DEBUGGING=false
```

```bash
# .env.development
REACT_APP_API_URL=http://localhost:8000/api
REACT_APP_WS_URL=ws://localhost:8000
REACT_APP_ENABLE_DEBUGGING=true
```

```bash
# .env.staging
REACT_APP_API_URL=https://api-staging.yourproduction.com/api
REACT_APP_WS_URL=wss://api-staging.yourproduction.com
REACT_APP_SENTRY_DSN=https://your-staging-sentry-dsn
REACT_APP_ANALYTICS_ID=your-staging-analytics-id
REACT_APP_ENABLE_DEBUGGING=true
```

### Configuration Service

```typescript
// src/config/environment.ts
export const config = {
  apiUrl: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
  wsUrl: process.env.REACT_APP_WS_URL || 'ws://localhost:8000',
  sentryDsn: process.env.REACT_APP_SENTRY_DSN,
  analyticsId: process.env.REACT_APP_ANALYTICS_ID,
  enableDebugging: process.env.REACT_APP_ENABLE_DEBUGGING === 'true',
  isDevelopment: process.env.NODE_ENV === 'development',
  isProduction: process.env.NODE_ENV === 'production',
  isStaging: process.env.REACT_APP_ENV === 'staging',
} as const;

// Validate required environment variables
const requiredEnvVars = ['REACT_APP_API_URL', 'REACT_APP_WS_URL'];

export const validateEnvironment = () => {
  const missing = requiredEnvVars.filter((key) => !process.env[key]);
  
  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(', ')}`
    );
  }
};
```

## Build Optimization

### Package.json Scripts

```json
{
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "build:analyze": "npm run build && source-map-explorer 'build/static/js/*.js'",
    "build:staging": "env-cmd -f .env.staging react-scripts build",
    "build:production": "env-cmd -f .env.production react-scripts build",
    "test": "react-scripts test",
    "test:coverage": "react-scripts test --coverage --watchAll=false",
    "lint": "eslint src --ext .ts,.tsx",
    "lint:fix": "eslint src --ext .ts,.tsx --fix",
    "format": "prettier --write 'src/**/*.{ts,tsx,css,json}'",
    "type-check": "tsc --noEmit"
  },
  "devDependencies": {
    "env-cmd": "^10.1.0",
    "source-map-explorer": "^2.5.3",
    "@typescript-eslint/eslint-plugin": "^6.0.0",
    "@typescript-eslint/parser": "^6.0.0",
    "eslint": "^8.50.0",
    "prettier": "^3.0.3"
  }
}
```

### Webpack Configuration

```javascript
// config-overrides.js (using react-app-rewired)
const webpack = require('webpack');
const { override, addWebpackPlugin, adjustStyleLoaders } = require('customize-cra');
const CompressionPlugin = require('compression-webpack-plugin');
const TerserPlugin = require('terser-webpack-plugin');

module.exports = override(
  // Enable compression
  addWebpackPlugin(
    new CompressionPlugin({
      filename: '[path][base].gz',
      algorithm: 'gzip',
      test: /\.(js|css|html|svg)$/,
      threshold: 8192,
      minRatio: 0.8,
    })
  ),

  // Optimize bundle size
  (config) => {
    if (config.mode === 'production') {
      config.optimization = {
        ...config.optimization,
        splitChunks: {
          chunks: 'all',
          cacheGroups: {
            vendor: {
              test: /[\\/]node_modules[\\/]/,
              name: 'vendors',
              priority: 10,
            },
            common: {
              minChunks: 2,
              priority: 5,
              reuseExistingChunk: true,
            },
          },
        },
        minimizer: [
          new TerserPlugin({
            terserOptions: {
              parse: {
                ecma: 8,
              },
              compress: {
                ecma: 5,
                warnings: false,
                comparisons: false,
                inline: 2,
                drop_console: true, // Remove console.log in production
              },
              mangle: {
                safari10: true,
              },
              output: {
                ecma: 5,
                comments: false,
                ascii_only: true,
              },
            },
          }),
        ],
      };
    }
    return config;
  }
);
```

### TypeScript Configuration

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "module": "esnext",
    "moduleResolution": "node",
    "resolveJsonModule": true,
    "allowJs": true,
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "allowSyntheticDefaultImports": true,
    "isolatedModules": true,
    "noEmit": true,
    "baseUrl": "src",
    "paths": {
      "@components/*": ["components/*"],
      "@services/*": ["services/*"],
      "@stores/*": ["stores/*"],
      "@hooks/*": ["hooks/*"],
      "@types/*": ["types/*"],
      "@utils/*": ["utils/*"]
    }
  },
  "include": ["src"],
  "exclude": ["node_modules", "build", "dist"]
}
```

## Docker Deployment

### Multi-Stage Dockerfile

```dockerfile
# Dockerfile
# Stage 1: Build
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install dependencies
RUN npm ci --only=production

# Copy source code
COPY src ./src
COPY public ./public

# Build arguments
ARG REACT_APP_API_URL
ARG REACT_APP_WS_URL
ARG REACT_APP_SENTRY_DSN
ARG REACT_APP_ANALYTICS_ID

# Build application
RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Copy custom nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built files
COPY --from=builder /app/build /usr/share/nginx/html

# Add healthcheck
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:80/health || exit 1

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

### Nginx Configuration

```nginx
# nginx.conf
worker_processes auto;
error_log /var/log/nginx/error.log warn;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';

    access_log /var/log/nginx/access.log main;

    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    client_max_body_size 50M;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript 
               application/x-javascript application/xml+rss 
               application/javascript application/json;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    server {
        listen 80;
        server_name _;
        root /usr/share/nginx/html;
        index index.html;

        # Health check endpoint
        location /health {
            access_log off;
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }

        # API proxy (optional - if you want to proxy API requests)
        location /api {
            proxy_pass https://api.yourproduction.com;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_cache_bypass $http_upgrade;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # WebSocket proxy
        location /webrtc/ws {
            proxy_pass https://api.yourproduction.com;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 86400;
        }

        # Static files with caching
        location /static {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }

        # React app - SPA routing
        location / {
            try_files $uri $uri/ /index.html;
            expires -1;
            add_header Cache-Control "no-store, no-cache, must-revalidate, proxy-revalidate";
        }

        # Deny access to hidden files
        location ~ /\. {
            deny all;
            access_log off;
            log_not_found off;
        }
    }
}
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build:
      context: .
      dockerfile: Dockerfile
      args:
        REACT_APP_API_URL: ${REACT_APP_API_URL}
        REACT_APP_WS_URL: ${REACT_APP_WS_URL}
        REACT_APP_SENTRY_DSN: ${REACT_APP_SENTRY_DSN}
        REACT_APP_ANALYTICS_ID: ${REACT_APP_ANALYTICS_ID}
    ports:
      - "80:80"
    restart: unless-stopped
    environment:
      - NODE_ENV=production
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

networks:
  app-network:
    driver: bridge
```

## CI/CD Pipeline

### GitHub Actions

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main

env:
  NODE_VERSION: '18'
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Type check
        run: npm run type-check
      
      - name: Lint
        run: npm run lint
      
      - name: Run tests
        run: npm run test:coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Build application
        env:
          REACT_APP_API_URL: ${{ secrets.REACT_APP_API_URL }}
          REACT_APP_WS_URL: ${{ secrets.REACT_APP_WS_URL }}
          REACT_APP_SENTRY_DSN: ${{ secrets.REACT_APP_SENTRY_DSN }}
          REACT_APP_ANALYTICS_ID: ${{ secrets.REACT_APP_ANALYTICS_ID }}
        run: npm run build:production
      
      - name: Upload build artifacts
        uses: actions/upload-artifact@v3
        with:
          name: build
          path: build/
          retention-days: 7

  docker:
    needs: build
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    permissions:
      contents: read
      packages: write
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha
      
      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          build-args: |
            REACT_APP_API_URL=${{ secrets.REACT_APP_API_URL }}
            REACT_APP_WS_URL=${{ secrets.REACT_APP_WS_URL }}
            REACT_APP_SENTRY_DSN=${{ secrets.REACT_APP_SENTRY_DSN }}
            REACT_APP_ANALYTICS_ID=${{ secrets.REACT_APP_ANALYTICS_ID }}

  deploy:
    needs: docker
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    
    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.DEPLOY_HOST }}
          username: ${{ secrets.DEPLOY_USER }}
          key: ${{ secrets.DEPLOY_KEY }}
          script: |
            cd /opt/second-brain-frontend
            docker-compose pull
            docker-compose up -d
            docker-compose exec frontend nginx -s reload
```

## Security Best Practices

### Content Security Policy

```typescript
// src/utils/security.ts
export const generateCSP = () => {
  const cspDirectives = {
    'default-src': ["'self'"],
    'script-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
    'font-src': ["'self'", "https://fonts.gstatic.com"],
    'img-src': ["'self'", "data:", "https:"],
    'media-src': ["'self'", "blob:"],
    'connect-src': [
      "'self'",
      process.env.REACT_APP_API_URL || '',
      process.env.REACT_APP_WS_URL || '',
    ],
    'frame-ancestors': ["'none'"],
    'base-uri': ["'self'"],
    'form-action': ["'self'"],
  };

  return Object.entries(cspDirectives)
    .map(([key, values]) => `${key} ${values.join(' ')}`)
    .join('; ');
};
```

### Secure Token Storage

```typescript
// src/utils/tokenStorage.ts
import CryptoJS from 'crypto-js';

const ENCRYPTION_KEY = process.env.REACT_APP_ENCRYPTION_KEY || 'default-key';

export const secureStorage = {
  setItem: (key: string, value: string): void => {
    const encrypted = CryptoJS.AES.encrypt(value, ENCRYPTION_KEY).toString();
    sessionStorage.setItem(key, encrypted);
  },

  getItem: (key: string): string | null => {
    const encrypted = sessionStorage.getItem(key);
    if (!encrypted) return null;

    try {
      const decrypted = CryptoJS.AES.decrypt(encrypted, ENCRYPTION_KEY);
      return decrypted.toString(CryptoJS.enc.Utf8);
    } catch {
      return null;
    }
  },

  removeItem: (key: string): void => {
    sessionStorage.removeItem(key);
  },

  clear: (): void => {
    sessionStorage.clear();
  },
};
```

### Input Sanitization

```typescript
// src/utils/sanitize.ts
import DOMPurify from 'dompurify';

export const sanitizeHTML = (dirty: string): string => {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
    ALLOWED_ATTR: ['href', 'target'],
  });
};

export const sanitizeInput = (input: string): string => {
  return input
    .trim()
    .replace(/[<>]/g, '') // Remove < and >
    .substring(0, 1000); // Limit length
};
```

## Monitoring & Analytics

### Sentry Integration

```typescript
// src/utils/monitoring.ts
import * as Sentry from '@sentry/react';
import { BrowserTracing } from '@sentry/tracing';
import { config } from '../config/environment';

export const initMonitoring = () => {
  if (config.sentryDsn && config.isProduction) {
    Sentry.init({
      dsn: config.sentryDsn,
      integrations: [new BrowserTracing()],
      tracesSampleRate: 0.1,
      environment: config.isProduction ? 'production' : 'development',
      beforeSend(event, hint) {
        // Filter sensitive data
        if (event.request?.headers) {
          delete event.request.headers['Authorization'];
        }
        return event;
      },
    });
  }
};

export const logError = (error: Error, context?: Record<string, any>) => {
  if (config.enableDebugging) {
    console.error('Error:', error, context);
  }
  
  Sentry.captureException(error, {
    extra: context,
  });
};
```

### Performance Monitoring

```typescript
// src/utils/performance.ts
export const measurePerformance = (name: string, fn: () => void) => {
  const start = performance.now();
  fn();
  const end = performance.now();
  const duration = end - start;

  if (duration > 100) {
    console.warn(`Slow operation: ${name} took ${duration.toFixed(2)}ms`);
  }

  // Send to analytics
  if (window.gtag) {
    window.gtag('event', 'timing_complete', {
      name,
      value: Math.round(duration),
      event_category: 'Performance',
    });
  }
};
```

This completes the production deployment and best practices guide!
