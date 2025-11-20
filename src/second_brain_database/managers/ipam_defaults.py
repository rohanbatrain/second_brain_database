"""
Default IPAM country mappings based on SOP.

This module provides default continent-country mappings for automatic seeding
when the database is empty. Based on Hierarchical IP Allocation Rules (10.X.Y.Z).
"""

from datetime import datetime, timezone
from typing import Dict, List

# Continent → Country Mapping (Fixed) from SOP
DEFAULT_COUNTRY_MAPPINGS = [
    # Asia
    {"continent": "Asia", "country": "India", "x_start": 0, "x_end": 29},
    {"continent": "Asia", "country": "UAE", "x_start": 30, "x_end": 37},
    {"continent": "Asia", "country": "Singapore", "x_start": 38, "x_end": 45},
    {"continent": "Asia", "country": "Japan", "x_start": 46, "x_end": 53},
    {"continent": "Asia", "country": "South Korea", "x_start": 54, "x_end": 61},
    {"continent": "Asia", "country": "Indonesia", "x_start": 62, "x_end": 69},
    {"continent": "Asia", "country": "Taiwan", "x_start": 70, "x_end": 77},
    # Africa
    {"continent": "Africa", "country": "South Africa", "x_start": 78, "x_end": 97},
    # Europe
    {"continent": "Europe", "country": "Finland", "x_start": 98, "x_end": 107},
    {"continent": "Europe", "country": "Sweden", "x_start": 108, "x_end": 117},
    {"continent": "Europe", "country": "Poland", "x_start": 118, "x_end": 127},
    {"continent": "Europe", "country": "Spain", "x_start": 128, "x_end": 137},
    # North America
    {"continent": "North America", "country": "Canada", "x_start": 138, "x_end": 152},
    {"continent": "North America", "country": "United States", "x_start": 153, "x_end": 167},
    # South America
    {"continent": "South America", "country": "Brazil", "x_start": 168, "x_end": 177},
    {"continent": "South America", "country": "Chile", "x_start": 178, "x_end": 187},
    # Australia
    {"continent": "Australia", "country": "Australia", "x_start": 188, "x_end": 207},
    # Reserved
    {"continent": "Reserved", "country": "Future Use", "x_start": 208, "x_end": 255},
]


def get_default_country_documents() -> List[Dict]:
    """
    Generate default country mapping documents for database insertion.

    Returns:
        List of country mapping documents with metadata
    """
    documents = []
    current_time = datetime.now(timezone.utc)

    for mapping in DEFAULT_COUNTRY_MAPPINGS:
        # Calculate total blocks (number of X values)
        total_blocks = mapping["x_end"] - mapping["x_start"] + 1

        doc = {
            "continent": mapping["continent"],
            "country": mapping["country"],
            "x_start": mapping["x_start"],
            "x_end": mapping["x_end"],
            "total_blocks": total_blocks,
            "allocated_regions": 0,  # Initially no regions allocated
            "remaining_capacity": total_blocks * 256,  # Each X has 256 Y values
            "utilization_percent": 0.0,
            "is_reserved": mapping["country"] == "Future Use",
            "created_at": current_time,
            "updated_at": current_time,
        }
        documents.append(doc)

    return documents
