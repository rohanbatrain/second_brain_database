#!/usr/bin/env python3
"""
Main Cleanup Runner - Orchestrates the complete repository cleanup process
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import subprocess
import json


class CleanupRunner:
    """Main coordinator for repository cleanup"""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.scripts_dir = self.repo_root / 'scripts' / 'repo_cleanup'
        self.reports_dir = self.scripts_dir / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Track execution state
        self.current_phase = None
        self.execution_log = []

    def log(self, message: str, level: str = 'INFO'):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{level}] {message}"
        print(log_entry)
        self.execution_log.append(log_entry)

    def run_script(self, script_name: str, args: list = None) -> int:
        """Run a Python script and return exit code"""
        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            self.log(f"Script not found: {script_name}", 'ERROR')
            return 1

        cmd = [sys.executable, str(script_path)]
        if args:
            cmd.extend(args)

        self.log(f"Running: {script_name}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_root,
                capture_output=False,
                text=True
            )
            return result.returncode
        except Exception as e:
            self.log(f"Error running {script_name}: {e}", 'ERROR')
            return 1

    def check_git_status(self) -> bool:
        """Check if git repository is clean"""
        self.log("Checking git status...")

        try:
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )

            if result.stdout.strip():
                self.log("⚠️  Git repository has uncommitted changes", 'WARNING')
                response = input("Continue anyway? (yes/no): ")
                return response.lower() == 'yes'
            else:
                self.log("✅ Git repository is clean")
                return True

        except Exception as e:
            self.log(f"Could not check git status: {e}", 'WARNING')
            return True

    def create_cleanup_branch(self) -> bool:
        """Create a new branch for cleanup work"""
        branch_name = f"refactor/cleanup-{datetime.now().strftime('%Y%m%d')}"

        self.log(f"Creating cleanup branch: {branch_name}")

        try:
            # Check if branch already exists
            result = subprocess.run(
                ['git', 'rev-parse', '--verify', branch_name],
                cwd=self.repo_root,
                capture_output=True
            )

            if result.returncode == 0:
                self.log(f"Branch {branch_name} already exists", 'WARNING')
                response = input("Switch to existing branch? (yes/no): ")

                if response.lower() == 'yes':
                    subprocess.run(['git', 'checkout', branch_name], cwd=self.repo_root)
                    return True
                else:
                    return False

            # Create new branch
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=self.repo_root)
            self.log(f"✅ Created and switched to branch: {branch_name}")
            return True

        except Exception as e:
            self.log(f"Could not create branch: {e}", 'ERROR')
            return False

    def phase_1_safety_backup(self) -> bool:
        """Phase 1: Create safety backup"""
        self.current_phase = "Phase 1: Safety Backup"
        self.log(f"\n{'='*60}")
        self.log(f"🔐 {self.current_phase}")
        self.log(f"{'='*60}\n")

        # Create backup
        return_code = self.run_script('backup_manager.py', ['create', 'Pre-cleanup safety backup'])

        if return_code != 0:
            self.log("Backup failed! Aborting cleanup.", 'ERROR')
            return False

        self.log("✅ Phase 1 complete\n")
        return True

    def phase_2_validation(self) -> bool:
        """Phase 2: Validate current structure"""
        self.current_phase = "Phase 2: Structure Validation"
        self.log(f"\n{'='*60}")
        self.log(f"🔍 {self.current_phase}")
        self.log(f"{'='*60}\n")

        # Run validation (non-critical, warnings are OK)
        return_code = self.run_script('structure_validator.py')

        # Validation can return non-zero for warnings, but we continue
        self.log("✅ Phase 2 complete\n")
        return True

    def phase_3_analysis(self) -> bool:
        """Phase 3: Analyze files and create migration plan"""
        self.current_phase = "Phase 3: File Analysis"
        self.log(f"\n{'='*60}")
        self.log(f"📊 {self.current_phase}")
        self.log(f"{'='*60}\n")

        return_code = self.run_script('file_analyzer.py')

        if return_code != 0:
            self.log("Analysis failed!", 'ERROR')
            return False

        self.log("✅ Phase 3 complete\n")
        return True

    def phase_4_migration(self, dry_run: bool = True) -> bool:
        """Phase 4: Execute file migration"""
        self.current_phase = f"Phase 4: File Migration ({'DRY RUN' if dry_run else 'LIVE'})"
        self.log(f"\n{'='*60}")
        self.log(f"📦 {self.current_phase}")
        self.log(f"{'='*60}\n")

        args = ['--dry-run'] if dry_run else []
        return_code = self.run_script('file_migrator.py', args)

        if return_code != 0:
            self.log("Migration failed!", 'ERROR')
            return False

        if dry_run:
            self.log("\n⚠️  This was a DRY RUN - no files were actually moved")
            response = input("\nProceed with actual migration? (yes/no): ")

            if response.lower() == 'yes':
                return self.phase_4_migration(dry_run=False)
            else:
                self.log("Migration cancelled by user")
                return False

        self.log("✅ Phase 4 complete\n")
        return True

    def phase_5_documentation(self) -> bool:
        """Phase 5: Consolidate documentation"""
        self.current_phase = "Phase 5: Documentation Consolidation"
        self.log(f"\n{'='*60}")
        self.log(f"📚 {self.current_phase}")
        self.log(f"{'='*60}\n")

        return_code = self.run_script('doc_consolidator.py')

        if return_code != 0:
            self.log("Documentation consolidation failed!", 'ERROR')
            return False

        self.log("✅ Phase 5 complete\n")
        return True

    def phase_6_verification(self) -> bool:
        """Phase 6: Final verification"""
        self.current_phase = "Phase 6: Final Verification"
        self.log(f"\n{'='*60}")
        self.log(f"✔️  {self.current_phase}")
        self.log(f"{'='*60}\n")

        # Run validation again to see improvements
        self.log("Running validation on cleaned structure...")
        self.run_script('structure_validator.py')

        self.log("\n✅ Phase 6 complete\n")
        return True

    def generate_final_report(self):
        """Generate final cleanup report"""
        self.log("\n" + "="*60)
        self.log("📋 CLEANUP SUMMARY")
        self.log("="*60)

        # Save execution log
        log_file = self.reports_dir / f'cleanup_execution_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        with open(log_file, 'w') as f:
            f.write('\n'.join(self.execution_log))

        self.log(f"\nExecution log saved to: {log_file}")

        # Show report files
        self.log("\n📁 Generated Reports:")
        report_files = sorted(self.reports_dir.glob('*'))
        for report_file in report_files[-10:]:  # Show last 10
            size_kb = report_file.stat().st_size / 1024
            self.log(f"  • {report_file.name} ({size_kb:.1f} KB)")

    def run_full_cleanup(self, interactive: bool = True):
        """Run the complete cleanup process"""
        self.log("\n" + "="*60)
        self.log("🧹 REPOSITORY CLEANUP ORCHESTRATOR")
        self.log("="*60)
        self.log(f"Repository: {self.repo_root}")
        self.log(f"Mode: {'Interactive' if interactive else 'Automated'}")
        self.log("")

        # Pre-flight checks
        if not self.check_git_status():
            self.log("Aborting cleanup due to uncommitted changes", 'ERROR')
            return False

        if interactive:
            self.log("\n⚠️  This will perform the following phases:")
            self.log("  1. Create safety backup")
            self.log("  2. Validate current structure")
            self.log("  3. Analyze files and create migration plan")
            self.log("  4. Execute file migration (with dry-run first)")
            self.log("  5. Consolidate documentation")
            self.log("  6. Final verification")

            response = input("\nProceed with cleanup? (yes/no): ")
            if response.lower() != 'yes':
                self.log("Cleanup cancelled by user")
                return False

        # Create cleanup branch
        if not self.create_cleanup_branch():
            self.log("Could not create cleanup branch", 'ERROR')
            return False

        # Execute phases
        try:
            # Phase 1: Backup
            if not self.phase_1_safety_backup():
                return False

            # Phase 2: Validation
            if not self.phase_2_validation():
                return False

            # Phase 3: Analysis
            if not self.phase_3_analysis():
                return False

            # Phase 4: Migration (dry-run, then real)
            if not self.phase_4_migration(dry_run=True):
                return False

            # Phase 5: Documentation
            if not self.phase_5_documentation():
                return False

            # Phase 6: Verification
            if not self.phase_6_verification():
                return False

            # Success!
            self.generate_final_report()

            self.log("\n" + "="*60)
            self.log("✨ CLEANUP COMPLETE! ✨")
            self.log("="*60)
            self.log("\nNext steps:")
            self.log("  1. Review changes in git")
            self.log("  2. Test the application")
            self.log("  3. Commit changes with: git commit -m 'refactor: repository cleanup'")
            self.log("  4. Create PR for team review")

            return True

        except KeyboardInterrupt:
            self.log("\n\n⚠️  Cleanup interrupted by user", 'WARNING')
            self.log("Repository may be in intermediate state")
            self.log("To restore, use: python scripts/repo_cleanup/backup_manager.py restore <snapshot_name>")
            return False

        except Exception as e:
            self.log(f"\n\n❌ Unexpected error: {e}", 'ERROR')
            self.log("To restore, use: python scripts/repo_cleanup/backup_manager.py restore <snapshot_name>")
            return False


def main():
    """Main entry point"""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    runner = CleanupRunner(repo_root)

    # Parse command line args
    interactive = '--non-interactive' not in sys.argv

    success = runner.run_full_cleanup(interactive=interactive)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
