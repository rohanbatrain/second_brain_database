# Production Deployment Guide

This guide covers deploying the Second Brain Database to production environments.

## Pre-Deployment Checklist

### Security

- [ ] All secrets stored in environment variables
- [ ] JWT secret is cryptographically secure (256+ bits)
- [ ] Database has authentication enabled
- [ ] HTTPS/TLS certificates configured
- [ ] CORS origins restricted to production domains
- [ ] Rate limiting configured
- [ ] Input validation on all endpoints

### Performance

- [ ] Database indexes created
- [ ] Redis caching configured
- [ ] Static assets optimized and compressed
- [ ] CDN configured for media files
- [ ] Load balancer set up (if needed)

### Monitoring

- [ ] Error tracking (Sentry, etc.)
- [ ] Performance monitoring (New Relic, etc.)
- [ ] Log aggregation (CloudWatch, etc.)
- [ ] Uptime monitoring
- [ ] Alert notifications configured

## Deployment Options

### Option 1: Docker Deployment

Recommended for containerized environments.

#### Build Images

```bash
# Backend
docker build -t sbd-backend:latest .

# Frontend (example for digital-shop)
cd submodules/sbd-nextjs-digital-shop
docker build -t sbd-nextjs-digital-shop:latest .
```

#### Docker Compose

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:7
    environment:
      MONGO_INITDB_ROOT_USERNAME: ${MONGO_USER}
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_PASSWORD}
    volumes:
      - mongodb_data:/data/db
    restart: always

  redis:
    image: redis:7
    restart: always

  backend:
    image: sbd-backend:latest
    environment:
      MONGODB_URL: mongodb://mongodb:27017/sbd
      REDIS_URL: redis://redis:6379
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      - mongodb
      - redis
    ports:
      - "8000:8000"
    restart: always

  digital-shop:
    image: sbd-nextjs-digital-shop:latest
    environment:
      NEXT_PUBLIC_API_URL: https://api.yourdomain.com
    ports:
      - "3000:3000"
    restart: always

volumes:
  mongodb_data:
```

#### Deploy

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Option 2: Platform as a Service (Vercel/Railway)

#### Vercel (Frontend)

1. **Connect Repository**:
   - Go to [vercel.com](https://vercel.com)
   - Import Git repository
   - Select submodule directory

2. **Configure Build**:
   ```json
   {
     "buildCommand": "npm run build",
     "outputDirectory": ".next",
     "installCommand": "npm install"
   }
   ```

3. **Set Environment Variables**:
   ```
   NEXT_PUBLIC_API_URL=https://api.yourdomain.com
   ```

4. **Deploy**: Vercel auto-deploys on push to main

#### Railway (Backend)

1. **Create New Project**:
   - Connect GitHub repo
   - Select Python runtime

2. **Add MongoDB & Redis**:
   - Add MongoDB plugin
   - Add Redis plugin
   - Railway auto-configures URLs

3. **Set Environment Variables**:
   ```
   JWT_SECRET=your-secret-key
   CORS_ORIGINS=["https://shop.yourdomain.com"]
   ```

4. **Deploy**: Railway auto-deploys on push

### Option 3: VPS (DigitalOcean, AWS EC2, etc.)

#### Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.11 python3-pip nginx redis-server

# Install MongoDB
wget -qO - https://www.mongodb.org/static/pgp/server-7.0.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org

# Install Node.js
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

#### Deploy Backend

```bash
# Clone repository
git clone https://github.com/yourusername/second_brain_database.git
cd second_brain_database

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.production.example .env
nano .env  # Edit with production values

# Run with systemd
sudo cp deployment/sbd-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sbd-backend
sudo systemctl start sbd-backend
```

**systemd service file** (`deployment/sbd-backend.service`):

```ini
[Unit]
Description=Second Brain Database Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/second_brain_database
Environment="PATH=/var/www/second_brain_database/venv/bin"
ExecStart=/var/www/second_brain_database/venv/bin/uvicorn src.second_brain_database.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Deploy Frontend

```bash
cd submodules/sbd-nextjs-digital-shop

# Install dependencies
npm install

# Build for production
npm run build

# Serve with PM2
npm install -g pm2
pm2 start npm --name "sbd-nextjs-digital-shop" -- start
pm2 save
pm2 startup
```

