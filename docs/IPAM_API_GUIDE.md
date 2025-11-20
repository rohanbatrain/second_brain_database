# IPAM API Guide

## Overview

The Hierarchical IP Allocation Management (IPAM) system provides a structured approach to managing private IPv4 address space (10.0.0.0/8) through a four-level hierarchy:

- **Global Root**: 10.0.0.0/8 (entire private address space)
- **Country**: 10.X.0.0/16 (predefined country blocks)
- **Region**: 10.X.Y.0/24 (user-created regional blocks)
- **Host**: 10.X.Y.Z (individual host addresses)

### Key Features

- **Auto-Allocation**: System automatically assigns the next available X.Y or Z values
- **User Isolation**: Each user has a completely isolated namespace
- **Geographic Hierarchy**: Predefined continent-country mappings provide global structure
- **Comprehensive Audit**: All operations are logged with complete audit trails
- **Hard Delete**: Retired allocations are permanently deleted to reclaim address space
- **Concurrency Safe**: Database transactions prevent duplicate IP assignments

### Enhancement Features

This guide covers the core IPAM functionality. For advanced features including:
- **Reservation Management**: Reserve IPs before allocation
- **Shareable Links**: Generate public read-only links
- **User Preferences**: Save filters and customize dashboard
- **Notifications**: Set up alerts and notification rules
- **Capacity Forecasting**: Predictive analytics for capacity planning
- **Webhooks**: Integrate with external systems
- **Bulk Operations**: Efficient multi-resource updates

See the [IPAM Enhancements Complete API Guide](./IPAM_ENHANCEMENTS_COMPLETE_API_GUIDE.md) for detailed documentation.

### Authentication

All IPAM endpoints require JWT authentication. Include your JWT token in the Authorization header:

```
Authorization: Bearer <your-jwt-token>
```

### Permissions

IPAM operations require specific permissions in your JWT token:

- `ipam:read` - View allocations and statistics
- `ipam:allocate` - Create new regions and hosts
- `ipam:update` - Modify existing allocations
- `ipam:release` - Release/retire allocations
- `ipam:admin` - Administrative operations (quota management)

### Rate Limits

- **Region Creation**: 100 requests per hour per user
- **Host Creation**: 1000 requests per hour per user
- **Query Operations**: 500 requests per hour per user

When rate limit is exceeded, you'll receive HTTP 429 with a `retry_after` header.

### Base URL

All endpoints are prefixed with `/api/v1/ipam`


## Table of Contents

