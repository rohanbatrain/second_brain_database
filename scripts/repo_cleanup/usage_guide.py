#!/usr/bin/env python3
"""
Usage Examples - Generate usage examples and documentation
"""

USAGE_GUIDE = """
╔═══════════════════════════════════════════════════════════════════╗
║         🧹 REPOSITORY CLEANUP SYSTEM - USAGE GUIDE                ║
╚═══════════════════════════════════════════════════════════════════╝

📋 TABLE OF CONTENTS
────────────────────────────────────────────────────────────────────

1. Quick Start (Recommended)
2. Full Cleanup Process
3. Individual Operations
4. Backup Management
5. Report Analysis
6. Troubleshooting
7. Advanced Usage

════════════════════════════════════════════════════════════════════
1️⃣  QUICK START (RECOMMENDED FOR FIRST-TIME USERS)
════════════════════════════════════════════════════════════════════

🎯 Using the Shell Script (Easiest):

   cd scripts/repo_cleanup
   ./cleanup.sh start

🎯 Using Python Directly:

   python scripts/repo_cleanup/quick_start.py

This launches an interactive wizard that guides you through all options.

════════════════════════════════════════════════════════════════════
2️⃣  FULL CLEANUP PROCESS
════════════════════════════════════════════════════════════════════

Run the complete cleanup in one command:

   python scripts/repo_cleanup/run_cleanup.py

This will:
   ✓ Create a safety backup
   ✓ Validate current structure
   ✓ Analyze all files
   ✓ Create migration plan (with dry-run preview)
   ✓ Execute migrations (after confirmation)
   ✓ Consolidate documentation
   ✓ Generate final reports

⏱️  Estimated time: 5-15 minutes (depending on repo size)

════════════════════════════════════════════════════════════════════
3️⃣  INDIVIDUAL OPERATIONS
════════════════════════════════════════════════════════════════════

📊 Analyze Files Only:

   python scripts/repo_cleanup/file_analyzer.py

   Output:
   • reports/analysis_report_TIMESTAMP.json
   • reports/migration_plan_TIMESTAMP.md

✅ Validate Structure Only:

   python scripts/repo_cleanup/structure_validator.py

   Output:
   • reports/validation_report_TIMESTAMP.json

📦 Migrate Files Only:

   # Dry-run first (recommended)
   python scripts/repo_cleanup/file_migrator.py --dry-run

   # Then execute
   python scripts/repo_cleanup/file_migrator.py

📚 Consolidate Documentation:

   python scripts/repo_cleanup/doc_consolidator.py

════════════════════════════════════════════════════════════════════
4️⃣  BACKUP MANAGEMENT
════════════════════════════════════════════════════════════════════

💾 Create Backup:

   python scripts/repo_cleanup/backup_manager.py create "My backup description"

📋 List All Backups:

   python scripts/repo_cleanup/backup_manager.py list

🔍 Verify Backup Integrity:

   python scripts/repo_cleanup/backup_manager.py verify snapshot_20231104_120000

📦 Create Compressed Archive:

   # Archive latest snapshot
   python scripts/repo_cleanup/backup_manager.py archive

   # Archive specific snapshot
   python scripts/repo_cleanup/backup_manager.py archive snapshot_20231104_120000

🔙 Restore from Backup:

   ⚠️  WARNING: This will overwrite current files!

   python scripts/repo_cleanup/backup_manager.py restore snapshot_20231104_120000

════════════════════════════════════════════════════════════════════
5️⃣  REPORT ANALYSIS
════════════════════════════════════════════════════════════════════

All reports are saved in: scripts/repo_cleanup/reports/

📊 View Analysis Report:

   cat scripts/repo_cleanup/reports/analysis_report_*.json | jq

   # Or use Python
   python -m json.tool scripts/repo_cleanup/reports/analysis_report_*.json

📋 View Migration Plan:

   cat scripts/repo_cleanup/reports/migration_plan_*.md

✅ View Validation Report:

   cat scripts/repo_cleanup/reports/validation_report_*.json | jq

📝 View Execution Log:

   cat scripts/repo_cleanup/reports/cleanup_execution_*.log

════════════════════════════════════════════════════════════════════
6️⃣  TROUBLESHOOTING
════════════════════════════════════════════════════════════════════

🚨 Cleanup Failed Mid-Process:

   1. List available backups:
      python scripts/repo_cleanup/backup_manager.py list

   2. Restore from backup:
      python scripts/repo_cleanup/backup_manager.py restore <snapshot_name>

🚨 Wrong Files Categorized:

   1. Edit categorization rules in file_analyzer.py
   2. Re-run analysis
   3. Review new migration plan before executing

🚨 Want to Undo Changes:

   If changes are committed:
      git revert HEAD

   If changes are not committed:
      git reset --hard HEAD~1

   Nuclear option (restore from backup):
      python scripts/repo_cleanup/backup_manager.py restore <snapshot_name>

🚨 Script Errors:

   Check Python version (requires 3.8+):
      python --version

   Check if scripts are executable:
      chmod +x scripts/repo_cleanup/*.py

════════════════════════════════════════════════════════════════════
7️⃣  ADVANCED USAGE
════════════════════════════════════════════════════════════════════

🎛️  Customize Categorization Rules:

   Edit: scripts/repo_cleanup/file_analyzer.py

   Add new rule:
   self.rules['my_category'] = {
       'patterns': [r'my_pattern.*\\.py$'],
       'destination': 'my_destination/',
       'confidence': 0.85
   }

🎛️  Customize Validation Rules:

   Edit: scripts/repo_cleanup/structure_validator.py

   Add new validation:
   def validate_my_rule(self):
       # Your validation logic
       pass

🎛️  Non-Interactive Mode (CI/CD):

   python scripts/repo_cleanup/run_cleanup.py --non-interactive

🎛️  Custom Backup Location:

   Edit: scripts/repo_cleanup/backup_manager.py

   Change:
   self.backup_dir = self.repo_root / 'my_custom_backup_dir'

════════════════════════════════════════════════════════════════════
📚 ADDITIONAL RESOURCES
════════════════════════════════════════════════════════════════════

📖 Full Documentation:
   scripts/repo_cleanup/README.md

ℹ️  System Information:
   python scripts/repo_cleanup/system_info.py

🔧 Shell Script:
   ./scripts/repo_cleanup/cleanup.sh help

════════════════════════════════════════════════════════════════════
💡 TIPS & BEST PRACTICES
════════════════════════════════════════════════════════════════════

✓ Always run in interactive mode first
✓ Review migration plan before executing
✓ Create backup before any major changes
✓ Test your application after cleanup
✓ Create PR for team review before merging
✓ Keep backups for at least a week
✓ Use dry-run mode when testing migrations
✓ Check validation reports for quick wins

════════════════════════════════════════════════════════════════════

Questions or issues?
• Check the README: scripts/repo_cleanup/README.md
• View system info: python scripts/repo_cleanup/system_info.py
• List backups: python scripts/repo_cleanup/backup_manager.py list

════════════════════════════════════════════════════════════════════
"""


def main():
    """Print usage guide"""
    print(USAGE_GUIDE)


if __name__ == '__main__':
    main()
