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
                'LANGCHAIN_MCP_FULL_COVERAGE.md',
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
        'langgraph_integration': {
            'output': 'docs/integrations/langgraph/LANGGRAPH_GUIDE.md',
            'sources': [
                'LANGGRAPH_PRODUCTION_STATUS.md',
                'LANGGRAPH_ISSUES_AND_FIXES.md',
            ],
            'title': '🕸️ LangGraph Integration Guide',
            'description': 'LangGraph setup, issues, and solutions'
        },
    }

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = Path(repo_root)
        self.dry_run = dry_run
        self.consolidation_log: List[str] = []

    def read_markdown_file(self, file_path: Path) -> str:
        """Read markdown file and return content."""
        try:
            if file_path.exists():
                return file_path.read_text(encoding='utf-8')
            return ""
        except Exception as e:
            print(f"  ⚠️  Error reading {file_path}: {e}")
            return ""

    def merge_documents(self, group_name: str, config: Dict) -> str:
        """
        Merge multiple documents into one.

        Args:
            group_name: Name of the merge group
            config: Configuration dict with sources, output, title, etc.

        Returns:
            Merged content as string
        """
        print(f"  📚 Merging {group_name}...")

        # Start with header
        content = f"""# {config['title']}

> {config['description']}

**Last Updated:** {datetime.now().strftime("%Y-%m-%d")}
**Consolidated from:** {', '.join(config['sources'])}

---

## Table of Contents

"""

        # Collect content from all sources
        sections = []
        toc_entries = []

        for source in config['sources']:
            # Try to find the source file in various locations
            source_paths = [
                self.repo_root / source,
                self.repo_root / 'docs' / source,
                self.repo_root / 'docs' / 'production' / source,
                self.repo_root / 'docs' / 'integrations' / 'mcp' / source,
                self.repo_root / 'docs' / 'integrations' / 'voice' / source,
                self.repo_root / 'docs' / 'integrations' / 'langgraph' / source,
            ]

            source_content = ""
            found_path = None

            for path in source_paths:
                if path.exists():
                    source_content = self.read_markdown_file(path)
                    found_path = path
                    break

            if not source_content:
                print(f"    ⚠️  Source not found: {source}")
                continue

            # Extract title from source
            title_match = re.search(r'^#\s+(.+)$', source_content, re.MULTILINE)
            section_title = title_match.group(1) if title_match else source

            # Remove the first title (we'll use our own)
            source_content = re.sub(r'^#\s+.+$', '', source_content, count=1, flags=re.MULTILINE)

            # Add to sections
            section_anchor = section_title.lower().replace(' ', '-').replace('🚀', '').replace('🔌', '').replace('🎤', '').replace('🕸️', '').strip()
            toc_entries.append(f"- [{section_title}](#{section_anchor})")

            sections.append(f"""
## {section_title}

> **Source:** `{source}`

{source_content.strip()}

---
""")

        # Add TOC
        content += '\n'.join(toc_entries)
        content += '\n\n---\n'

        # Add all sections
        content += '\n'.join(sections)

        # Add footer
        content += f"""

---

## Document History

This document was automatically consolidated from multiple sources on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}.

### Original Sources
"""
        for source in config['sources']:
            content += f"- `{source}`\n"

        return content

    def write_consolidated_doc(self, output_path: Path, content: str) -> bool:
        """Write consolidated document to file."""
        if self.dry_run:
            print(f"    🔍 Would write to: {output_path}")
            return True

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding='utf-8')
            print(f"    ✅ Written to: {output_path}")
            return True
        except Exception as e:
            print(f"    ❌ Error writing {output_path}: {e}")
            return False

    def consolidate_documentation(self) -> List[str]:
        """Consolidate all documentation groups."""
        print("\n📚 Consolidating documentation...\n")

        for group_name, config in self.MERGE_GROUPS.items():
            # Merge documents
            merged_content = self.merge_documents(group_name, config)

            # Write consolidated document
            output_path = self.repo_root / config['output']
            success = self.write_consolidated_doc(output_path, merged_content)

            if success:
                self.consolidation_log.append(f"{group_name} → {config['output']}")

        return self.consolidation_log

    def create_docs_index(self) -> bool:
        """Create master documentation index."""
        print("\n📑 Creating documentation index...\n")

        index_content = f"""# 📚 Documentation Index

**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This index provides quick access to all project documentation.

## 🚀 Production Documentation

### Deployment & Operations
- [Production Guide](production/PRODUCTION_GUIDE.md) - Complete production deployment guide
- [Deployment Checklist](production/DEPLOYMENT_CHECKLIST.md) - Pre-deployment checklist
- [Setup Instructions](production/SETUP_GUIDE.md) - Initial setup instructions

## 🔌 Integration Guides

### MCP (Model Context Protocol)
- [MCP Integration Guide](integrations/mcp/MCP_INTEGRATION_GUIDE.md)
- [MCP Configuration](integrations/mcp/kiro_mcp_config.json)

### Voice Agent
- [Voice Agent Guide](integrations/voice/VOICE_AGENT_GUIDE.md)
- [Voice Testing](integrations/voice/test_voice_agent.sh)

### LangGraph
- [LangGraph Integration Guide](integrations/langgraph/LANGGRAPH_GUIDE.md)
- [Log Monitoring](integrations/langgraph/LOG_MONITORING_GUIDE.md)

### LangChain
- [LangChain Testing](integrations/langchain/LANGCHAIN_TESTING.md)

### Agent Chat
- [Agent Chat UI Setup](integrations/agent_chat/AGENTCHAT_UI_SETUP.md)
- [Integration Success Report](integrations/agent_chat/INTEGRATION_SUCCESS.md)

### Family Features
- [Family Account Documentation](integrations/family/)

## 📋 Planning & Development

### Planning Documents
- [TODOs and Tasks](plans/TODOS/)
- [Development Roadmap](plans/)

## 📖 Additional Resources

### API Documentation
- [Family API Spec](family_sbd_api_spec.md)
- [Backend Purchase Status](backend_family_purchase_status_for_flutter.md)

### Development Guides
- [Development Setup](DEVELOPMENT.md)
- [Dependency Management](DEPENDENCY_MANAGEMENT.md)
- [Error Handling System](ERROR_HANDLING_SYSTEM.md)

### Deployment & Infrastructure
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Infrastructure Setup](../infra/)

## 🏗️ Architecture

### Core Components
- Authentication & Authorization
- Family Management System
- Permanent Token System
- WebAuthn Integration
- Real-time Notifications

### Database
- MongoDB Collections
- Redis Caching
- Data Models

## 🧪 Testing

- [Test Suite Documentation](../tests/README.md)
- Test Coverage Reports
- Integration Tests

## 🔒 Security

- [Security Audit Reports](enhanced_audit_compliance_summary.md)
- WebAuthn Implementation
- Rate Limiting & Throttling

## 📝 Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

---

*This index is automatically maintained. Last regenerated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

        index_path = self.repo_root / "docs" / "README.md"

        if self.dry_run:
            print(f"  🔍 Would create index at: {index_path}")
            return True

        try:
            index_path.parent.mkdir(parents=True, exist_ok=True)
            index_path.write_text(index_content, encoding='utf-8')
            print(f"  ✅ Created documentation index: {index_path}")
            return True
        except Exception as e:
            print(f"  ❌ Error creating index: {e}")
            return False

    def generate_consolidation_report(self) -> str:
        """Generate consolidation report."""
        report = f"""# Documentation Consolidation Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Mode: {'DRY RUN' if self.dry_run else 'PRODUCTION'}

## Summary
- Total consolidations: {len(self.consolidation_log)}

## Consolidations Performed

"""
        for consolidation in self.consolidation_log:
            report += f"- {consolidation}\n"

        return report


if __name__ == "__main__":
    # Standalone testing
    import sys
    repo_root = Path(__file__).parent.parent.parent

    print("Testing DocConsolidator in dry-run mode...\n")

    consolidator = DocConsolidator(repo_root, dry_run=True)
    results = consolidator.consolidate_documentation()
    consolidator.create_docs_index()

    print(f"\n📊 Consolidation Results:")
    for result in results:
        print(f"   - {result}")