1. [Country Management](#country-management)
2. [Region Management](#region-management)
3. [Host Management](#host-management)
4. [IP Interpretation](#ip-interpretation)
5. [Search and Filtering](#search-and-filtering)
6. [Statistics and Analytics](#statistics-and-analytics)
7. [Import/Export](#importexport)
8. [Audit History](#audit-history)
9. [Quota Management](#quota-management)
10. [Error Responses](#error-responses)

---

## Country Management

### List All Countries

Get all predefined countries with their X octet ranges and utilization statistics.

**Endpoint**: `POST /api/v1/ipam/countries`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "continent": "Asia",  // Optional: filter by continent
  "include_utilization": true  // Optional: include utilization stats
}
```

**Response** (200 OK):
```json
{
  "countries": [
    {
      "country": "India",
      "continent": "Asia",
      "x_start": 0,
      "x_end": 29,
      "total_capacity": 7680,  // (30 X values) × 256 regions
      "allocated_regions": 150,
      "utilization_percentage": 1.95,
      "remaining_capacity": 7530
    }
  ],
  "total_count": 15
}
```


### Get Country Details

Get detailed information about a specific country.

**Endpoint**: `GET /api/v1/ipam/countries/{country}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "country": "India",
  "continent": "Asia",
  "x_start": 0,
  "x_end": 29,
  "total_capacity": 7680,
  "allocated_regions": 150,
  "utilization_percentage": 1.95,
  "x_value_breakdown": [
    {
      "x_octet": 0,
      "allocated_y_count": 10,
      "available_y_count": 246,
      "utilization_percentage": 3.91
    }
  ]
}
```

### Get Country Utilization

Get detailed utilization statistics for a country.

**Endpoint**: `GET /api/v1/ipam/countries/{country}/utilization`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "country": "India",
  "total_capacity": 7680,
  "allocated_regions": 150,
  "utilization_percentage": 1.95,
  "warning_threshold": 80,
  "critical_threshold": 100,
  "status": "healthy",  // healthy, warning, critical
  "next_available": "10.0.23.0/24"
}
```

---

## Region Management

### Create Region

Allocate a new /24 region block. The system automatically assigns the next available X.Y combination.

**Endpoint**: `POST /api/v1/ipam/regions`

**Required Permission**: `ipam:allocate`

**Rate Limit**: 100 requests per hour

**Request Body**:
```json
{
  "country": "India",
  "region_name": "Mumbai DC1",
  "description": "Primary datacenter in Mumbai",  // Optional
  "owner": "ops-team",  // Optional
  "tags": {  // Optional
    "environment": "production",
    "tier": "1"
  }
}
```


**Response** (201 Created):
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "x_octet": 5,
  "y_octet": 23,
  "country": "India",
  "continent": "Asia",
  "region_name": "Mumbai DC1",
  "description": "Primary datacenter in Mumbai",
  "status": "Active",
  "owner": "ops-team",
  "tags": {
    "environment": "production",
    "tier": "1"
  },
  "created_at": "2025-11-11T10:30:00Z",
  "created_by": "user123"
}
```

**Error Responses**:

- **400 Bad Request**: Invalid country or validation error
```json
{
  "error": "validation_error",
  "message": "Invalid country name",
  "details": {
    "field": "country",
    "value": "InvalidCountry"
  }
}
```

- **409 Conflict**: Capacity exhausted or duplicate name
```json
{
  "error": "capacity_exhausted",
  "message": "No available addresses in country India",
  "details": {
    "country": "India",
    "total_capacity": 7680,
    "allocated": 7680
  }
}
```

### List Regions

Query regions with filters and pagination.

**Endpoint**: `GET /api/v1/ipam/regions`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `country` (optional): Filter by country
- `status` (optional): Filter by status (Active, Reserved, Retired)
- `owner` (optional): Filter by owner
- `tags` (optional): Filter by tags (JSON format)
- `created_after` (optional): Filter by creation date (ISO 8601)
- `created_before` (optional): Filter by creation date (ISO 8601)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 50, max: 100)


**Response** (200 OK):
```json
{
  "regions": [
    {
      "region_id": "550e8400-e29b-41d4-a716-446655440000",
      "cidr": "10.5.23.0/24",
      "x_octet": 5,
      "y_octet": 23,
      "country": "India",
      "continent": "Asia",
      "region_name": "Mumbai DC1",
      "status": "Active",
      "allocated_hosts": 45,
      "total_capacity": 254,
      "utilization_percentage": 17.72
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 150,
    "total_pages": 3
  }
}
```

### Get Region Details

Get detailed information about a specific region.

**Endpoint**: `GET /api/v1/ipam/regions/{region_id}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "x_octet": 5,
  "y_octet": 23,
  "country": "India",
  "continent": "Asia",
  "region_name": "Mumbai DC1",
  "description": "Primary datacenter in Mumbai",
  "status": "Active",
  "owner": "ops-team",
  "tags": {
    "environment": "production",
    "tier": "1"
  },
  "allocated_hosts": 45,
  "total_capacity": 254,
  "utilization_percentage": 17.72,
  "next_available_host": "10.5.23.46",
  "comments": [
    {
      "text": "Upgraded network infrastructure",
      "author_id": "user123",
      "timestamp": "2025-11-10T15:30:00Z"
    }
  ],
  "created_at": "2025-11-11T10:30:00Z",
  "created_by": "user123",
  "updated_at": "2025-11-11T12:00:00Z",
  "updated_by": "user123"
}
```


### Update Region

Update region metadata and status.

**Endpoint**: `PATCH /api/v1/ipam/regions/{region_id}`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "region_name": "Mumbai DC1 - Updated",  // Optional
  "description": "Updated description",  // Optional
  "owner": "new-team",  // Optional
  "status": "Active",  // Optional: Active, Reserved, Retired
  "tags": {  // Optional
    "environment": "production",
    "tier": "2"
  }
}
```

**Response** (200 OK):
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "region_name": "Mumbai DC1 - Updated",
  "updated_at": "2025-11-11T14:00:00Z",
  "updated_by": "user123"
}
```

### Retire Region

Permanently delete a region and optionally cascade-delete all child hosts.

**Endpoint**: `DELETE /api/v1/ipam/regions/{region_id}`

**Required Permission**: `ipam:release`

**Query Parameters**:
- `cascade` (optional): If true, also retire all child hosts (default: false)
- `reason` (required): Reason for retirement

**Response** (200 OK):
```json
{
  "message": "Region retired successfully",
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "hosts_retired": 45,  // If cascade=true
  "audit_record_id": "audit-123"
}
```

### Add Comment to Region

Add a comment to a region for documentation purposes.

**Endpoint**: `POST /api/v1/ipam/regions/{region_id}/comments`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "text": "Scheduled maintenance on 2025-11-15"
}
```

**Response** (201 Created):
```json
{
  "comment_id": "comment-123",
  "text": "Scheduled maintenance on 2025-11-15",
  "author_id": "user123",
  "timestamp": "2025-11-11T15:00:00Z"
}
```


### Preview Next Available Region

Preview the next region that would be allocated for a country.

**Endpoint**: `GET /api/v1/ipam/regions/preview-next`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `country` (required): Country name

**Response** (200 OK):
```json
{
  "country": "India",
  "next_available": "10.5.24.0/24",
  "x_octet": 5,
  "y_octet": 24,
  "capacity_remaining": 7530,
  "capacity_exhausted": false
}
```

### Get Region Utilization

Get detailed utilization statistics for a region.

**Endpoint**: `GET /api/v1/ipam/regions/{region_id}/utilization`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "allocated_hosts": 45,
  "total_capacity": 254,
  "utilization_percentage": 17.72,
  "warning_threshold": 90,
  "status": "healthy",  // healthy, warning, critical
  "next_available_host": "10.5.23.46"
}
```

---

## Host Management

### Create Host

Allocate a new host address. The system automatically assigns the next available Z octet.

**Endpoint**: `POST /api/v1/ipam/hosts`

**Required Permission**: `ipam:allocate`

**Rate Limit**: 1000 requests per hour

**Request Body**:
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "hostname": "web-server-01",
  "device_type": "VM",  // Optional: VM, Container, Physical
  "os_type": "Ubuntu 22.04",  // Optional
  "application": "nginx",  // Optional
  "cost_center": "engineering",  // Optional
  "owner": "ops-team",  // Optional
  "purpose": "Production web server",  // Optional
  "tags": {  // Optional
    "environment": "production",
    "role": "webserver"
  },
  "notes": "Primary web server"  // Optional
}
```


**Response** (201 Created):
```json
{
  "host_id": "host-123",
  "ip_address": "10.5.23.45",
  "x_octet": 5,
  "y_octet": 23,
  "z_octet": 45,
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "hostname": "web-server-01",
  "device_type": "VM",
  "status": "Active",
  "created_at": "2025-11-11T16:00:00Z",
  "created_by": "user123"
}
```

### Batch Create Hosts

Allocate multiple hosts in a single request.

**Endpoint**: `POST /api/v1/ipam/hosts/batch`

**Required Permission**: `ipam:allocate`

**Rate Limit**: 1000 requests per hour (counts as number of hosts created)

**Request Body**:
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "count": 10,  // Max: 100
  "hostname_prefix": "web-server",  // Will create web-server-01, web-server-02, etc.
  "device_type": "VM",  // Optional
  "tags": {  // Optional
    "environment": "production"
  }
}
```

**Response** (201 Created):
```json
{
  "total_requested": 10,
  "total_created": 10,
  "hosts": [
    {
      "host_id": "host-123",
      "ip_address": "10.5.23.45",
      "hostname": "web-server-01"
    },
    {
      "host_id": "host-124",
      "ip_address": "10.5.23.46",
      "hostname": "web-server-02"
    }
  ],
  "failures": []  // Array of failed allocations with reasons
}
```

### List Hosts

Query hosts with filters and pagination.

**Endpoint**: `GET /api/v1/ipam/hosts`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `region_id` (optional): Filter by region
- `hostname` (optional): Partial hostname match (case-insensitive)
- `status` (optional): Filter by status (Active, Reserved, Released)
- `device_type` (optional): Filter by device type
- `owner` (optional): Filter by owner
- `tags` (optional): Filter by tags (JSON format)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 50, max: 100)


**Response** (200 OK):
```json
{
  "hosts": [
    {
      "host_id": "host-123",
      "ip_address": "10.5.23.45",
      "hostname": "web-server-01",
      "device_type": "VM",
      "status": "Active",
      "region": {
        "region_id": "550e8400-e29b-41d4-a716-446655440000",
        "region_name": "Mumbai DC1",
        "cidr": "10.5.23.0/24"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 450,
    "total_pages": 9
  }
}
```

### Get Host Details

Get detailed information about a specific host.

**Endpoint**: `GET /api/v1/ipam/hosts/{host_id}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "host_id": "host-123",
  "ip_address": "10.5.23.45",
  "x_octet": 5,
  "y_octet": 23,
  "z_octet": 45,
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "hostname": "web-server-01",
  "device_type": "VM",
  "os_type": "Ubuntu 22.04",
  "application": "nginx",
  "cost_center": "engineering",
  "owner": "ops-team",
  "purpose": "Production web server",
  "status": "Active",
  "tags": {
    "environment": "production",
    "role": "webserver"
  },
  "notes": "Primary web server",
  "comments": [],
  "created_at": "2025-11-11T16:00:00Z",
  "created_by": "user123"
}
```

### Lookup Host by IP Address

Retrieve host details by IP address.

**Endpoint**: `GET /api/v1/ipam/hosts/by-ip/{ip_address}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "host_id": "host-123",
  "ip_address": "10.5.23.45",
  "hostname": "web-server-01",
  "status": "Active",
  "region": {
    "region_id": "550e8400-e29b-41d4-a716-446655440000",
    "region_name": "Mumbai DC1",
    "cidr": "10.5.23.0/24",
    "country": "India"
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "not_found",
  "message": "IP address 10.5.23.45 is not allocated"
}
```


### Bulk IP Lookup

Lookup multiple IP addresses in a single request.

**Endpoint**: `POST /api/v1/ipam/hosts/bulk-lookup`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "ip_addresses": [
    "10.5.23.45",
    "10.5.23.46",
    "10.5.23.47"
  ]
}
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "ip_address": "10.5.23.45",
      "found": true,
      "host": {
        "host_id": "host-123",
        "hostname": "web-server-01",
        "status": "Active"
      }
    },
    {
      "ip_address": "10.5.23.46",
      "found": false,
      "message": "IP address not allocated"
    }
  ]
}
```

### Update Host

Update host metadata and status.

**Endpoint**: `PATCH /api/v1/ipam/hosts/{host_id}`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "hostname": "web-server-01-updated",  // Optional
  "device_type": "Container",  // Optional
  "os_type": "Ubuntu 24.04",  // Optional
  "status": "Active",  // Optional: Active, Reserved, Released
  "tags": {  // Optional
    "environment": "staging"
  },
  "notes": "Updated notes"  // Optional
}
```

**Response** (200 OK):
```json
{
  "host_id": "host-123",
  "ip_address": "10.5.23.45",
  "hostname": "web-server-01-updated",
  "updated_at": "2025-11-11T17:00:00Z",
  "updated_by": "user123"
}
```

### Retire Host

Permanently delete a host allocation.

**Endpoint**: `DELETE /api/v1/ipam/hosts/{host_id}`

**Required Permission**: `ipam:release`

**Query Parameters**:
- `reason` (required): Reason for retirement

**Response** (200 OK):
```json
{
  "message": "Host retired successfully",
  "host_id": "host-123",
  "ip_address": "10.5.23.45",
  "audit_record_id": "audit-456"
}
```


### Bulk Release Hosts

Release multiple hosts in a single request.

**Endpoint**: `POST /api/v1/ipam/hosts/bulk-release`

**Required Permission**: `ipam:release`

**Request Body**:
```json
{
  "host_ids": [
    "host-123",
    "host-124",
    "host-125"
  ],
  "reason": "Decommissioning old infrastructure"
}
```

**Response** (200 OK):
```json
{
  "total_requested": 3,
  "total_released": 3,
  "results": [
    {
      "host_id": "host-123",
      "ip_address": "10.5.23.45",
      "success": true
    },
    {
      "host_id": "host-124",
      "ip_address": "10.5.23.46",
      "success": true
    },
    {
      "host_id": "host-125",
      "ip_address": "10.5.23.47",
      "success": false,
      "error": "Host not found"
    }
  ]
}
```

### Add Comment to Host

Add a comment to a host for documentation purposes.

**Endpoint**: `POST /api/v1/ipam/hosts/{host_id}/comments`

**Required Permission**: `ipam:update`

**Request Body**:
```json
{
  "text": "Upgraded to latest OS version"
}
```

**Response** (201 Created):
```json
{
  "comment_id": "comment-456",
  "text": "Upgraded to latest OS version",
  "author_id": "user123",
  "timestamp": "2025-11-11T18:00:00Z"
}
```

### Preview Next Available Host

Preview the next host IP that would be allocated for a region.

**Endpoint**: `GET /api/v1/ipam/hosts/preview-next`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `region_id` (required): Region ID

**Response** (200 OK):
```json
{
  "region_id": "550e8400-e29b-41d4-a716-446655440000",
  "cidr": "10.5.23.0/24",
  "next_available": "10.5.23.46",
  "z_octet": 46,
  "capacity_remaining": 209,
  "capacity_exhausted": false
}
```

---

## IP Interpretation

### Interpret IP Address

Parse an IP address and return its hierarchical context.

**Endpoint**: `POST /api/v1/ipam/interpret`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "ip_address": "10.5.23.45"
}
```


**Response** (200 OK):
```json
{
  "ip_address": "10.5.23.45",
  "hierarchy": {
    "global_root": "10.0.0.0/8",
    "continent": "Asia",
    "country": {
      "name": "India",
      "x_range": "0-29",
      "x_octet": 5
    },
    "region": {
      "region_id": "550e8400-e29b-41d4-a716-446655440000",
      "region_name": "Mumbai DC1",
      "cidr": "10.5.23.0/24",
      "y_octet": 23,
      "status": "Active"
    },
    "host": {
      "host_id": "host-123",
      "hostname": "web-server-01",
      "z_octet": 45,
      "status": "Active",
      "device_type": "VM"
    }
  }
}
```

**Error Response** (404 Not Found):
```json
{
  "error": "not_found",
  "message": "IP address 10.5.23.45 is not allocated or does not belong to you",
  "hierarchy": {
    "global_root": "10.0.0.0/8",
    "continent": "Asia",
    "country": {
      "name": "India",
      "x_range": "0-29",
      "x_octet": 5
    },
    "region": null,
    "host": null
  }
}
```

---

## Search and Filtering

### Search Allocations

Search for regions and hosts using various filters.

**Endpoint**: `GET /api/v1/ipam/search`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `ip_address` (optional): Exact or partial IP match
- `cidr` (optional): CIDR range match
- `hostname` (optional): Partial hostname match (case-insensitive)
- `region_name` (optional): Partial region name match
- `continent` (optional): Filter by continent
- `country` (optional): Filter by country
- `status` (optional): Filter by status
- `owner` (optional): Filter by owner
- `tags` (optional): Filter by tags (JSON format)
- `created_after` (optional): Date range filter (ISO 8601)
- `created_before` (optional): Date range filter (ISO 8601)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 50, max: 100)


**Response** (200 OK):
```json
{
  "results": [
    {
      "type": "region",
      "region_id": "550e8400-e29b-41d4-a716-446655440000",
      "cidr": "10.5.23.0/24",
      "region_name": "Mumbai DC1",
      "country": "India",
      "continent": "Asia",
      "status": "Active"
    },
    {
      "type": "host",
      "host_id": "host-123",
      "ip_address": "10.5.23.45",
      "hostname": "web-server-01",
      "region_name": "Mumbai DC1",
      "country": "India",
      "status": "Active"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 125,
    "total_pages": 3
  }
}
```

---

## Statistics and Analytics

### Get Continent Statistics

Get aggregated statistics for a continent.

**Endpoint**: `GET /api/v1/ipam/statistics/continent/{continent}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "continent": "Asia",
  "total_countries": 7,
  "total_capacity": 30720,  // Total regions across all countries
  "allocated_regions": 450,
  "utilization_percentage": 1.46,
  "countries": [
    {
      "country": "India",
      "allocated_regions": 150,
      "total_capacity": 7680,
      "utilization_percentage": 1.95
    }
  ]
}
```

### Get Top Utilized Resources

Get the most utilized countries and regions.

**Endpoint**: `GET /api/v1/ipam/statistics/top-utilized`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `limit` (optional): Number of results (default: 10, max: 50)
- `resource_type` (optional): Filter by type (country, region)

**Response** (200 OK):
```json
{
  "countries": [
    {
      "country": "India",
      "utilization_percentage": 85.5,
      "allocated_regions": 6566,
      "total_capacity": 7680
    }
  ],
  "regions": [
    {
      "region_id": "550e8400-e29b-41d4-a716-446655440000",
      "region_name": "Mumbai DC1",
      "cidr": "10.5.23.0/24",
      "utilization_percentage": 95.3,
      "allocated_hosts": 242,
      "total_capacity": 254
    }
  ]
}
```


### Get Allocation Velocity

Get allocation trends over time.

**Endpoint**: `GET /api/v1/ipam/statistics/allocation-velocity`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `time_range` (optional): Time range (day, week, month) (default: week)
- `resource_type` (optional): Filter by type (region, host)

**Response** (200 OK):
```json
{
  "time_range": "week",
  "period_start": "2025-11-04T00:00:00Z",
  "period_end": "2025-11-11T00:00:00Z",
  "regions": {
    "total_allocated": 25,
    "allocations_per_day": 3.57,
    "daily_breakdown": [
      {
        "date": "2025-11-04",
        "count": 5
      },
      {
        "date": "2025-11-05",
        "count": 3
      }
    ]
  },
  "hosts": {
    "total_allocated": 150,
    "allocations_per_day": 21.43
  }
}
```

---

## Import/Export

### Create Export Job

Create an asynchronous export job for allocations.

**Endpoint**: `POST /api/v1/ipam/export`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "format": "csv",  // csv or json
  "resource_type": "all",  // all, regions, hosts
  "include_hierarchy": true,  // Include parent/child relationships
  "filters": {  // Optional filters
    "country": "India",
    "status": "Active"
  }
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "export-job-123",
  "status": "pending",
  "created_at": "2025-11-11T19:00:00Z",
  "estimated_completion": "2025-11-11T19:05:00Z"
}
```

### Get Export Job Status

Check the status of an export job.

**Endpoint**: `GET /api/v1/ipam/export/{job_id}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "job_id": "export-job-123",
  "status": "completed",  // pending, processing, completed, failed
  "created_at": "2025-11-11T19:00:00Z",
  "completed_at": "2025-11-11T19:03:00Z",
  "download_url": "/api/v1/ipam/export/export-job-123/download",
  "expires_at": "2025-11-12T19:03:00Z"
}
```


### Download Export

Download the completed export file.

**Endpoint**: `GET /api/v1/ipam/export/{job_id}/download`

**Required Permission**: `ipam:read`

**Response** (200 OK):
- Content-Type: `text/csv` or `application/json`
- Content-Disposition: `attachment; filename="ipam-export-{job_id}.csv"`

### Import Allocations

Import allocations from CSV or JSON file.

**Endpoint**: `POST /api/v1/ipam/import`

**Required Permission**: `ipam:allocate`

**Request Body** (multipart/form-data):
- `file`: CSV or JSON file
- `mode`: `auto` (system assigns X/Y/Z) or `manual` (use values from file)
- `force`: `true` to skip existing allocations, `false` to reject on conflicts

**Response** (200 OK):
```json
{
  "total_rows": 100,
  "imported": 95,
  "skipped": 3,
  "failed": 2,
  "errors": [
    {
      "line": 45,
      "error": "Duplicate IP address",
      "details": {
        "ip_address": "10.5.23.45"
      }
    }
  ]
}
```

### Preview Import

Validate import file without committing changes.

**Endpoint**: `POST /api/v1/ipam/import/preview`

**Required Permission**: `ipam:read`

**Request Body** (multipart/form-data):
- `file`: CSV or JSON file

**Response** (200 OK):
```json
{
  "total_rows": 100,
  "valid": 95,
  "invalid": 5,
  "validation_errors": [
    {
      "line": 12,
      "error": "Invalid country name",
      "field": "country",
      "value": "InvalidCountry"
    }
  ],
  "conflicts": [
    {
      "line": 45,
      "error": "IP address already allocated",
      "ip_address": "10.5.23.45"
    }
  ]
}
```

---

## Audit History

### Query Audit History

Get audit history with filters.

**Endpoint**: `GET /api/v1/ipam/audit/history`

**Required Permission**: `ipam:read`

**Query Parameters**:
- `user_id` (optional): Filter by user
- `action_type` (optional): Filter by action (create, update, release, retire)
- `resource_type` (optional): Filter by type (region, host)
- `date_from` (optional): Start date (ISO 8601)
- `date_to` (optional): End date (ISO 8601)
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 50, max: 100)


**Response** (200 OK):
```json
{
  "audit_records": [
    {
      "audit_id": "audit-123",
      "user_id": "user123",
      "action_type": "create",
      "resource_type": "host",
      "resource_id": "host-123",
      "ip_address": "10.5.23.45",
      "snapshot": {
        "hostname": "web-server-01",
        "status": "Active"
      },
      "timestamp": "2025-11-11T16:00:00Z"
    },
    {
      "audit_id": "audit-456",
      "user_id": "user123",
      "action_type": "update",
      "resource_type": "host",
      "resource_id": "host-123",
      "changes": [
        {
          "field": "hostname",
          "old_value": "web-server-01",
          "new_value": "web-server-01-updated"
        }
      ],
      "timestamp": "2025-11-11T17:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 1250,
    "total_pages": 25
  }
}
```

### Get IP-Specific History

Get audit history for a specific IP address.

**Endpoint**: `GET /api/v1/ipam/audit/history/{ip_address}`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "ip_address": "10.5.23.45",
  "history": [
    {
      "audit_id": "audit-123",
      "action_type": "create",
      "hostname": "web-server-01",
      "user_id": "user123",
      "timestamp": "2025-11-11T16:00:00Z"
    },
    {
      "audit_id": "audit-456",
      "action_type": "update",
      "changes": [
        {
          "field": "hostname",
          "old_value": "web-server-01",
          "new_value": "web-server-01-updated"
        }
      ],
      "user_id": "user123",
      "timestamp": "2025-11-11T17:00:00Z"
    },
    {
      "audit_id": "audit-789",
      "action_type": "retire",
      "reason": "Decommissioned",
      "user_id": "user123",
      "timestamp": "2025-11-11T18:00:00Z"
    }
  ]
}
```


### Export Audit History

Export audit history in CSV or JSON format.

**Endpoint**: `POST /api/v1/ipam/audit/export`

**Required Permission**: `ipam:read`

**Request Body**:
```json
{
  "format": "csv",  // csv or json
  "filters": {  // Optional filters
    "date_from": "2025-11-01T00:00:00Z",
    "date_to": "2025-11-11T23:59:59Z",
    "action_type": "create"
  }
}
```

**Response** (202 Accepted):
```json
{
  "job_id": "audit-export-123",
  "status": "pending",
  "created_at": "2025-11-11T20:00:00Z"
}
```

---

## Quota Management

### Get User Quota

Get quota information for the current user.

**Endpoint**: `GET /api/v1/ipam/quotas/me`

**Required Permission**: `ipam:read`

**Response** (200 OK):
```json
{
  "user_id": "user123",
  "region_quota": 1000,
  "region_count": 150,
  "region_utilization_percentage": 15.0,
  "host_quota": 10000,
  "host_count": 450,
  "host_utilization_percentage": 4.5,
  "warnings": []  // Array of warnings if approaching quota
}
```

**Response with Warning** (200 OK):
```json
{
  "user_id": "user123",
  "region_quota": 1000,
  "region_count": 850,
  "region_utilization_percentage": 85.0,
  "host_quota": 10000,
  "host_count": 450,
  "host_utilization_percentage": 4.5,
  "warnings": [
    {
      "type": "region_quota_warning",
      "message": "You have used 85% of your region quota",
      "remaining": 150
    }
  ]
}
```

### Get User Quota (Admin)

Get quota information for any user (admin only).

**Endpoint**: `GET /api/v1/ipam/admin/quotas/{user_id}`

**Required Permission**: `ipam:admin`

**Response** (200 OK):
```json
{
  "user_id": "user456",
  "region_quota": 1000,
  "region_count": 150,
  "host_quota": 10000,
  "host_count": 450,
  "last_updated": "2025-11-11T10:00:00Z"
}
```


### Update User Quota (Admin)

Update quota limits for a user (admin only).

**Endpoint**: `PATCH /api/v1/ipam/admin/quotas/{user_id}`

**Required Permission**: `ipam:admin`

**Request Body**:
```json
{
  "region_quota": 2000,  // Optional
  "host_quota": 20000  // Optional
}
```

**Response** (200 OK):
```json
{
  "user_id": "user456",
  "region_quota": 2000,
  "host_quota": 20000,
  "updated_at": "2025-11-11T21:00:00Z",
  "updated_by": "admin123"
}
```

### List All User Quotas (Admin)

List quota information for all users (admin only).

**Endpoint**: `GET /api/v1/ipam/admin/quotas`

**Required Permission**: `ipam:admin`

**Query Parameters**:
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Results per page (default: 50, max: 100)

**Response** (200 OK):
```json
{
  "quotas": [
    {
      "user_id": "user123",
      "region_quota": 1000,
      "region_count": 150,
      "host_quota": 10000,
      "host_count": 450
    },
    {
      "user_id": "user456",
      "region_quota": 2000,
      "region_count": 500,
      "host_quota": 20000,
      "host_count": 1200
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total_count": 125,
    "total_pages": 3
  }
}
```

---

## Error Responses

### Common Error Codes

All error responses follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    // Additional context-specific details
  }
}
```

### HTTP Status Codes

- **200 OK**: Request succeeded
- **201 Created**: Resource created successfully
- **202 Accepted**: Request accepted for async processing
- **400 Bad Request**: Invalid request parameters or validation error
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Insufficient permissions
- **404 Not Found**: Resource not found or not accessible
- **409 Conflict**: Resource conflict (duplicate, capacity exhausted)
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error


### Error Examples

#### Validation Error (400)
```json
{
  "error": "validation_error",
  "message": "Invalid country name",
  "details": {
    "field": "country",
    "value": "InvalidCountry",
    "valid_values": ["India", "United States", "..."]
  }
}
```

#### Authentication Error (401)
```json
{
  "error": "authentication_required",
  "message": "Valid JWT token required"
}
```

#### Permission Error (403)
```json
{
  "error": "insufficient_permissions",
  "required_permission": "ipam:allocate",
  "message": "This operation requires ipam:allocate permission"
}
```

#### Not Found Error (404)
```json
{
  "error": "not_found",
  "message": "Region not found or not accessible",
  "details": {
    "region_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

#### Capacity Exhausted (409)
```json
{
  "error": "capacity_exhausted",
  "message": "No available addresses in country India",
  "details": {
    "country": "India",
    "total_capacity": 7680,
    "allocated": 7680,
    "suggestion": "Consider using a different country or contact administrator for quota increase"
  }
}
```

#### Duplicate Name (409)
```json
{
  "error": "duplicate_name",
  "message": "Region name already exists in this country",
  "details": {
    "country": "India",
    "region_name": "Mumbai DC1",
    "existing_region_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

#### Rate Limit Exceeded (429)
```json
{
  "error": "rate_limit_exceeded",
  "limit": 100,
  "period": 3600,
  "retry_after": 1800,
  "message": "Rate limit exceeded. Try again in 30 minutes."
}
```

#### Quota Exceeded (429)
```json
{
  "error": "quota_exceeded",
  "message": "Region quota exceeded",
  "details": {
    "quota": 1000,
    "current_count": 1000,
    "resource_type": "region"
  }
}
```

---

## Auto-Allocation Behavior

### Region Auto-Allocation

When creating a region, the system automatically:

1. Validates the country exists in the predefined mapping
2. Retrieves the country's X octet range (e.g., India: 0-29)
3. For each X value in the range (starting from x_start):
   - Queries allocated Y octets for this user and X value
   - If fewer than 256 Y octets are allocated:
     - Finds the lowest available Y value (0-255)
     - Allocates X.Y combination
     - Returns immediately
4. If all X values are exhausted, returns capacity_exhausted error

**Example**: For India (X range 0-29):
- First allocation: 10.0.0.0/24
- Second allocation: 10.0.1.0/24
- After 256 allocations in X=0: 10.1.0.0/24
- After 7680 allocations: capacity_exhausted

### Host Auto-Allocation

When creating a host, the system automatically:

1. Validates the region exists and belongs to the user
2. Queries allocated Z octets for this user and region
3. Finds the lowest available Z value (1-254, excluding 0 and 255)
4. Allocates the Z octet
5. If all 254 Z values are allocated, returns capacity_exhausted error

**Example**: For region 10.5.23.0/24:
- First allocation: 10.5.23.1
- Second allocation: 10.5.23.2
- After 254 allocations: capacity_exhausted

---

## Best Practices

### 1. Use Descriptive Names

Use clear, descriptive names for regions and hosts:
- ✅ Good: "Mumbai-DC1-Production", "web-server-prod-01"
- ❌ Bad: "region1", "server1"

### 2. Leverage Tags

Use tags to organize allocations:
```json
{
  "environment": "production",
  "team": "infrastructure",
  "cost_center": "engineering",
  "project": "web-platform"
}
```

### 3. Add Comments

Document important changes and maintenance windows:
```json
{
  "text": "Scheduled maintenance: 2025-11-15 02:00-04:00 UTC"
}
```

### 4. Monitor Quotas

Regularly check quota utilization to avoid hitting limits:
```bash
GET /api/v1/ipam/quotas/me
```

### 5. Use Batch Operations

For bulk operations, use batch endpoints to improve performance:
```bash
POST /api/v1/ipam/hosts/batch
POST /api/v1/ipam/hosts/bulk-release
```

### 6. Export Regularly

Export allocations regularly for backup and reporting:
```bash
POST /api/v1/ipam/export
```

### 7. Review Audit History

Regularly review audit history for compliance and troubleshooting:
```bash
GET /api/v1/ipam/audit/history
```

---

## Support and Resources

- **API Documentation**: `/docs` (Swagger UI)
- **OpenAPI Schema**: `/openapi.json`
- **GitHub Repository**: https://github.com/rohanbatrain/second_brain_database
- **Issue Tracker**: https://github.com/rohanbatrain/second_brain_database/issues

For questions or support, please open an issue on GitHub.
