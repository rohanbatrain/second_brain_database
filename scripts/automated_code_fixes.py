#!/usr/bin/env python3
"""
Automated Code Quality Fixes
Automatically fixes common code quality issues in the codebase

This script fixes:
1. Bare except clauses → except Exception:
2. Updates .gitignore with common patterns
3. Removes trailing whitespace
4. Ensures files end with newline
5. Removes duplicate blank lines
"""

import os
import re
from pathlib import Path
from typing import List, Tuple
import argparse


class AutomatedCodeFixer:
    """Automatically fixes common code quality issues."""

    def __init__(self, repo_root: Path, dry_run: bool = False):
        self.repo_root = repo_root
        self.dry_run = dry_run
        self.stats = {
            'files_processed': 0,
            'bare_excepts_fixed': 0,
            'trailing_whitespace_removed': 0,
            'newlines_added': 0,
            'duplicate_blanks_removed': 0,
        }

    def fix_bare_excepts(self, content: str) -> Tuple[str, int]:
        """Replace bare except: with except Exception:"""
        fixes = 0
        lines = content.split('\n')
        fixed_lines = []

        for i, line in enumerate(lines):
            # Match bare except followed by colon and optional whitespace
            if re.match(r'^(\s*)except:\s*$', line):
                indent = re.match(r'^(\s*)except:\s*$', line).group(1)
                # Check next line to see if it's a comment explaining the broad except
                next_line_is_comment = (i + 1 < len(lines) and
                                       lines[i + 1].strip().startswith('#'))
                if next_line_is_comment:
                    # Keep bare except if there's a comment explaining it
                    fixed_lines.append(line)
                else:
                    # Replace with specific exception
                    fixed_lines.append(f"{indent}except Exception:  # TODO: Use specific exception type")
                    fixes += 1
            else:
                fixed_lines.append(line)

        return '\n'.join(fixed_lines), fixes

    def fix_trailing_whitespace(self, content: str) -> Tuple[str, int]:
        """Remove trailing whitespace from lines."""
        lines = content.split('\n')
        fixed_lines = []
        fixes = 0

        for line in lines:
            if line != line.rstrip():
                fixes += 1
            fixed_lines.append(line.rstrip())

        return '\n'.join(fixed_lines), fixes

    def ensure_final_newline(self, content: str) -> Tuple[str, int]:
        """Ensure file ends with a single newline."""
        if not content.endswith('\n'):
            return content + '\n', 1
        return content, 0

    def remove_duplicate_blank_lines(self, content: str) -> Tuple[str, int]:
        """Remove excessive blank lines (more than 2 consecutive)."""
        # Replace 3+ consecutive newlines with 2
        fixed_content = re.sub(r'\n{4,}', '\n\n\n', content)
        fixes = len(re.findall(r'\n{4,}', content))
        return fixed_content, fixes

    def fix_file(self, file_path: Path) -> bool:
        """Fix a single Python file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            content = original_content
            total_fixes = 0

            # Apply fixes
            content, fixes = self.fix_bare_excepts(content)
            total_fixes += fixes
            self.stats['bare_excepts_fixed'] += fixes

            content, fixes = self.fix_trailing_whitespace(content)
            total_fixes += fixes
            self.stats['trailing_whitespace_removed'] += fixes

            content, fixes = self.remove_duplicate_blank_lines(content)
            total_fixes += fixes
            self.stats['duplicate_blanks_removed'] += fixes

            content, fixes = self.ensure_final_newline(content)
            total_fixes += fixes
            self.stats['newlines_added'] += fixes

            # Write back if changes were made
            if content != original_content:
                if not self.dry_run:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"✅ Fixed: {file_path.relative_to(self.repo_root)} ({total_fixes} issues)")
                else:
                    print(f"🔄 Would fix: {file_path.relative_to(self.repo_root)} ({total_fixes} issues)")
                return True

            return False

        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            return False

    def process_repository(self, skip_patterns: List[str] = None):
        """Process all Python files in the repository."""
        if skip_patterns is None:
            skip_patterns = [
                '.venv', 'venv', '__pycache__', '.git',
                'node_modules', 'dist', 'build', '.pytest_cache',
                'htmlcov', '.mypy_cache', 'backups', 'submodules',
                'legacy/unused'
            ]

        python_files = []
        for root, dirs, files in os.walk(self.repo_root):
            dirs[:] = [d for d in dirs if not any(pattern in str(Path(root) / d) for pattern in skip_patterns)]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    if not any(pattern in str(file_path) for pattern in skip_patterns):
                        python_files.append(file_path)

        print(f"🔧 Processing {len(python_files)} Python files...\n")

        for file_path in python_files:
            if self.fix_file(file_path):
                self.stats['files_processed'] += 1

        return self.stats

    def update_gitignore(self):
        """Update .gitignore with comprehensive patterns."""
        gitignore_path = self.repo_root / '.gitignore'

        additional_patterns = """
