#!/usr/bin/env python3
"""
Quick Start - Interactive wizard for repository cleanup
"""
import os
import sys
from pathlib import Path


def print_header():
    """Print welcome header"""
    print("\n" + "="*70)
    print("🧹 REPOSITORY CLEANUP - QUICK START WIZARD")
    print("="*70)
    print()


def print_menu():
    """Print main menu"""
    print("\nWhat would you like to do?")
    print()
    print("  1. 🚀 Run Full Cleanup (Recommended)")
    print("  2. 📊 Analyze Repository Only")
    print("  3. ✅ Validate Structure Only")
    print("  4. 💾 Create Backup Only")
    print("  5. 📋 View Reports")
    print("  6. 🔙 List/Restore Backups")
    print("  7. 📖 View Documentation")
    print("  8. ❌ Exit")
    print()


def run_command(script_name: str, args: list = None):
    """Run a cleanup script"""
    repo_root = Path(__file__).parent.parent.parent
    script_path = repo_root / 'scripts' / 'repo_cleanup' / script_name

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    print(f"\n{'='*70}")
    print(f"Running: {script_name}")
    print(f"{'='*70}\n")

    import subprocess
    result = subprocess.run(cmd, cwd=repo_root)

    return result.returncode


def option_full_cleanup():
    """Option 1: Run full cleanup"""
    print("\n🚀 FULL CLEANUP MODE")
    print("="*70)
    print()
    print("This will perform the following steps:")
    print("  1. Create a safety backup")
    print("  2. Validate current structure")
    print("  3. Analyze all files")
    print("  4. Create migration plan")
    print("  5. Execute migration (with dry-run first)")
    print("  6. Consolidate documentation")
    print("  7. Generate final reports")
    print()
    print("⚠️  This process may take several minutes.")
    print("⚠️  A git branch will be created for the cleanup.")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        return run_command('run_cleanup.py')
    else:
        print("Cancelled.")
        return 0


def option_analyze():
    """Option 2: Analyze only"""
    print("\n📊 ANALYSIS MODE")
    print("="*70)
    print()
    print("This will:")
    print("  • Scan all files in the repository")
    print("  • Categorize files by type and purpose")
    print("  • Suggest destinations for each file")
    print("  • Generate detailed reports")
    print()
    print("No files will be moved or modified.")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        return run_command('file_analyzer.py')
    else:
        print("Cancelled.")
        return 0


def option_validate():
    """Option 3: Validate only"""
    print("\n✅ VALIDATION MODE")
    print("="*70)
    print()
    print("This will:")
    print("  • Check directory structure")
    print("  • Validate naming conventions")
    print("  • Check file placement")
    print("  • Verify documentation completeness")
    print("  • Check Python imports")
    print()
    print("No files will be moved or modified.")
    print()

    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        return run_command('structure_validator.py')
    else:
        print("Cancelled.")
        return 0


def option_backup():
    """Option 4: Create backup"""
    print("\n💾 BACKUP MODE")
    print("="*70)
    print()
    print("Create a safety snapshot of your repository.")
    print()

    description = input("Enter backup description (or press Enter for default): ").strip()
    if not description:
        description = "Manual backup"

    return run_command('backup_manager.py', ['create', description])


def option_view_reports():
    """Option 5: View reports"""
    print("\n📋 VIEWING REPORTS")
    print("="*70)
    print()

    repo_root = Path(__file__).parent.parent.parent
    reports_dir = repo_root / 'scripts' / 'repo_cleanup' / 'reports'

    if not reports_dir.exists():
        print("No reports directory found.")
        return 0

    report_files = sorted(reports_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

    if not report_files:
        print("No reports found. Run analysis or validation first.")
        return 0

    print("Recent reports:")
    print()

    for i, report_file in enumerate(report_files[:10], 1):
        size_kb = report_file.stat().st_size / 1024
        from datetime import datetime
        mtime = datetime.fromtimestamp(report_file.stat().st_mtime)
        print(f"  {i}. {report_file.name}")
        print(f"     Size: {size_kb:.1f} KB | Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    print("\nTo view a report:")
    print(f"  cd {reports_dir}")
    print("  cat <report_name>")
    print()

    return 0


def option_backups():
    """Option 6: List/restore backups"""
    print("\n🔙 BACKUP MANAGEMENT")
    print("="*70)
    print()
    print("What would you like to do?")
    print()
    print("  1. List all backups")
    print("  2. Verify backup integrity")
    print("  3. Restore from backup")
    print("  4. Create archive")
    print("  5. Back to main menu")
    print()

    choice = input("Enter choice (1-5): ").strip()

    if choice == '1':
        return run_command('backup_manager.py', ['list'])

    elif choice == '2':
        snapshot_name = input("Enter snapshot name: ").strip()
        return run_command('backup_manager.py', ['verify', snapshot_name])

    elif choice == '3':
        print("\n⚠️  WARNING: This will overwrite current files!")
        print("Make sure you have committed or backed up recent changes.")
        print()
        snapshot_name = input("Enter snapshot name to restore: ").strip()
        return run_command('backup_manager.py', ['restore', snapshot_name])

    elif choice == '4':
        snapshot_name = input("Enter snapshot name (or press Enter for latest): ").strip()
        args = ['archive'] if not snapshot_name else ['archive', snapshot_name]
        return run_command('backup_manager.py', args)

    else:
        return 0


def option_docs():
    """Option 7: View documentation"""
    print("\n📖 DOCUMENTATION")
    print("="*70)
    print()

    repo_root = Path(__file__).parent.parent.parent
    readme_path = repo_root / 'scripts' / 'repo_cleanup' / 'README.md'

    if readme_path.exists():
        print(f"Documentation location: {readme_path}")
        print()
        print("View with:")
        print(f"  cat {readme_path}")
        print(f"  open {readme_path}")
        print()

        response = input("Display README now? (yes/no): ")
        if response.lower() == 'yes':
            with open(readme_path) as f:
                print("\n" + "="*70)
                print(f.read())
                print("="*70)
    else:
        print("README not found.")

    return 0


def main():
    """Main menu loop"""
    print_header()

    print("Welcome to the Repository Cleanup System!")
    print()
    print("This interactive wizard will help you clean and reorganize")
    print("your repository safely, without losing any code or documentation.")
    print()

    while True:
        print_menu()
        choice = input("Enter your choice (1-8): ").strip()

        if choice == '1':
            option_full_cleanup()

        elif choice == '2':
            option_analyze()

        elif choice == '3':
            option_validate()

        elif choice == '4':
            option_backup()

        elif choice == '5':
            option_view_reports()

        elif choice == '6':
            option_backups()

        elif choice == '7':
            option_docs()

        elif choice == '8':
            print("\n👋 Goodbye!")
            break

        else:
            print("\n❌ Invalid choice. Please enter 1-8.")

        input("\nPress Enter to continue...")

    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
        sys.exit(0)