#### Nginx Configuration

```nginx
# Backend API
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Digital Shop Frontend
server {
    listen 80;
    server_name shop.yourdomain.com;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable HTTPS with Let's Encrypt:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d api.yourdomain.com -d shop.yourdomain.com
```

## Environment Variables

### Backend (.env)

```env
# Production values
MONGODB_URL=mongodb://user:pass@mongodb:27017/sbd?authSource=admin
REDIS_URL=redis://redis:6379/0

JWT_SECRET=<256-bit-random-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRATION=3600

API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false

CORS_ORIGINS=["https://shop.yourdomain.com","https://clubs.yourdomain.com"]

# Email (if using)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@yourdomain.com
SMTP_PASSWORD=<app-password>

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
```

### Frontend (Next.js)

```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_SITE_URL=https://shop.yourdomain.com
NODE_ENV=production
```

## Database Management

### Creating Indexes

```javascript
// MongoDB indexes for performance
db.users.createIndex({ email: 1 }, { unique: true });
db.items.createIndex({ category: 1, price: 1 });
db.items.createIndex({ name: "text", description: "text" });
db.purchases.createIndex({ userId: 1, purchasedAt: -1 });
```

### Backup Strategy

**Automated Backups**:

```bash
# MongoDB backup script
#!/bin/bash
BACKUP_DIR="/backups/mongodb"
DATE=$(date +%Y%m%d_%H%M%S)

mongodump --uri="mongodb://user:pass@localhost:27017/sbd" --out="$BACKUP_DIR/$DATE"

# Keep last 7 days
find $BACKUP_DIR -type d -mtime +7 -exec rm -rf {} \;
```

**Cron job** (daily at 2 AM):

```cron
0 2 * * * /usr/local/bin/backup-mongodb.sh
```

### Migration Strategy

```bash
# Run migrations before deployment
python scripts/run_migrations.py --env production
```

## Health Checks

### Backend Health Endpoint

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "database": await check_db_connection(),
        "redis": await check_redis_connection()
    }
```

### Monitoring

```bash
# Check backend status
curl https://api.yourdomain.com/health

# Expected response
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

## Rollback Procedure

If deployment fails:

### Docker

```bash
# Rollback to previous version
docker-compose down
docker-compose up -d --scale backend=0
docker tag sbd-backend:previous sbd-backend:latest
docker-compose up -d
```

### Vercel

1. Go to **Deployments**
2. Find previous working deployment
3. Click **Promote to Production**

### VPS

```bash
# Rollback git
git reset --hard <previous-commit>

# Restart services
sudo systemctl restart sbd-backend
pm2 restart all
```

## Performance Optimization

### Backend

- Use **Gunicorn** with multiple workers: `--workers 4`
- Enable **Redis caching** for frequent queries
- Add **database connection pooling**

### Frontend

- Enable **static optimization**: `output: 'standalone'` in next.config.js
- Use **Image Optimization**: Next.js Image component
- Enable **compression**: gzip/brotli in Nginx

### Database

- Create proper **indexes**
- Use **query projection** (select only needed fields)
- Implement **pagination** for large datasets

## Monitoring and Alerts

### Set Up Sentry

```python
import sentry_sdk

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment="production",
    traces_sample_rate=1.0,
)
```

### CloudWatch Logs (AWS)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
```

### Uptime Monitoring

Use services like:
- **UptimeRobot** - Free tier available
- **Pingdom** - Comprehensive monitoring
- **StatusCake** - Multiple check locations

## Security Best Practices

- **Never commit secrets** to version control
- Use **environment variables** for all sensitive data
- Enable **database authentication**
- Implement **rate limiting** on APIs
- Keep dependencies **up to date**
- Use **HTTPS everywhere**
- Implement **CSP headers**
- Regular **security audits**

## Post-Deployment

- [ ] Verify all services are running
- [ ] Check logs for errors
- [ ] Test critical user flows
- [ ] Monitor performance metrics
- [ ] Update documentation
- [ ] Notify team of deployment

---

**Last Updated**: November 2024  
**Support**: devops@secondbraindatabase.com
