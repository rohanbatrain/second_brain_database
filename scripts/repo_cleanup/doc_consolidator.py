#!/usr/bin/env python3
"""
Documentation Consolidator Module
Merges and consolidates documentation files.
"""

from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import re


class DocConsolidator:
    """Consolidates and merges documentation files."""

    # Documentation merge groups
    MERGE_GROUPS = {
        'production_guide': {
            'output': 'docs/production/PRODUCTION_GUIDE.md',
            'sources': [
                'PRODUCTION_CHECKLIST.md',
                'DEPLOYMENT_GUIDE.md',
                'DEPLOYMENT_COMPLETE.md',
            ],
            'title': '🚀 Production Deployment Guide',
            'description': 'Comprehensive guide for production deployment and operations'
        },
        'mcp_integration': {
            'output': 'docs/integrations/mcp/MCP_INTEGRATION_GUIDE.md',
            'sources': [
                'MCP_PRODUCTION_DEPLOYMENT_MODERN.md',

            ],
            'title': '🔌 MCP Integration Guide',
            'description': 'Complete guide for Model Context Protocol integration'
        },
        'voice_agent': {
            'output': 'docs/integrations/voice/VOICE_AGENT_GUIDE.md',
            'sources': [
                'VOICE_WORKER_FIX_SUMMARY.md',
                'VOICE_AGENT_TEST_README.md',
            ],
            'title': '🎤 Voice Agent Integration Guide',
            'description': 'Voice agent setup and troubleshooting'
        },
