#!/usr/bin/env python3
"""
Documentation Consolidation Script
Organizes all documentation files into proper directories

This script:
1. Moves implementation/status docs to docs/implementation/
2. Moves cleanup/quality reports to docs/maintenance/
3. Moves integration guides to docs/integrations/
4. Creates a central index in docs/
5. Keeps only essential docs in root (README, QUICKSTART, CHANGELOG)
"""

import shutil
from pathlib import Path
from datetime import datetime


class DocumentationOrganizer:
    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.moves = []
        
    def move_doc(self, filename: str, dest_dir: str, description: str = ""):
        """Move a documentation file to destination directory."""
        src = self.repo_root / filename
        if not src.exists():
            return
            
        dest = self.repo_root / dest_dir
        dest.mkdir(parents=True, exist_ok=True)
        dest_file = dest / filename
        
        if self.dry_run:
            print(f"📦 Would move: {filename} → {dest_dir}/")
        else:
            shutil.move(str(src), str(dest_file))
            print(f"✅ Moved: {filename} → {dest_dir}/")
        
        self.moves.append({
            'file': filename,
            'from': 'root',
            'to': dest_dir,
            'description': description
        })
    
    def organize_docs(self):
        """Organize all documentation files."""
        print("📚 Organizing Documentation Files...\n")
        
        # Implementation & Status Reports
        print("📄 Implementation & Status Reports:")
        self.move_doc("INTEGRATION_SUCCESS.md", "docs/implementation", 
                      "Integration success report")

        self.move_doc("VOICE_AGENT_TEST_README.md", "docs/integrations",
                      "Voice agent testing guide")
        self.move_doc("VOICE_WORKER_FIX_SUMMARY.md", "docs/integrations",
                      "Voice worker fix summary")
        
        # Maintenance & Quality Reports
        print("\n🧹 Maintenance & Quality Reports:")
        self.move_doc("CLEANUP_LOG.md", "docs/maintenance",
                      "Initial cleanup log")
        self.move_doc("COMPREHENSIVE_CLEANUP_LOG.md", "docs/maintenance",
                      "Comprehensive cleanup log")
        self.move_doc("CODEBASE_CLEANUP_COMPLETE.md", "docs/maintenance",
                      "Cleanup completion summary")
        self.move_doc("CODE_QUALITY_REPORT.md", "docs/maintenance",
                      "Code quality analysis report")
        self.move_doc("ANALYSIS_REPORT.md", "docs/maintenance",
                      "Repository analysis report")
        
        # Monitoring & Operations
        print("\n📊 Monitoring & Operations:")
        self.move_doc("LOG_MONITORING_GUIDE.md", "docs/operations",
                      "Log monitoring guide")
        
    def create_docs_index(self):
        """Create a central documentation index."""
        index_content = f"""# Documentation Index

**Last Updated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

This directory contains all project documentation organized by category.

## 📖 Quick Links

- **[README](../README.md)** - Project overview and setup
- **[QUICKSTART](../QUICKSTART.md)** - Quick start guide
- **[Makefile](../Makefile)** - Build and deployment commands

## 📁 Documentation Categories

### 🚀 Implementation & Status
Documentation about feature implementations and project status.

Location: `docs/implementation/`

"""
        

        
        index_content += """
### 🧹 Maintenance & Quality
Code quality reports and maintenance documentation.

Location: `docs/maintenance/`

"""
        
        maintenance_docs = [
            ("CLEANUP_LOG.md", "Initial cleanup log"),
            ("COMPREHENSIVE_CLEANUP_LOG.md", "Comprehensive cleanup log"),
            ("CODEBASE_CLEANUP_COMPLETE.md", "Cleanup completion summary"),
            ("CODE_QUALITY_REPORT.md", "Code quality analysis report"),
            ("ANALYSIS_REPORT.md", "Repository analysis report"),
        ]
        
        for doc, desc in maintenance_docs:
            index_content += f"- **[{doc}](maintenance/{doc})** - {desc}\n"
        
        index_content += """
### 📊 Operations & Monitoring
Operational guides and monitoring documentation.

Location: `docs/operations/`

- **[LOG_MONITORING_GUIDE.md](operations/LOG_MONITORING_GUIDE.md)** - Log monitoring guide

### 📚 Other Documentation

- **[examples/](examples/)** - Example code and HTML demos
- **[validation/](validation/)** - Validation results and reports
- **[analysis/](analysis/)** - Analysis notebooks and reports

## 🔧 Development Tools

- **[scripts/](../scripts/)** - Development and maintenance scripts
- **[tests/](../tests/)** - Test suite documentation
- **[config/](../config/)** - Configuration examples

## 🏗️ Infrastructure

- **[infra/](../infra/)** - Infrastructure and deployment files
- **[automation/](../automation/)** - Automation workflows

## 📝 Notes

- All documentation is written in Markdown format
- Keep documentation up-to-date when making changes
- Follow the existing structure when adding new docs
- Link between documents using relative paths

---

*This index is automatically updated by the documentation organization script.*
"""
        
        index_file = self.repo_root / "docs" / "INDEX.md"
        
        if self.dry_run:
            print(f"\n📋 Would create: docs/INDEX.md")
        else:
            with open(index_file, 'w') as f:
                f.write(index_content)
            print(f"\n✅ Created: docs/INDEX.md")
    
    def create_root_readme_addition(self):
        """Create content to add to root README."""
        addition = """

## 📚 Documentation

All project documentation is organized in the `docs/` directory:

- **[Documentation Index](docs/INDEX.md)** - Complete documentation catalog
- **[Implementation Status](docs/implementation/)** - Feature implementations and status
- **[Integration Guides](docs/integrations/)** - External service integrations
- **[Maintenance](docs/maintenance/)** - Code quality and maintenance reports
- **[Operations](docs/operations/)** - Monitoring and operational guides

For quick start instructions, see [QUICKSTART.md](QUICKSTART.md).
"""
        
        readme_path = self.repo_root / "README.md"
        
        if readme_path.exists():
            with open(readme_path, 'r') as f:
                content = f.read()
            
            if "Documentation Index" not in content and not self.dry_run:
                # Add before the last section or at the end
                if "## License" in content:
                    content = content.replace("## License", addition + "\n## License")
                else:
                    content += addition
                
                with open(readme_path, 'w') as f:
                    f.write(content)
                print("✅ Updated README.md with documentation section")
            elif self.dry_run:
                print("📋 Would update README.md with documentation links")
    
    def generate_summary(self):
        """Generate summary of changes."""
        summary = f"""# Documentation Organization Summary

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Mode:** {"DRY RUN" if self.dry_run else "EXECUTED"}

## Changes Made

### Files Moved: {len(self.moves)}

"""
        
        by_category = {}
        for move in self.moves:
            cat = move['to']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(move)
        
        for category in sorted(by_category.keys()):
            summary += f"\n#### {category}/\n"
            for move in by_category[category]:
                summary += f"- `{move['file']}` - {move['description']}\n"
        
        summary += """

## Documentation Structure

```
docs/
├── INDEX.md                    # Central documentation index
├── implementation/             # Implementation & status reports
├── integrations/               # Integration guides
├── maintenance/                # Maintenance & quality reports
├── operations/                 # Operations & monitoring guides
├── examples/                   # Code examples
├── validation/                 # Validation results
└── analysis/                   # Analysis notebooks
```

## Root Directory

After organization, the root directory contains only:
- **README.md** - Project overview
- **QUICKSTART.md** - Quick start guide  
- **Makefile** - Build commands
- **pyproject.toml** - Python project configuration
- **requirements.txt** - Python dependencies

All other documentation has been organized into the `docs/` directory.

## Benefits

1. ✅ **Cleaner root directory** - Only essential files remain
2. ✅ **Better organization** - Docs grouped by purpose
3. ✅ **Easier navigation** - Central index for all docs
4. ✅ **Improved discoverability** - Logical directory structure
5. ✅ **Maintainability** - Clear location for new docs

---

*Generated by `scripts/organize_documentation.py`*
"""
        
        summary_file = self.repo_root / "docs" / "ORGANIZATION_SUMMARY.md"
        
        if not self.dry_run:
            with open(summary_file, 'w') as f:
                f.write(summary)
            print(f"\n✅ Created: docs/ORGANIZATION_SUMMARY.md")
        else:
            print(f"\n📋 Would create: docs/ORGANIZATION_SUMMARY.md")
        
        return summary


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Organize documentation files")
    parser.add_argument('--dry-run', action='store_true', help="Preview changes without executing")
    args = parser.parse_args()
    
    repo_root = Path(__file__).parent.parent
    
    print("📚 Documentation Organization Script")
    print(f"{'='*60}")
    print(f"Repository: {repo_root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}")
    print(f"{'='*60}\n")
    
    organizer = DocumentationOrganizer(repo_root, args.dry_run)
    
    # Organize documentation
    organizer.organize_docs()
    
    # Create index
    print()
    organizer.create_docs_index()
    
    # Update README
    print()
    organizer.create_root_readme_addition()
    
    # Generate summary
    print()
    organizer.generate_summary()
    
    print(f"\n{'='*60}")
    print(f"📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Files organized: {len(organizer.moves)}")
    print(f"Documentation index: Created")
    print(f"README: Updated")
    print(f"{'='*60}")
    
    if args.dry_run:
        print("\n⚠️  This was a DRY RUN - no changes were made")
        print("Run without --dry-run to execute the organization")
    else:
        print("\n✅ Documentation organization complete!")
        print("\n💡 Next steps:")
        print("1. Review the changes: ls docs/")
        print("2. Check the index: cat docs/INDEX.md")
        print("3. Commit the changes")


if __name__ == "__main__":
    main()
