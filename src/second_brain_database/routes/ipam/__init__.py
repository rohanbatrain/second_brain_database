"""
IPAM (IP Address Management) routes module.

This module provides REST API endpoints for hierarchical IP allocation management
following the 10.X.Y.Z private IPv4 address space structure.
"""

from second_brain_database.routes.ipam.routes import router

__all__ = ["router"]
