#!/usr/bin/env python3
"""
System Info - Display information about the cleanup system
"""
import os
from pathlib import Path
from datetime import datetime


def print_system_info():
    """Print cleanup system information"""
    repo_root = Path(__file__).parent.parent.parent
    cleanup_dir = repo_root / 'scripts' / 'repo_cleanup'

    print("\n" + "="*70)
    print("🧹 REPOSITORY CLEANUP SYSTEM - INFO")
    print("="*70)
    print()

    # System info
    print("📍 Locations:")
    print(f"   Repository Root: {repo_root}")
    print(f"   Cleanup Scripts: {cleanup_dir}")
    print(f"   Reports: {cleanup_dir / 'reports'}")
    print(f"   Backups: {repo_root / 'backups'}")
    print()

    # Available scripts
    print("📜 Available Scripts:")
    scripts = sorted([f for f in cleanup_dir.glob('*.py') if f.name != '__init__.py'])
    for script in scripts:
        size = script.stat().st_size / 1024
        print(f"   • {script.name:<30} ({size:.1f} KB)")
    print()

    # Recent activity
    reports_dir = cleanup_dir / 'reports'
    if reports_dir.exists():
        reports = sorted(reports_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if reports:
            print("📊 Recent Activity:")
            for report in reports[:5]:
                mtime = datetime.fromtimestamp(report.stat().st_mtime)
                print(f"   • {report.name}")
                print(f"     {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print()

    # Backups
    backup_dir = repo_root / 'backups'
    if backup_dir.exists():
        snapshots = [d for d in backup_dir.iterdir() if d.is_dir()]
        archives = [f for f in backup_dir.iterdir() if f.suffix == '.gz']

        if snapshots or archives:
            print(f"💾 Backups: {len(snapshots)} snapshots, {len(archives)} archives")

            if snapshots:
                latest = max(snapshots, key=lambda p: p.stat().st_mtime)
                mtime = datetime.fromtimestamp(latest.stat().st_mtime)
                print(f"   Latest: {latest.name} ({mtime.strftime('%Y-%m-%d %H:%M:%S')})")
            print()

    # Quick start commands
    print("🚀 Quick Start:")
    print()
    print("   Run full cleanup:")
    print("   $ python scripts/repo_cleanup/quick_start.py")
    print()
    print("   Or directly:")
    print("   $ python scripts/repo_cleanup/run_cleanup.py")
    print()
    print("   Analyze only:")
    print("   $ python scripts/repo_cleanup/file_analyzer.py")
    print()
    print("   Create backup:")
    print("   $ python scripts/repo_cleanup/backup_manager.py create 'My backup'")
    print()

    print("="*70)
    print("📖 For full documentation: scripts/repo_cleanup/README.md")
    print("="*70)
    print()


if __name__ == '__main__':
    print_system_info()
