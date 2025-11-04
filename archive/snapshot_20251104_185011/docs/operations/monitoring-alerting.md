# Monitoring and Alerting Configuration

## Overview

This document provides comprehensive guidance for setting up monitoring and alerting for the Family Management System. The monitoring stack includes application metrics, health checks, log aggregation, and alerting mechanisms.

## Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                             │
├─────────────────────────────────────────────────────────────────┤
│  Application Metrics (Prometheus)                               │
│  ├── FastAPI Metrics (Request/Response)                        │
│  ├── Family System Metrics (Operations)                        │
│  ├── Database Metrics (MongoDB/Redis)                          │
│  └── System Metrics (CPU/Memory/Disk)                          │
├─────────────────────────────────────────────────────────────────┤
│  Log Aggregation (ELK Stack / Loki)                            │
│  ├── Application Logs (Structured JSON)                        │
│  ├── Access Logs (Nginx)                                       │
│  ├── Database Logs (MongoDB/Redis)                             │
│  └── System Logs (Syslog)                                      │
├─────────────────────────────────────────────────────────────────┤
│  Alerting (AlertManager / PagerDuty)                           │
│  ├── Critical System Alerts                                    │
│  ├── Performance Degradation Alerts                            │
│  ├── Security Incident Alerts                                  │
│  └── Business Logic Alerts                                     │
├─────────────────────────────────────────────────────────────────┤
│  Dashboards (Grafana)                                          │
│  ├── System Overview Dashboard                                 │
│  ├── Family Management Dashboard                               │
│  ├── Security Dashboard                                        │
│  └── Performance Dashboard                                     │
└─────────────────────────────────────────────────────────────────┘
```

## Application Metrics

### Prometheus Configuration

Create `/etc/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "family_management_rules.yml"
  - "system_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Family Management API
  - job_name: 'sbd-api'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 15s
    metrics_path: /metrics
    scrape_timeout: 10s

  # MongoDB Exporter
  - job_name: 'mongodb'
    static_configs:
      - targets: ['localhost:9216']
    scrape_interval: 30s

  # Redis Exporter
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
    scrape_interval: 30s

  # Node Exporter (System Metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 15s

  # Nginx Exporter
  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']
    scrape_interval: 30s
```

### Custom Application Metrics

The application exposes custom metrics for family management operations:

```python
# Family Management Metrics
family_operations_total = Counter(
    'family_operations_total',
    'Total family operations',
    ['operation_type', 'status']
)

