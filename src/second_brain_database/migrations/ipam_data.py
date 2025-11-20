"""
IPAM continent-country mapping data.

This module defines the predefined continent-country mappings with fixed X octet ranges
for the hierarchical IP allocation system.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any

# Predefined continent-country mappings with X octet ranges
# These mappings are immutable and define the geographic structure of the IPAM system
CONTINENT_COUNTRY_MAPPINGS: List[Dict[str, Any]] = [
    # Asia
    {
        "continent": "Asia",
        "country": "India",
        "x_start": 0,
        "x_end": 29,
        "total_blocks": 30 * 256,  # 7,680 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "UAE",
        "x_start": 30,
        "x_end": 37,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "Singapore",
        "x_start": 38,
        "x_end": 45,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "Japan",
        "x_start": 46,
        "x_end": 53,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "South Korea",
        "x_start": 54,
        "x_end": 61,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "Indonesia",
        "x_start": 62,
        "x_end": 69,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Asia",
        "country": "Taiwan",
        "x_start": 70,
        "x_end": 77,
        "total_blocks": 8 * 256,  # 2,048 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # Africa
    {
        "continent": "Africa",
        "country": "South Africa",
        "x_start": 78,
        "x_end": 97,
        "total_blocks": 20 * 256,  # 5,120 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # Europe
    {
        "continent": "Europe",
        "country": "Finland",
        "x_start": 98,
        "x_end": 107,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Europe",
        "country": "Sweden",
        "x_start": 108,
        "x_end": 117,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Europe",
        "country": "Poland",
        "x_start": 118,
        "x_end": 127,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "Europe",
        "country": "Spain",
        "x_start": 128,
        "x_end": 137,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # North America
    {
        "continent": "North America",
        "country": "Canada",
        "x_start": 138,
        "x_end": 152,
        "total_blocks": 15 * 256,  # 3,840 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "North America",
        "country": "United States",
        "x_start": 153,
        "x_end": 167,
        "total_blocks": 15 * 256,  # 3,840 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # South America
    {
        "continent": "South America",
        "country": "Brazil",
        "x_start": 168,
        "x_end": 177,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    {
        "continent": "South America",
        "country": "Chile",
        "x_start": 178,
        "x_end": 187,
        "total_blocks": 10 * 256,  # 2,560 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # Australia
    {
        "continent": "Australia",
        "country": "Australia",
        "x_start": 188,
        "x_end": 207,
        "total_blocks": 20 * 256,  # 5,120 possible /24 regions
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    },
    # Reserved
    {
        "continent": "Reserved",
        "country": "Reserved",
        "x_start": 208,
        "x_end": 255,
        "total_blocks": 48 * 256,  # 12,288 possible /24 regions
        "is_reserved": True,
        "created_at": datetime.now(timezone.utc),
    },
]
