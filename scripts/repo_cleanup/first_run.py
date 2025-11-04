#!/usr/bin/env python3
"""
First Run - Initial setup and guided tour for the cleanup system
"""
import os
import sys
from pathlib import Path


def print_banner():
    """Print welcome banner"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                                                                   ║
    ║           🧹 REPOSITORY CLEANUP SYSTEM - FIRST RUN 🧹             ║
    ║                                                                   ║
    ║              Welcome to your repository cleanup!                 ║
    ║                                                                   ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def check_system():
    """Check system requirements"""
    print("\n📋 Checking system requirements...")
    print("-" * 70)

    # Check Python version
    import sys
    python_version = sys.version_info
    if python_version >= (3, 8):
        print(f"✅ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"⚠️  Python {python_version.major}.{python_version.minor} (3.8+ recommended)")

    # Check Git
    try:
        import subprocess
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Git installed: {result.stdout.strip()}")
        else:
            print("⚠️  Git not found (optional but recommended)")
    except Exception:  # TODO: Use specific exception type
        print("⚠️  Git not found (optional but recommended)")

    # Check repo root
    repo_root = Path(__file__).parent.parent.parent
    print(f"✅ Repository root: {repo_root}")

    # Check if in git repo
    git_dir = repo_root / '.git'
    if git_dir.exists():
        print("✅ Git repository detected")
    else:
        print("⚠️  Not a git repository (backups will still work)")

    print()


def show_overview():
    """Show system overview"""
    print("\n📚 WHAT THIS SYSTEM DOES")
    print("-" * 70)
    print("""
This cleanup system will help you:

  1. 🔍 Analyze your repository structure
     → Categorize files by type and purpose
     → Identify misplaced or redundant files
     → Generate detailed reports

  2. 🔐 Create safety backups
     → Full snapshots before any changes
     → Integrity verification
     → Easy restore functionality

  3. 📦 Reorganize files
     → Move files to appropriate directories
     → Consolidate documentation
     → Preserve all content (nothing deleted!)

  4. ✅ Validate structure
     → Check naming conventions
     → Verify directory structure
     → Identify issues and suggest fixes

  5. 📊 Generate reports
     → Migration plans
     → Validation results
     → Execution logs
""")


def show_quick_commands():
    """Show quick command reference"""
    print("\n⚡ QUICK COMMAND REFERENCE")
    print("-" * 70)
    print("""
Interactive Mode (Recommended for first-time users):
  $ python scripts/repo_cleanup/quick_start.py
  $ ./scripts/repo_cleanup/cleanup.sh start

Full Cleanup (One command does everything):
  $ python scripts/repo_cleanup/run_cleanup.py

Individual Operations:
  $ python scripts/repo_cleanup/file_analyzer.py        # Analyze files
  $ python scripts/repo_cleanup/structure_validator.py  # Validate structure
  $ python scripts/repo_cleanup/backup_manager.py create "My backup"

View Information:
  $ python scripts/repo_cleanup/system_info.py     # System information
  $ python scripts/repo_cleanup/usage_guide.py     # Full usage guide
  $ ./scripts/repo_cleanup/cleanup.sh help         # Shell script help
""")


def show_safety_info():
    """Show safety information"""
    print("\n🛡️  SAFETY GUARANTEES")
    print("-" * 70)
    print("""
This system is designed to be SAFE:

  ✅ Nothing is ever deleted - only moved or consolidated
  ✅ Automatic backups before any changes
  ✅ Dry-run mode shows what will happen before executing
  ✅ Git integration prevents working on main/master
  ✅ Easy restore from any backup
  ✅ All changes tracked in detailed logs

If anything goes wrong:
  → Restore from backup: backup_manager.py restore <snapshot>
  → Git reset: git reset --hard HEAD~1
  → Everything is reversible!
""")


def show_next_steps():
    """Show recommended next steps"""
    print("\n🚀 RECOMMENDED NEXT STEPS")
    print("-" * 70)
    print("""
For first-time users, we recommend:

  1. Read the documentation:
     $ cat scripts/repo_cleanup/README.md

  2. View the usage guide:
     $ python scripts/repo_cleanup/usage_guide.py

  3. Create a backup (just to be safe):
     $ python scripts/repo_cleanup/backup_manager.py create "Before cleanup"

  4. Analyze your repository:
     $ python scripts/repo_cleanup/file_analyzer.py

  5. Review the migration plan:
     $ cat scripts/repo_cleanup/reports/migration_plan_*.md

  6. Run the interactive wizard:
     $ python scripts/repo_cleanup/quick_start.py

Or skip ahead and run the full cleanup:
     $ python scripts/repo_cleanup/run_cleanup.py
""")


def offer_quick_start():
    """Offer to launch quick start wizard"""
    print("\n" + "=" * 70)
    response = input("\n🎯 Would you like to launch the interactive wizard now? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        print("\n🚀 Launching interactive wizard...\n")
        import subprocess
        script_path = Path(__file__).parent / 'quick_start.py'
        subprocess.run([sys.executable, str(script_path)])
    else:
        print("\n👍 No problem! You can run it anytime with:")
        print("   $ python scripts/repo_cleanup/quick_start.py")
        print("\nOr explore individual scripts:")
        print("   $ python scripts/repo_cleanup/system_info.py")
        print("   $ python scripts/repo_cleanup/usage_guide.py")


def main():
    """Main execution"""
    print_banner()
    check_system()
    show_overview()
    show_quick_commands()
    show_safety_info()
    show_next_steps()
    offer_quick_start()

    print("\n" + "=" * 70)
    print("📖 Full documentation: scripts/repo_cleanup/README.md")
    print("=" * 70)
    print("\n✨ Happy cleaning! ✨\n")


if __name__ == '__main__':
    main()