family_operation_duration = Histogram(
    'family_operation_duration_seconds',
    'Family operation duration',
    ['operation_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

active_families_gauge = Gauge(
    'active_families_total',
    'Total number of active families'
)

family_members_gauge = Gauge(
    'family_members_total',
    'Total number of family members'
)

sbd_account_balance = Gauge(
    'sbd_account_balance',
    'SBD account balance by family',
    ['family_id']
)

token_requests_gauge = Gauge(
    'token_requests_pending',
    'Number of pending token requests'
)

invitation_success_rate = Gauge(
    'invitation_success_rate',
    'Family invitation success rate'
)

# Security Metrics
authentication_attempts = Counter(
    'authentication_attempts_total',
    'Authentication attempts',
    ['method', 'status']
)

rate_limit_violations = Counter(
    'rate_limit_violations_total',
    'Rate limit violations',
    ['endpoint', 'user_type']
)

security_events = Counter(
    'security_events_total',
    'Security events',
    ['event_type', 'severity']
)

# Performance Metrics
database_query_duration = Histogram(
    'database_query_duration_seconds',
    'Database query duration',
    ['collection', 'operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

cache_hit_rate = Gauge(
    'cache_hit_rate',
    'Cache hit rate by cache type',
    ['cache_type']
)

concurrent_requests = Gauge(
    'concurrent_requests',
    'Number of concurrent requests'
)
```

### Alerting Rules

Create `/etc/prometheus/family_management_rules.yml`:

```yaml
groups:
  - name: family_management_alerts
    rules:
      # High Error Rate
      - alert: HighErrorRate
        expr: rate(family_operations_total{status="error"}[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in family operations"
          description: "Error rate is {{ $value }} errors per second"

      # Critical Error Rate
      - alert: CriticalErrorRate
        expr: rate(family_operations_total{status="error"}[5m]) > 0.5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Critical error rate in family operations"
          description: "Error rate is {{ $value }} errors per second"

      # Slow Operations
      - alert: SlowFamilyOperations
        expr: histogram_quantile(0.95, rate(family_operation_duration_seconds_bucket[5m])) > 5
        for: 3m
        labels:
          severity: warning
        annotations:
          summary: "Family operations are slow"
          description: "95th percentile latency is {{ $value }} seconds"

      # Database Connection Issues
      - alert: DatabaseConnectionFailure
        expr: up{job="mongodb"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "MongoDB is down"
          description: "MongoDB has been down for more than 1 minute"

      # Redis Connection Issues
      - alert: RedisConnectionFailure
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Redis is down"
          description: "Redis has been down for more than 1 minute"

      # High Rate Limit Violations
      - alert: HighRateLimitViolations
        expr: rate(rate_limit_violations_total[5m]) > 10
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High rate of rate limit violations"
          description: "Rate limit violations: {{ $value }} per second"

      # Security Events
      - alert: SecurityIncident
        expr: rate(security_events_total{severity="high"}[1m]) > 0
        for: 0s
        labels:
          severity: critical
        annotations:
          summary: "Security incident detected"
          description: "High severity security event detected"

      # Low Invitation Success Rate
      - alert: LowInvitationSuccessRate
        expr: invitation_success_rate < 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low invitation success rate"
          description: "Invitation success rate is {{ $value }}"

      # High Memory Usage
      - alert: HighMemoryUsage
        expr: (node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      # High CPU Usage
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"

      # Disk Space Low
      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Low disk space"
          description: "Disk space is {{ $value | humanizePercentage }} full"

      # Application Down
      - alert: ApplicationDown
        expr: up{job="sbd-api"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "SBD API is down"
          description: "SBD API has been down for more than 1 minute"
```

## AlertManager Configuration

Create `/etc/alertmanager/alertmanager.yml`:

```yaml
global:
  smtp_smarthost: 'localhost:587'
  smtp_from: 'alerts@yourdomain.com'
  smtp_auth_username: 'alerts@yourdomain.com'
  smtp_auth_password: 'smtp_password'

route:
  group_by: ['alertname']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 5s
      repeat_interval: 5m
    - match:
        severity: warning
      receiver: 'warning-alerts'
      repeat_interval: 30m

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'http://localhost:5001/'

  - name: 'critical-alerts'
    email_configs:
      - to: 'oncall@yourdomain.com'
        subject: 'CRITICAL: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts-critical'
        title: 'Critical Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    pagerduty_configs:
      - routing_key: 'your-pagerduty-integration-key'
        description: '{{ .GroupLabels.alertname }}'

  - name: 'warning-alerts'
    email_configs:
      - to: 'team@yourdomain.com'
        subject: 'WARNING: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK'
        channel: '#alerts-warning'
        title: 'Warning: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
```

## Grafana Dashboards

### Family Management Dashboard

Create dashboard JSON for Grafana:

```json
{
  "dashboard": {
    "id": null,
    "title": "Family Management System",
    "tags": ["family", "sbd"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Family Operations Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(family_operations_total[5m])",
            "legendFormat": "{{ operation_type }} - {{ status }}"
          }
        ],
        "yAxes": [
          {
            "label": "Operations/sec"
          }
        ]
      },
      {
        "id": 2,
        "title": "Active Families",
        "type": "singlestat",
        "targets": [
          {
            "expr": "active_families_total"
          }
        ]
      },
      {
        "id": 3,
        "title": "Total Family Members",
        "type": "singlestat",
        "targets": [
          {
            "expr": "family_members_total"
          }
        ]
      },
      {
        "id": 4,
        "title": "Operation Latency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(family_operation_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          },
          {
            "expr": "histogram_quantile(0.95, rate(family_operation_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.99, rate(family_operation_duration_seconds_bucket[5m]))",
            "legendFormat": "99th percentile"
          }
        ]
      },
      {
        "id": 5,
        "title": "Token Requests",
        "type": "graph",
        "targets": [
          {
            "expr": "token_requests_pending",
            "legendFormat": "Pending Requests"
          }
        ]
      },
      {
        "id": 6,
        "title": "Invitation Success Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "invitation_success_rate",
            "legendFormat": "Success Rate"
          }
        ]
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
```

### Security Dashboard

```json
{
  "dashboard": {
    "id": null,
    "title": "Security Monitoring",
    "tags": ["security", "auth"],
    "panels": [
      {
        "id": 1,
        "title": "Authentication Attempts",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(authentication_attempts_total[5m])",
            "legendFormat": "{{ method }} - {{ status }}"
          }
        ]
      },
      {
        "id": 2,
        "title": "Rate Limit Violations",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(rate_limit_violations_total[5m])",
            "legendFormat": "{{ endpoint }}"
          }
        ]
      },
      {
        "id": 3,
        "title": "Security Events",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(security_events_total[5m])",
            "legendFormat": "{{ event_type }} - {{ severity }}"
          }
        ]
      },
      {
        "id": 4,
        "title": "Failed Login Attempts by IP",
        "type": "table",
        "targets": [
          {
            "expr": "topk(10, sum by (source_ip) (rate(authentication_attempts_total{status=\"failed\"}[1h])))"
          }
        ]
      }
    ]
  }
}
```

## Log Aggregation

### ELK Stack Configuration

#### Elasticsearch Configuration

Create `/etc/elasticsearch/elasticsearch.yml`:

```yaml
cluster.name: sbd-logs
node.name: sbd-log-node-1
path.data: /var/lib/elasticsearch
path.logs: /var/log/elasticsearch
network.host: localhost
http.port: 9200
discovery.type: single-node

# Security
xpack.security.enabled: true
xpack.security.transport.ssl.enabled: true
```

#### Logstash Configuration

Create `/etc/logstash/conf.d/sbd-logs.conf`:

```ruby
input {
  beats {
    port => 5044
  }
  
  file {
    path => "/var/log/sbd/*.log"
    start_position => "beginning"
    codec => "json"
    type => "sbd-application"
  }
  
  file {
    path => "/var/log/nginx/sbd-api.access.log"
    start_position => "beginning"
    type => "nginx-access"
  }
}

filter {
  if [type] == "sbd-application" {
    # Parse structured JSON logs
    json {
      source => "message"
    }
    
    # Add timestamp
    date {
      match => [ "timestamp", "ISO8601" ]
    }
    
    # Extract user information
    if [user_id] {
      mutate {
        add_field => { "user_context" => "%{user_id}" }
      }
    }
    
    # Categorize log levels
    if [level] == "ERROR" {
      mutate {
        add_tag => [ "error" ]
      }
    }
  }
  
  if [type] == "nginx-access" {
    grok {
      match => { 
        "message" => "%{NGINXACCESS}"
      }
    }
    
    # Parse response time
    mutate {
      convert => { "response_time" => "float" }
    }
    
    # GeoIP lookup
    geoip {
      source => "clientip"
    }
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "sbd-logs-%{+YYYY.MM.dd}"
  }
  
  # Send errors to separate index
  if "error" in [tags] {
    elasticsearch {
      hosts => ["localhost:9200"]
      index => "sbd-errors-%{+YYYY.MM.dd}"
    }
  }
}
```

#### Kibana Configuration

Create `/etc/kibana/kibana.yml`:

```yaml
server.port: 5601
server.host: "localhost"
elasticsearch.hosts: ["http://localhost:9200"]
kibana.index: ".kibana"

# Security
elasticsearch.username: "kibana_system"
elasticsearch.password: "kibana_password"
```

### Loki Configuration (Alternative)

Create `/etc/loki/loki.yml`:

```yaml
auth_enabled: false

server:
  http_listen_port: 3100

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 1h
  max_chunk_age: 1h
  chunk_target_size: 1048576
  chunk_retain_period: 30s

schema_config:
  configs:
    - from: 2020-10-24
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    shared_store: filesystem
  filesystem:
    directory: /loki/chunks

limits_config:
  enforce_metric_name: false
  reject_old_samples: true
  reject_old_samples_max_age: 168h

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: false
  retention_period: 0s
```

## Health Checks

### Application Health Endpoints

The application provides multiple health check endpoints:

```python
# Basic health check
@router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

# Detailed health check
@router.get("/health/detailed")
async def detailed_health_check():
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "components": {}
    }
    
    # Check database connectivity
    try:
        db = await get_database()
        await db.admin.command('ping')
        health_status["components"]["database"] = "healthy"
    except Exception as e:
        health_status["components"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check Redis connectivity
    try:
        redis_client = await get_redis_client()
        await redis_client.ping()
        health_status["components"]["redis"] = "healthy"
    except Exception as e:
        health_status["components"]["redis"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Check family system health
    try:
        family_health = await family_monitor.check_family_system_health()
        health_status["components"]["family_system"] = family_health
    except Exception as e:
        health_status["components"]["family_system"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    
    return health_status

# Readiness check
@router.get("/health/ready")
async def readiness_check():
    # Check if application is ready to serve requests
    checks = [
        check_database_ready(),
        check_redis_ready(),
        check_migrations_complete()
    ]
    
    results = await asyncio.gather(*checks, return_exceptions=True)
    
    if all(result is True for result in results):
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")

# Liveness check
@router.get("/health/live")
async def liveness_check():
    # Simple check to verify application is alive
    return {"status": "alive", "pid": os.getpid()}
```

### External Health Monitoring

Create monitoring script `/opt/monitoring/health_monitor.py`:

```python
#!/usr/bin/env python3
"""External health monitoring script."""

import asyncio
import aiohttp
import logging
import json
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HealthMonitor:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "checks": {}
        }
        
        # Basic health check
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    results["checks"]["basic"] = "healthy"
                else:
                    results["checks"]["basic"] = f"unhealthy: HTTP {response.status}"
                    results["overall_status"] = "unhealthy"
        except Exception as e:
            results["checks"]["basic"] = f"unhealthy: {str(e)}"
            results["overall_status"] = "unhealthy"
        
        # Detailed health check
        try:
            async with self.session.get(f"{self.base_url}/health/detailed") as response:
                if response.status == 200:
                    data = await response.json()
                    results["checks"]["detailed"] = data
                    if data.get("status") != "healthy":
                        results["overall_status"] = "unhealthy"
                else:
                    results["checks"]["detailed"] = f"unhealthy: HTTP {response.status}"
                    results["overall_status"] = "unhealthy"
        except Exception as e:
            results["checks"]["detailed"] = f"unhealthy: {str(e)}"
            results["overall_status"] = "unhealthy"
        
        # API functionality check
        try:
            # Test a simple API endpoint
            headers = {"Authorization": "Bearer test_token"}
            async with self.session.get(f"{self.base_url}/family/my-families", headers=headers) as response:
                # We expect 401 for invalid token, which means API is working
                if response.status in [200, 401]:
                    results["checks"]["api"] = "healthy"
                else:
                    results["checks"]["api"] = f"unhealthy: HTTP {response.status}"
                    results["overall_status"] = "unhealthy"
        except Exception as e:
            results["checks"]["api"] = f"unhealthy: {str(e)}"
            results["overall_status"] = "unhealthy"
        
        return results
    
    async def send_alert(self, health_results: Dict[str, Any]):
        """Send alert if health check fails."""
        if health_results["overall_status"] != "healthy":
            # Send to monitoring system
            logger.error(f"Health check failed: {json.dumps(health_results, indent=2)}")
            
            # You can integrate with your alerting system here
            # Example: send to Slack, PagerDuty, etc.

async def main():
    async with HealthMonitor("http://localhost:8000") as monitor:
        health_results = await monitor.check_health()
        
        print(json.dumps(health_results, indent=2))
        
        if health_results["overall_status"] != "healthy":
            await monitor.send_alert(health_results)
            exit(1)
        else:
            logger.info("All health checks passed")

if __name__ == "__main__":
    asyncio.run(main())
```

## Monitoring Setup Scripts

### Installation Script

Create `/opt/scripts/setup_monitoring.sh`:

```bash
#!/bin/bash

set -e

echo "Setting up monitoring stack..."

# Install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
sudo mv prometheus-*/prometheus /usr/local/bin/
sudo mv prometheus-*/promtool /usr/local/bin/
sudo mkdir -p /etc/prometheus /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus /var/lib/prometheus

# Install AlertManager
wget https://github.com/prometheus/alertmanager/releases/download/v0.25.0/alertmanager-0.25.0.linux-amd64.tar.gz
tar xvfz alertmanager-*.tar.gz
sudo mv alertmanager-*/alertmanager /usr/local/bin/
sudo mv alertmanager-*/amtool /usr/local/bin/
sudo mkdir -p /etc/alertmanager
sudo chown alertmanager:alertmanager /etc/alertmanager

# Install Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.5.0/node_exporter-1.5.0.linux-amd64.tar.gz
tar xvfz node_exporter-*.tar.gz
sudo mv node_exporter-*/node_exporter /usr/local/bin/

# Install MongoDB Exporter
wget https://github.com/percona/mongodb_exporter/releases/download/v0.37.0/mongodb_exporter-0.37.0.linux-amd64.tar.gz
tar xvfz mongodb_exporter-*.tar.gz
sudo mv mongodb_exporter /usr/local/bin/

# Install Redis Exporter
wget https://github.com/oliver006/redis_exporter/releases/download/v1.45.0/redis_exporter-v1.45.0.linux-amd64.tar.gz
tar xvfz redis_exporter-*.tar.gz
sudo mv redis_exporter /usr/local/bin/

# Create systemd services
sudo tee /etc/systemd/system/prometheus.service > /dev/null <<EOF
[Unit]
Description=Prometheus
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \\
    --config.file /etc/prometheus/prometheus.yml \\
    --storage.tsdb.path /var/lib/prometheus/ \\
    --web.console.templates=/etc/prometheus/consoles \\
    --web.console.libraries=/etc/prometheus/console_libraries \\
    --web.listen-address=0.0.0.0:9090 \\
    --web.enable-lifecycle

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/node_exporter.service > /dev/null <<EOF
[Unit]
Description=Node Exporter
Wants=network-online.target
After=network-online.target

[Service]
User=node_exporter
Group=node_exporter
Type=simple
ExecStart=/usr/local/bin/node_exporter

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable prometheus node_exporter
sudo systemctl start prometheus node_exporter

echo "Monitoring stack setup complete!"
```

### Dashboard Import Script

Create `/opt/scripts/import_dashboards.py`:

```python
#!/usr/bin/env python3
"""Import Grafana dashboards."""

import requests
import json
import os

GRAFANA_URL = "http://localhost:3000"
GRAFANA_API_KEY = os.getenv("GRAFANA_API_KEY")

dashboards = [
    {
        "name": "Family Management System",
        "file": "/opt/dashboards/family_management.json"
    },
    {
        "name": "Security Monitoring",
        "file": "/opt/dashboards/security.json"
    },
    {
        "name": "System Overview",
        "file": "/opt/dashboards/system.json"
    }
]

def import_dashboard(dashboard_file, dashboard_name):
    """Import a dashboard into Grafana."""
    headers = {
        "Authorization": f"Bearer {GRAFANA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    with open(dashboard_file, 'r') as f:
        dashboard_json = json.load(f)
    
    payload = {
        "dashboard": dashboard_json,
        "overwrite": True,
        "message": f"Imported {dashboard_name}"
    }
    
    response = requests.post(
        f"{GRAFANA_URL}/api/dashboards/db",
        headers=headers,
        json=payload
    )
    
    if response.status_code == 200:
        print(f"Successfully imported {dashboard_name}")
    else:
        print(f"Failed to import {dashboard_name}: {response.text}")

def main():
    if not GRAFANA_API_KEY:
        print("Please set GRAFANA_API_KEY environment variable")
        return
    
    for dashboard in dashboards:
        if os.path.exists(dashboard["file"]):
            import_dashboard(dashboard["file"], dashboard["name"])
        else:
            print(f"Dashboard file not found: {dashboard['file']}")

if __name__ == "__main__":
    main()
```

This comprehensive monitoring and alerting configuration provides full observability into the Family Management System, enabling proactive issue detection and resolution.