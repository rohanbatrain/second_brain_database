# Repository Cleanup System

A comprehensive Python-based system for safely reorganizing and cleaning up your repository structure.

## 🎯 Purpose

This cleanup system helps you:
- **Reorganize** files into a clean, logical structure
- **Preserve** all code and documentation (nothing is deleted)
- **Consolidate** redundant documentation
- **Validate** naming conventions and structure
- **Track** all changes with detailed logs

## 📦 Components

### Core Scripts

1. **`run_cleanup.py`** - Main orchestrator that runs the full cleanup process
2. **`backup_manager.py`** - Creates and manages safety backups
3. **`file_analyzer.py`** - Analyzes files and suggests categorization
4. **`file_migrator.py`** - Executes file migrations safely
5. **`doc_consolidator.py`** - Merges and reorganizes documentation
6. **`structure_validator.py`** - Validates repository structure and conventions
7. **`cleanup_orchestrator.py`** - Orchestrates the cleanup process

### Support Scripts

- **`quick_start.py`** - Interactive wizard for running cleanup

## 🚀 Quick Start

### Option 1: Full Automated Cleanup

```bash
# Run the complete cleanup process (interactive mode)
python scripts/repo_cleanup/run_cleanup.py

# Non-interactive mode (for CI/CD)
python scripts/repo_cleanup/run_cleanup.py --non-interactive
```

### Option 2: Step-by-Step

```bash
# 1. Create a safety backup
python scripts/repo_cleanup/backup_manager.py create "Before cleanup"

# 2. Analyze current structure
python scripts/repo_cleanup/file_analyzer.py

# 3. Validate structure
python scripts/repo_cleanup/structure_validator.py

# 4. Run migration (dry-run first)
python scripts/repo_cleanup/file_migrator.py --dry-run

# 5. Execute migration
python scripts/repo_cleanup/file_migrator.py

# 6. Consolidate documentation
python scripts/repo_cleanup/doc_consolidator.py
```

### Option 3: Individual Operations

#### Backup Management

```bash
# Create backup
python scripts/repo_cleanup/backup_manager.py create "Manual backup"

# List backups
python scripts/repo_cleanup/backup_manager.py list

# Create archive
python scripts/repo_cleanup/backup_manager.py archive

# Verify backup integrity
python scripts/repo_cleanup/backup_manager.py verify snapshot_20240104_120000

# Restore from backup
python scripts/repo_cleanup/backup_manager.py restore snapshot_20240104_120000
```

#### File Analysis

```bash
# Analyze all files
python scripts/repo_cleanup/file_analyzer.py

# Output: reports/analysis_report_TIMESTAMP.json
# Output: reports/migration_plan_TIMESTAMP.md
```

#### Structure Validation

```bash
# Validate repository structure
python scripts/repo_cleanup/structure_validator.py

# Output: reports/validation_report_TIMESTAMP.json
```

## 📋 Cleanup Process

The cleanup follows this workflow:

```
Phase 1: Safety Backup
   ↓
Phase 2: Structure Validation
   ↓
Phase 3: File Analysis
   ↓
Phase 4: File Migration (Dry-run → Confirm → Execute)
   ↓
Phase 5: Documentation Consolidation
   ↓
Phase 6: Final Verification
   ↓
Generate Reports & Cleanup Log
```

## 📂 Target Structure

The cleanup aims to create this structure:

```
.
├── README.md                    # Main repository README
├── CONTRIBUTING.md              # Contribution guidelines
├── CLEANUP_LOG.md              # Record of all cleanup changes
├── src/                        # Production source code (unchanged)
│   └── second_brain_database/
├── tests/                      # Test suite (unchanged)
├── scripts/                    # Development & maintenance scripts
│   ├── maintenance/            # One-off utilities (verify_*, fix_*, etc.)
│   ├── setup/                  # Installation & setup scripts
│   ├── tools/                  # Development tools
│   └── examples/               # Example scripts
├── docs/                       # Documentation
│   ├── production/             # Production guides
│   ├── integrations/           # Integration docs (MCP, Voice, etc.)
│   │   ├── mcp/
│   │   ├── voice/
│   │   ├── langgraph/
│   │   └── family/
│   ├── guides/                 # User guides
│   ├── specs/                  # Product specifications
│   ├── internal/               # Internal documentation
│   └── plans/                  # Roadmaps & TODOs
├── infra/                      # Infrastructure & deployment
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── setup/
├── config/                     # Configuration files
├── automation/                 # Automation workflows
│   └── n8n_workflows/
├── legacy/                     # Archived/deprecated code
│   ├── unused/                 # .unused files
│   └── temp/                   # Temporary files
└── backups/                    # Safety backups (git-ignored)
```

