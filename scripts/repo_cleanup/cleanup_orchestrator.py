#!/usr/bin/env python3
"""
Repository Cleanup Orchestrator
Main entry point for repository reorganization and cleanup operations.

This script coordinates the entire cleanup process across multiple phases.
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.repo_cleanup.file_analyzer import FileAnalyzer
from scripts.repo_cleanup.file_migrator import FileMigrator
from scripts.repo_cleanup.doc_consolidator import DocConsolidator
from scripts.repo_cleanup.cleanup_validator import CleanupValidator


class CleanupOrchestrator:
    """Orchestrates the complete repository cleanup process."""

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.start_time = datetime.now()

        # Initialize components
        self.analyzer = FileAnalyzer(repo_root)
        self.migrator = FileMigrator(repo_root, dry_run)
        self.consolidator = DocConsolidator(repo_root, dry_run)
        self.validator = CleanupValidator(repo_root)

        self.results = {
            'analysis': {},
            'migrations': [],
            'consolidations': [],
            'validations': []
        }

    def run_phase_1_analysis(self) -> Dict:
        """Phase 1: Analyze repository structure and categorize files."""
        print("\n" + "=" * 70)
        print("📊 PHASE 1: Repository Analysis")
        print("=" * 70)

        # Analyze file structure
        analysis = self.analyzer.analyze_repository()

        # Print summary
        print(f"\n✅ Analysis Complete:")
        print(f"   - Total files analyzed: {analysis['total_files']}")
        print(f"   - Python scripts: {analysis['python_files']}")
        print(f"   - Markdown docs: {analysis['markdown_files']}")
        print(f"   - Config files: {analysis['config_files']}")
        print(f"   - Test files: {analysis['test_files']}")

        self.results['analysis'] = analysis
        return analysis

    def run_phase_2_migration(self) -> List[Tuple[str, str]]:
        """Phase 2: Migrate files to new structure."""
        print("\n" + "=" * 70)
        print("🚚 PHASE 2: File Migration")
        print("=" * 70)

        if self.dry_run:
            print("🔍 DRY RUN MODE - No files will be moved\n")

        # Execute migrations
        migrations = self.migrator.execute_migrations()

        print(f"\n✅ Migration {'Preview' if self.dry_run else 'Complete'}:")
        print(f"   - Total files processed: {len(migrations)}")
        print(f"   - Successful moves: {sum(1 for _, _, success in migrations if success)}")
        print(f"   - Failed moves: {sum(1 for _, _, success in migrations if not success)}")

        self.results['migrations'] = migrations
        return migrations

    def run_phase_3_consolidation(self) -> List[str]:
        """Phase 3: Consolidate and merge documentation."""
        print("\n" + "=" * 70)
        print("📚 PHASE 3: Documentation Consolidation")
        print("=" * 70)

        # Consolidate docs
        consolidations = self.consolidator.consolidate_documentation()

        print(f"\n✅ Consolidation {'Preview' if self.dry_run else 'Complete'}:")
        print(f"   - Documents merged: {len(consolidations)}")

        self.results['consolidations'] = consolidations
        return consolidations

    def run_phase_4_validation(self) -> Dict:
        """Phase 4: Validate cleanup and generate reports."""
        print("\n" + "=" * 70)
        print("✔️ PHASE 4: Validation & Reporting")
        print("=" * 70)

        # Validate structure
        validation = self.validator.validate_cleanup()

        print(f"\n✅ Validation Complete:")
        print(f"   - Structure valid: {validation['structure_valid']}")
        print(f"   - Missing files: {len(validation['missing_files'])}")
        print(f"   - Orphaned files: {len(validation['orphaned_files'])}")

        self.results['validations'] = validation
        return validation

    def generate_cleanup_log(self):
        """Generate comprehensive cleanup log."""
        log_path = self.repo_root / "CLEANUP_LOG.md"

        content = f"""# Repository Cleanup Log
Generated: {self.start_time.strftime("%Y-%m-%d %H:%M:%S")}
Mode: {'DRY RUN' if self.dry_run else 'PRODUCTION'}

