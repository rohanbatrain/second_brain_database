#!/usr/bin/env python3
"""
File Migrator Module
Handles safe file migration to new directory structure.
"""

import shutil
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import datetime


class FileMigrator:
    """Manages file migration operations with safety checks."""

    # Comprehensive migration map
    MIGRATION_MAP = {
        # Infrastructure files
        "infra/docker/": [
            "Dockerfile",
            "docker-compose.yml",
            "docker-compose copy.yml.bkp.yml",
        ],

        # Maintenance scripts
        "scripts/maintenance/": [
            "fix_all_indentation.py",
            "clear_rate_limits.py",
            "install_deepseek.py",
            "check_mcp_health.py",
            "clean_guidance_prompts.py",
            "fix_resource_indentation.py",
            "verify_task3_implementation.py",
            "update_mcp_resources.py",
            "update_mcp_tools.py",
            "verify_family_setup.py",
            "fix_mcp_auth_now.py",
            "verify_platform_config.py",
        ],

        # Tool scripts
        "scripts/tools/": [
            "mcp_connection_guide.py",
            "cleanup_repository.py",
        ],

        # Production documentation
        "docs/production/": [
            "PRODUCTION_CHECKLIST.md",
            "DEPLOYMENT_GUIDE.md",
            "DEPLOYMENT_COMPLETE.md",
            "PRODUCTION_SETUP.md",
        ],

        # Integration documentation - MCP
        "docs/integrations/mcp/": [
            "MCP_PRODUCTION_DEPLOYMENT_MODERN.md",

            "kiro_mcp_config.json",
            "vscode_mcp_config.json",
        ],

        # Integration documentation - Family
        "docs/integrations/family/": [
            "family_integration_validation_results.json",
        ],

        # Integration documentation - Voice
        "docs/integrations/voice/": [
            "VOICE_WORKER_FIX_SUMMARY.md",
            "VOICE_AGENT_TEST_README.md",
            "run_voice_agent.sh",
            "test_voice_agent.sh",
            "test_voice_config.env",
            "voice_agent_test.html",
        ],



        # Legacy/Archive - Database files
        "archive/db_files/": [
            "celerybeat-schedule",
            "celerybeat-schedule-shm",
            "celerybeat-schedule-wal",
        ],

        # Legacy/Archive - Notebooks
        "archive/notebooks/": [
            "repo_cleanup_analysis.ipynb",
        ],
    }

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = Path(repo_root)
        self.dry_run = dry_run
        self.migrations_log: List[Tuple[str, str, bool]] = []
        self.backup_dir = self.repo_root / ".cleanup_backup" / datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_directory_structure(self):
        """Create all target directories."""
        directories = set()

        # Extract all unique directories from migration map
        for dest_dir in self.MIGRATION_MAP.keys():
            directories.add(dest_dir)

        # Create directories
        for dir_path in sorted(directories):
            full_path = self.repo_root / dir_path
            if not self.dry_run:
                full_path.mkdir(parents=True, exist_ok=True)
                print(f"  📁 Created: {dir_path}")
            else:
                print(f"  📁 Would create: {dir_path}")

    def backup_file(self, file_path: Path) -> bool:
        """Create backup of file before moving."""
        if self.dry_run:
            return True

        try:
            relative_path = file_path.relative_to(self.repo_root)
            backup_path = self.backup_dir / relative_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file_path, backup_path)
            return True
        except Exception as e:
            print(f"    ⚠️  Backup failed: {e}")
            return False

    def move_file(self, src: str, dst_dir: str) -> Tuple[str, str, bool]:
        """
        Move a file from source to destination directory.

        Returns:
            Tuple of (source, destination, success)
        """
        src_path = self.repo_root / src
        dst_path = self.repo_root / dst_dir / Path(src).name

        # Check if source exists
        if not src_path.exists():
            print(f"  ⚠️  Source not found: {src}")
            return (src, dst_dir, False)

        # Check if destination already exists
        if dst_path.exists() and not self.dry_run:
            print(f"  ⚠️  Destination exists: {dst_path}")
            return (src, dst_dir, False)

        if self.dry_run:
            print(f"  🔄 Would move: {src} → {dst_dir}")
            return (src, dst_dir, True)

        try:
            # Backup original file
            if not self.backup_file(src_path):
                return (src, dst_dir, False)

            # Ensure destination directory exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Move file
            shutil.move(str(src_path), str(dst_path))
            print(f"  ✅ Moved: {src} → {dst_dir}")
            return (src, dst_dir, True)

        except Exception as e:
            print(f"  ❌ Error moving {src}: {e}")
            return (src, dst_dir, False)

    def move_directory(self, src: str, dst_dir: str) -> Tuple[str, str, bool]:
        """
        Move an entire directory to destination.

        Returns:
            Tuple of (source, destination, success)
        """
        src_path = self.repo_root / src
        dst_path = self.repo_root / dst_dir / Path(src).name

        if not src_path.exists() or not src_path.is_dir():
            print(f"  ⚠️  Source directory not found: {src}")
            return (src, dst_dir, False)

        if dst_path.exists() and not self.dry_run:
            print(f"  ⚠️  Destination directory exists: {dst_path}")
            return (src, dst_dir, False)

        if self.dry_run:
            print(f"  🔄 Would move directory: {src}/ → {dst_dir}")
            return (src, dst_dir, True)

        try:
            # Ensure destination parent exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            # Move directory
            shutil.move(str(src_path), str(dst_path))
            print(f"  ✅ Moved directory: {src}/ → {dst_dir}")
            return (src, dst_dir, True)

        except Exception as e:
            print(f"  ❌ Error moving directory {src}: {e}")
            return (src, dst_dir, False)

    def execute_migrations(self) -> List[Tuple[str, str, bool]]:
        """Execute all file migrations."""
        print("\n🚚 Starting file migrations...\n")

        # Create directory structure first
        self.create_directory_structure()

        print("\n📦 Migrating files...\n")

        # Execute file moves
        for dst_dir, files in self.MIGRATION_MAP.items():
            if not files:
                continue

            print(f"📂 Target: {dst_dir}")

            for file_path in files:
                result = self.move_file(file_path, dst_dir)
                self.migrations_log.append(result)

        # Special handling for directory moves
        print(f"\n📂 Moving directories...\n")

        # Move TODOS directory
        if (self.repo_root / "TODOS").exists():
            result = self.move_directory("TODOS", "docs/plans/")
            self.migrations_log.append(result)

        # Move n8n_workflows if needed
        if (self.repo_root / "n8n_workflows").exists():
            result = self.move_directory("n8n_workflows", "automation/")
            self.migrations_log.append(result)

        return self.migrations_log

    def get_migration_stats(self) -> Dict:
        """Get statistics about migrations."""
        total = len(self.migrations_log)
        successful = sum(1 for _, _, success in self.migrations_log if success)
        failed = total - successful

        return {
            'total': total,
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / total * 100) if total > 0 else 0
        }

    def generate_migration_report(self) -> str:
        """Generate detailed migration report."""
        stats = self.get_migration_stats()

        report = f"""# File Migration Report
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Mode: {'DRY RUN' if self.dry_run else 'PRODUCTION'}

## Statistics
- Total migrations: {stats['total']}
- Successful: {stats['successful']}
- Failed: {stats['failed']}
- Success rate: {stats['success_rate']:.1f}%

## Migration Details

"""

        # Group by destination
        by_destination = {}
        for src, dst, success in self.migrations_log:
            if dst not in by_destination:
                by_destination[dst] = []
            by_destination[dst].append((src, success))

        for dst, moves in sorted(by_destination.items()):
            report += f"### {dst}\n\n"
            for src, success in moves:
                status = "✅" if success else "❌"
                report += f"{status} {src}\n"
            report += "\n"

        return report


if __name__ == "__main__":
    # Standalone testing
    import sys
    repo_root = Path(__file__).parent.parent.parent

    print("Testing FileMigrator in dry-run mode...\n")

    migrator = FileMigrator(repo_root, dry_run=True)
    migrator.execute_migrations()

    stats = migrator.get_migration_stats()
    print(f"\n📊 Migration Statistics:")
    print(f"   Total: {stats['total']}")
    print(f"   Successful: {stats['successful']}")
    print(f"   Failed: {stats['failed']}")