## 🔧 Configuration

### File Categorization Rules

The system uses pattern-based rules to categorize files. Edit `file_analyzer.py` to customize:

```python
self.rules = {
    'verification_scripts': {
        'patterns': [r'verify_.*\.py$', ...],
        'destination': 'scripts/maintenance/',
        'confidence': 0.9
    },
    # ... add more rules
}
```

### Exclusions

Customize exclusions in individual scripts:

- **Backup exclusions**: Edit `backup_manager.py`
- **Analysis exclusions**: Edit `file_analyzer.py`
- **Validation exclusions**: Edit `structure_validator.py`

## 📊 Reports

All operations generate detailed reports in `scripts/repo_cleanup/reports/`:

- **`analysis_report_*.json`** - File categorization analysis
- **`migration_plan_*.md`** - Detailed migration plan
- **`validation_report_*.json`** - Structure validation results
- **`cleanup_execution_*.log`** - Complete execution log
- **`CLEANUP_LOG.md`** - Human-readable change log

## ✅ Safety Features

1. **Git Integration**
   - Checks for uncommitted changes
   - Creates cleanup branch automatically
   - Never modifies main/master directly

2. **Backup System**
   - Creates full snapshots before changes
   - Verifies backup integrity
   - Easy restore functionality

3. **Dry-Run Mode**
   - Test migrations without making changes
   - Preview exactly what will happen
   - Confirm before executing

4. **Preservation**
   - Nothing is ever deleted
   - Files moved to `legacy/` if uncategorized
   - All documentation consolidated, not removed

## 🔍 Troubleshooting

### Cleanup Failed Mid-Process

```bash
# Restore from most recent backup
python scripts/repo_cleanup/backup_manager.py list
python scripts/repo_cleanup/backup_manager.py restore snapshot_YYYYMMDD_HHMMSS
```

### Files Categorized Incorrectly

1. Edit the categorization rules in `file_analyzer.py`
2. Re-run analysis: `python scripts/repo_cleanup/file_analyzer.py`
3. Review new migration plan before executing

### Want to Undo Changes

```bash
# If committed: revert the commit
git revert HEAD

# If not committed: reset to previous state
git reset --hard HEAD~1

# Nuclear option: restore from backup
python scripts/repo_cleanup/backup_manager.py restore <snapshot_name>
```

## 📝 Best Practices

1. **Always run in interactive mode first** to review each step
2. **Review the migration plan** before executing
3. **Test your application** after cleanup
4. **Create PR for team review** before merging
5. **Keep backups** for at least a week after cleanup

## 🎨 Customization

### Adding New Categorization Rules

Edit `file_analyzer.py`:

```python
self.rules['my_category'] = {
    'patterns': [r'my_pattern.*\.py$'],
    'destination': 'my_destination/',
    'confidence': 0.85
}
```

### Adding New Validations

Edit `structure_validator.py`:

```python
def validate_my_rule(self):
    # Your validation logic
    pass

# Add to run_validation():
self.validate_my_rule()
```

## 🤝 Contributing

To improve the cleanup system:

1. Test changes on a branch
2. Add validation for new rules
3. Update this README
4. Submit PR with examples

## 📄 License

Same as parent repository.

---

**Questions?** Check existing backups with:
```bash
python scripts/repo_cleanup/backup_manager.py list
```

**Need help?** Run validation to see what needs attention:
```bash
python scripts/repo_cleanup/structure_validator.py
```