# Code Quality Reports
CODE_QUALITY_REPORT.md
CODEBASE_IMPROVEMENTS_*.md

# Jupyter Notebook checkpoints
.ipynb_checkpoints/

# macOS
.DS_Store
.AppleDouble
.LSOverride
._*

# IDEs
.idea/
.vscode/settings.json
.vscode/launch.json
*.swp
*.swo
*~

# Logs
*.log
logs/
*.log.*

# Environment
.env.local
.env.*.local
.sbd.local
.sbd.*.local

# Python
*.pyc
__pycache__/
*.py[cod]
*$py.class
.Python

# Testing
.coverage
.coverage.*
htmlcov/
.pytest_cache/
.tox/
*.cover

# Build
build/
dist/
*.egg-info/
"""

        try:
            with open(gitignore_path, 'r') as f:
                current_content = f.read()

            # Check what's missing
            missing_patterns = []
            for pattern in additional_patterns.strip().split('\n'):
                pattern = pattern.strip()
                if pattern and not pattern.startswith('#') and pattern not in current_content:
                    missing_patterns.append(pattern)

            if missing_patterns:
                if not self.dry_run:
                    with open(gitignore_path, 'a') as f:
                        f.write('\n' + additional_patterns)
                    print(f"✅ Updated .gitignore with {len(missing_patterns)} new patterns")
                else:
                    print(f"🔄 Would add {len(missing_patterns)} patterns to .gitignore")

        except Exception as e:
            print(f"❌ Error updating .gitignore: {e}")


def main():
    parser = argparse.ArgumentParser(description="Automated code quality fixes")
    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).parent.parent,
        help="Path to repository root"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be changed without making changes"
    )

    args = parser.parse_args()

    print("🔧 Starting Automated Code Quality Fixes...")
    print(f"📁 Repository: {args.repo_root}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'EXECUTE'}\n")

    fixer = AutomatedCodeFixer(args.repo_root, args.dry_run)

    # Update .gitignore
    print("📝 Updating .gitignore...")
    fixer.update_gitignore()
    print()

    # Process Python files
    stats = fixer.process_repository()

    print("\n" + "=" * 60)
    print("📊 FIXES COMPLETE")
    print("=" * 60)
    print(f"Files processed: {stats['files_processed']}")
    print(f"Bare excepts fixed: {stats['bare_excepts_fixed']}")
    print(f"Trailing whitespace removed: {stats['trailing_whitespace_removed']}")
    print(f"Duplicate blanks removed: {stats['duplicate_blanks_removed']}")
    print(f"Final newlines added: {stats['newlines_added']}")
    print("=" * 60)

    if args.dry_run:
        print("\n⚠️  This was a DRY RUN - no changes were made")
        print("Run without --dry-run to apply fixes")
    else:
        print("\n✅ All fixes applied successfully!")
        print("\n💡 Next steps:")
        print("1. Review changes with git diff")
        print("2. Run tests to ensure nothing broke")
        print("3. Commit the improvements")


if __name__ == "__main__":
    main()
