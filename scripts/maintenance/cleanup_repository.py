#!/usr/bin/env python3
"""
Second Brain Database Repository Cleanup Script
Generated on: 2025-11-04 12:00:00

This script safely reorganizes the repository structure while preserving all files.
Run with --dry-run first to see what changes will be made.
"""

import os
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Repository root
REPO_ROOT = Path(__file__).parent

def create_directory_structure():
    """Create the new directory structure"""
    directories = [
        "infra",
        "scripts/maintenance",
        "scripts/tools",
        "automation",
        "docs/production",
        "docs/integrations/mcp",
        "docs/integrations/family",
        "docs/integrations/auth",
        "docs/integrations/voice",
        "docs/specs",
        "docs/plans",
        "legacy"
    ]

    for dir_path in directories:
        full_path = REPO_ROOT / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {dir_path}")

def move_file_safely(src: str, dst_dir: str, dry_run: bool = False):
    """Safely move a file to destination directory"""
    src_path = REPO_ROOT / src
    dst_path = REPO_ROOT / dst_dir / os.path.basename(src)

    if not src_path.exists():
        print(f"⚠️ Source file does not exist: {src}")
        return False

    if dst_path.exists():
        print(f"⚠️ Destination already exists: {dst_path}")
        return False

    if dry_run:
        print(f"🔄 Would move: {src} → {dst_dir}/{os.path.basename(src)}")
        return True

    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_path), str(dst_path))
        print(f"✅ Moved: {src} → {dst_dir}/{os.path.basename(src)}")
        return True
    except Exception as e:
        print(f"❌ Error moving {src}: {e}")
        return False

# File migration mappings - COMPREHENSIVE
MIGRATION_MAP = {
    "scripts/maintenance/": [
        "fix_all_indentation.py",
        "clear_rate_limits.py",
        "install_deepseek.py",
        "check_mcp_health.py",
        "clean_guidance_prompts.py",
        "fix_resource_indentation.py",
        "verify_task3_implementation.py",
        "update_mcp_resources.py",
        "verify_family_setup.py",
        "fix_mcp_auth_now.py",
        "mcp_connection_guide.py"
    ],
    "archive/root_docs/": [
        "LOG_MONITORING_GUIDE.md",
        "VOICE_WORKER_FIX_SUMMARY.md",

}

def create_cleanup_log(moves_made):
    """Create a log of all moves made"""
    log_content = f"""# Repository Cleanup Log
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary
- Total files moved: {len(moves_made)}
- New directory structure created

## File Moves
"""

    for src, dst in moves_made:
        log_content += f"- `{src}` → `{dst}`\n"

    with open(REPO_ROOT / "CLEANUP_LOG.md", "w") as f:
        f.write(log_content)

    print(f"📋 Created cleanup log: CLEANUP_LOG.md")

def main():
    parser = argparse.ArgumentParser(description="Cleanup Second Brain Database repository")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--phase", choices=["1", "2", "3", "all"], default="all", help="Run specific migration phase")

    args = parser.parse_args()

    print("🧠 Second Brain Database Repository Cleanup")
    print("=" * 50)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be moved")

    # Create directory structure
    if not args.dry_run:
        create_directory_structure()

    # Execute migrations
    moves_made = []
    total_moves = 0
    successful_moves = 0

    phase_map = {
        "1": ["docs/production/", "docs/integrations/mcp/", "docs/integrations/family/", "docs/integrations/auth/", "infra/"],
        "2": ["scripts/maintenance/", "scripts/tools/", "automation/", "docs/integrations/voice/", "docs/specs/"],
        "3": ["docs/plans/", "legacy/"]
    }

    phases_to_run = phase_map.get(args.phase, []) if args.phase != "all" else list(MIGRATION_MAP.keys())

    for destination in phases_to_run:
        if destination in MIGRATION_MAP:
            print(f"\n📂 Processing: {destination}")
            for file_path in MIGRATION_MAP[destination]:
                total_moves += 1
                if move_file_safely(file_path, destination, args.dry_run):
                    successful_moves += 1
                    if not args.dry_run:
                        moves_made.append((file_path, destination))

    print(f"\n📊 Summary:")
    print(f"Total files processed: {total_moves}")
    print(f"Successful moves: {successful_moves}")
    print(f"Failed moves: {total_moves - successful_moves}")

    if not args.dry_run and moves_made:
        create_cleanup_log(moves_made)
        print(f"\n🎉 Repository cleanup completed!")
        print(f"Review CLEANUP_LOG.md for details of all changes made.")
    elif args.dry_run:
        print(f"\n🔍 Dry run completed. Use --phase 1,2,3 or remove --dry-run to execute.")

if __name__ == "__main__":
    main()
