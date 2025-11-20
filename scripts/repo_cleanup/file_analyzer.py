#!/usr/bin/env python3
"""
File Analyzer Module
Analyzes repository structure and categorizes files for cleanup.
"""

import re
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict


class FileAnalyzer:
    """Analyzes repository files and categorizes them for cleanup."""

    # File categorization patterns
    PATTERNS = {
        'maintenance_scripts': [
            r'fix_.*\.py$',
            r'verify_.*\.py$',
            r'clear_.*\.py$',
            r'install_.*\.py$',
            r'update_.*\.py$',
            r'check_.*\.py$',
            r'clean_.*\.py$',
        ],
        'production_scripts': [
            r'production.*\.py$',
            r'startup.*\.py$',
            r'.*_app\.py$',
        ],
        'test_scripts': [
            r'test_.*\.py$',
            r'.*_test\.py$',
        ],
        'production_docs': [
            r'PRODUCTION.*\.md$',
            r'DEPLOYMENT.*\.md$',
            r'SETUP.*\.md$',
        ],
        'integration_docs': [
            r'MCP_.*\.md$',
            r'FAMILY_.*\.md$',

            r'VOICE.*\.md$',
        ],
        'planning_docs': [
            r'TODO.*',
            r'PLAN.*\.md$',
        ],
        'legacy_files': [
            r'.*\.unused$',
            r'.*\.bkp.*$',
            r'.*\.old$',
            r'.*_old\..*$',
        ],
        'config_files': [
            r'.*\.json$',
            r'.*\.yml$',
            r'.*\.yaml$',
            r'.*\.toml$',
            r'.*\.env$',
            r'.*\.sbd$',
        ],
    }

    # Directories to skip during analysis
    SKIP_DIRS = {
        '.git', '__pycache__', 'node_modules', '.pytest_cache',
        'htmlcov', '.venv', 'venv', 'env', '.mypy_cache',
        'dist', 'build', '*.egg-info', 'logs', 'pids'
    }

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root)
        self.categorization: Dict[str, List[str]] = defaultdict(list)
        self.file_stats = {
            'total_files': 0,
            'python_files': 0,
            'markdown_files': 0,
            'config_files': 0,
            'test_files': 0,
            'ignored_files': 0,
        }

    def should_skip_dir(self, dir_path: Path) -> bool:
        """Check if directory should be skipped."""
        dir_name = dir_path.name
        return any(
            dir_name == skip or dir_name.startswith('.')
            for skip in self.SKIP_DIRS
        )

    def categorize_file(self, file_path: Path) -> str:
        """Categorize a file based on patterns."""
        relative_path = file_path.relative_to(self.repo_root)
        path_str = str(relative_path)

        # Check each category pattern
        for category, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_str, re.IGNORECASE):
                    return category

        # Default categorization based on location
        if 'src/' in path_str:
            return 'source_code'
        elif 'tests/' in path_str:
            return 'test_files'
        elif 'docs/' in path_str:
            return 'documentation'
        elif 'scripts/' in path_str:
            return 'scripts'
        elif 'infra/' in path_str:
            return 'infrastructure'

        return 'uncategorized'

    def analyze_file(self, file_path: Path):
        """Analyze a single file and update statistics."""
        self.file_stats['total_files'] += 1

        # Update file type stats
        if file_path.suffix == '.py':
            self.file_stats['python_files'] += 1
        elif file_path.suffix == '.md':
            self.file_stats['markdown_files'] += 1
        elif file_path.suffix in {'.json', '.yml', '.yaml', '.toml', '.env', '.sbd'}:
            self.file_stats['config_files'] += 1

        # Check if it's a test file
        if 'test' in file_path.name.lower():
            self.file_stats['test_files'] += 1

        # Categorize
        category = self.categorize_file(file_path)
        relative_path = str(file_path.relative_to(self.repo_root))
        self.categorization[category].append(relative_path)

    def scan_directory(self, directory: Path = None):
        """Recursively scan directory and analyze files."""
        if directory is None:
            directory = self.repo_root

        for item in directory.iterdir():
            if item.is_dir():
                if not self.should_skip_dir(item):
                    self.scan_directory(item)
            elif item.is_file():
                self.analyze_file(item)

    def analyze_repository(self) -> Dict:
        """Perform complete repository analysis."""
        print("🔍 Analyzing repository structure...")

        # Scan all files
        self.scan_directory()

        # Print categorization summary
        print("\n📊 Categorization Summary:")
        for category, files in sorted(self.categorization.items()):
            if files:
                print(f"   {category}: {len(files)} files")

        return {
            'total_files': self.file_stats['total_files'],
            'python_files': self.file_stats['python_files'],
            'markdown_files': self.file_stats['markdown_files'],
            'config_files': self.file_stats['config_files'],
            'test_files': self.file_stats['test_files'],
            'categorization': dict(self.categorization),
        }

    def get_files_by_category(self, category: str) -> List[str]:
        """Get all files in a specific category."""
        return self.categorization.get(category, [])

    def find_duplicate_docs(self) -> Dict[str, List[str]]:
        """Find potentially duplicate documentation files."""
        docs = [f for f in self.categorization.get('documentation', [])
                if f.endswith('.md')]

        # Group by similar names (ignoring case and common prefixes)
        similar_groups = defaultdict(list)

        for doc in docs:
            # Normalize name for comparison
            name = Path(doc).name.lower()
            name = re.sub(r'(production_|deployment_|setup_)', '', name)
            similar_groups[name].append(doc)

        # Return only groups with multiple files
        return {k: v for k, v in similar_groups.items() if len(v) > 1}

    def generate_analysis_report(self) -> str:
        """Generate detailed analysis report."""
        report = f"""# Repository Analysis Report
Generated: {Path(__file__).parent}

## Statistics
- Total files: {self.file_stats['total_files']}
- Python files: {self.file_stats['python_files']}
- Markdown files: {self.file_stats['markdown_files']}
- Config files: {self.file_stats['config_files']}
- Test files: {self.file_stats['test_files']}

## Categorization

"""
        for category, files in sorted(self.categorization.items()):
            if files:
                report += f"### {category.replace('_', ' ').title()} ({len(files)} files)\n\n"
                for file in files[:20]:  # Show first 20
                    report += f"- {file}\n"
                if len(files) > 20:
                    report += f"- ... and {len(files) - 20} more\n"
                report += "\n"

        # Add duplicate analysis
        duplicates = self.find_duplicate_docs()
        if duplicates:
            report += "## Potential Duplicate Documents\n\n"
            for name, docs in duplicates.items():
                report += f"### {name}\n"
                for doc in docs:
                    report += f"- {doc}\n"
                report += "\n"

        return report


if __name__ == "__main__":
    # Standalone testing
    import sys
    repo_root = Path(__file__).parent.parent.parent

    analyzer = FileAnalyzer(repo_root)
    results = analyzer.analyze_repository()

    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print("=" * 70)

    # Generate report
    report = analyzer.generate_analysis_report()
    report_path = repo_root / "ANALYSIS_REPORT.md"
    report_path.write_text(report)

    print(f"\n📄 Report saved to: {report_path}")