## Summary

- **Duration**: {(datetime.now() - self.start_time).total_seconds():.2f}s
- **Files Analyzed**: {self.results['analysis'].get('total_files', 0)}
- **Files Migrated**: {len(self.results['migrations'])}
- **Documents Consolidated**: {len(self.results['consolidations'])}

## Phase 1: Analysis Results

### File Categories
"""

        # Add analysis details
        if 'categorization' in self.results['analysis']:
            for category, files in self.results['analysis']['categorization'].items():
                content += f"\n#### {category}\n"
                for file in files[:10]:  # Show first 10
                    content += f"- {file}\n"
                if len(files) > 10:
                    content += f"- ... and {len(files) - 10} more\n"

        content += "\n## Phase 2: File Migrations\n\n"

        # Add migration details
        for src, dst, success in self.results['migrations']:
            status = "✅" if success else "❌"
            content += f"{status} `{src}` → `{dst}`\n"

        content += "\n## Phase 3: Documentation Consolidations\n\n"

        # Add consolidation details
        for consolidation in self.results['consolidations']:
            content += f"- {consolidation}\n"

        content += "\n## Phase 4: Validation Results\n\n"

        # Add validation details
        validation = self.results.get('validations', {})
        content += f"- Structure Valid: {validation.get('structure_valid', False)}\n"
        content += f"- Missing Files: {len(validation.get('missing_files', []))}\n"
        content += f"- Orphaned Files: {len(validation.get('orphaned_files', []))}\n"

        if validation.get('missing_files'):
            content += "\n### Missing Files\n"
            for file in validation['missing_files']:
                content += f"- {file}\n"

        if validation.get('orphaned_files'):
            content += "\n### Orphaned Files\n"
            for file in validation['orphaned_files']:
                content += f"- {file}\n"

        content += f"\n---\n*Generated by Repository Cleanup Orchestrator v1.0*\n"

        if not self.dry_run:
            log_path.write_text(content)
            print(f"\n📋 Cleanup log written to: {log_path}")
        else:
            print(f"\n📋 Cleanup log preview (not written in dry-run mode)")
            print(content[:500] + "..." if len(content) > 500 else content)

    def run_full_cleanup(self, phases: List[int] = None):
        """Run complete cleanup process."""
        if phases is None:
            phases = [1, 2, 3, 4]

        print("\n" + "=" * 70)
        print("🧠 Second Brain Database Repository Cleanup")
        print("=" * 70)
        print(f"Mode: {'🔍 DRY RUN' if self.dry_run else '🚀 PRODUCTION'}")
        print(f"Repository: {self.repo_root}")
        print("=" * 70)

        try:
            if 1 in phases:
                self.run_phase_1_analysis()

            if 2 in phases:
                self.run_phase_2_migration()

            if 3 in phases:
                self.run_phase_3_consolidation()

            if 4 in phases:
                self.run_phase_4_validation()

            # Generate final report
            self.generate_cleanup_log()

            print("\n" + "=" * 70)
            print("🎉 Cleanup Process Complete!")
            print("=" * 70)

            return True

        except Exception as e:
            print(f"\n❌ Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Second Brain Database Repository Cleanup Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (preview changes)
  python cleanup_orchestrator.py --dry-run

  # Run specific phases
  python cleanup_orchestrator.py --phases 1 2

  # Full cleanup (production)
  python cleanup_orchestrator.py

  # Analysis only
  python cleanup_orchestrator.py --phases 1 --dry-run
        """
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying files'
    )

    parser.add_argument(
        '--phases',
        nargs='+',
        type=int,
        choices=[1, 2, 3, 4],
        help='Specific phases to run (1=Analysis, 2=Migration, 3=Consolidation, 4=Validation)'
    )

    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).parent.parent.parent,
        help='Repository root directory'
    )

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = CleanupOrchestrator(
        repo_root=args.repo_root,
        dry_run=args.dry_run
    )

    # Run cleanup
    success = orchestrator.run_full_cleanup(phases=args.phases)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
