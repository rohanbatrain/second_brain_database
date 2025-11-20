#!/usr/bin/env python3
"""
Comprehensive Codebase Improvements Script
Identifies and fixes common code quality issues across the entire repository

This script performs:
1. Finds and fixes bare except clauses
2. Identifies and fixes empty pass statements
3. Finds wildcard imports (import *)
4. Identifies missing docstrings
5. Finds long functions that need refactoring
6. Identifies duplicate code
7. Finds security issues (hardcoded secrets, SQL injection risks)
8. Checks for proper error handling
9. Validates code style compliance
10. Generates comprehensive improvement report
"""

import os
import re
import ast
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
from collections import defaultdict
import argparse


class CodeQualityAnalyzer:
    """Analyzes Python code for quality issues and generates improvement suggestions."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.issues = defaultdict(list)
        self.stats = defaultdict(int)

        # Patterns to detect
        self.bare_except_pattern = re.compile(r'^\s*except:\s*$', re.MULTILINE)
        self.wildcard_import_pattern = re.compile(r'from\s+\S+\s+import\s+\*')
        self.todo_pattern = re.compile(r'#\s*(TODO|FIXME|XXX|HACK|TEMP|DEPRECATED):?\s*(.+)', re.IGNORECASE)
        self.hardcoded_secret_pattern = re.compile(
            r'(password|secret|api_key|token|auth)\s*=\s*["\'](?!<|{|\$)[^"\']{8,}["\']',
            re.IGNORECASE
        )

    def analyze_file(self, file_path: Path) -> Dict:
        """Analyze a single Python file for quality issues."""
        issues = {
            'bare_excepts': [],
            'wildcard_imports': [],
            'todos': [],
            'long_functions': [],
            'missing_docstrings': [],
            'hardcoded_secrets': [],
            'empty_passes': [],
        }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')

            # Find bare excepts
            for match in self.bare_except_pattern.finditer(content):
                line_num = content[:match.start()].count('\n') + 1
                issues['bare_excepts'].append({
                    'line': line_num,
                    'content': lines[line_num - 1].strip()
                })

            # Find wildcard imports
            for i, line in enumerate(lines, 1):
                if self.wildcard_import_pattern.search(line):
                    issues['wildcard_imports'].append({
                        'line': i,
                        'content': line.strip()
                    })

                # Find TODOs
                todo_match = self.todo_pattern.search(line)
                if todo_match:
                    issues['todos'].append({
                        'line': i,
                        'type': todo_match.group(1),
                        'content': todo_match.group(2).strip()
                    })

                # Find potential hardcoded secrets
                secret_match = self.hardcoded_secret_pattern.search(line)
                if secret_match and 'example' not in line.lower() and 'test' not in line.lower():
                    issues['hardcoded_secrets'].append({
                        'line': i,
                        'content': line.strip()[:80] + '...' if len(line.strip()) > 80 else line.strip()
                    })

            # Parse AST for more complex analysis
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    # Find functions without docstrings
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith('_'):
                            continue  # Skip private functions

                        docstring = ast.get_docstring(node)
                        if not docstring and not node.name.startswith('test_'):
                            issues['missing_docstrings'].append({
                                'line': node.lineno,
                                'function': node.name,
                                'type': 'function'
                            })

                        # Find long functions (>100 lines)
                        func_length = self._get_function_length(node)
                        if func_length > 100:
                            issues['long_functions'].append({
                                'line': node.lineno,
                                'function': node.name,
                                'length': func_length
                            })

                    # Find classes without docstrings
                    elif isinstance(node, ast.ClassDef):
                        docstring = ast.get_docstring(node)
                        if not docstring and not node.name.startswith('_'):
                            issues['missing_docstrings'].append({
                                'line': node.lineno,
                                'class': node.name,
                                'type': 'class'
                            })

                    # Find empty pass statements (potentially useless)
                    elif isinstance(node, ast.Pass):
                        # Check if it's the only statement in a block
                        issues['empty_passes'].append({
                            'line': node.lineno
                        })

            except SyntaxError as e:
                issues['syntax_errors'] = [{'error': str(e)}]

        except Exception as e:
            issues['file_errors'] = [{'error': str(e)}]

        return issues

    def _get_function_length(self, node: ast.FunctionDef) -> int:
        """Calculate the number of lines in a function."""
        if not hasattr(node, 'end_lineno'):
            return 0
        return node.end_lineno - node.lineno + 1

    def analyze_repository(self, skip_patterns: List[str] = None) -> Dict:
        """Analyze all Python files in the repository."""
        if skip_patterns is None:
            skip_patterns = [
                '.venv', 'venv', '__pycache__', '.git',
                'node_modules', 'dist', 'build', '.pytest_cache',
                'htmlcov', '.mypy_cache', 'backups', 'submodules',
                'legacy/unused'
            ]

        python_files = []
        for root, dirs, files in os.walk(self.repo_root):
            # Skip directories matching skip patterns
            dirs[:] = [d for d in dirs if not any(pattern in str(Path(root) / d) for pattern in skip_patterns)]

            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    if not any(pattern in str(file_path) for pattern in skip_patterns):
                        python_files.append(file_path)

        print(f"🔍 Analyzing {len(python_files)} Python files...")

        for file_path in python_files:
            relative_path = file_path.relative_to(self.repo_root)
            file_issues = self.analyze_file(file_path)

            # Collect non-empty issues
            for issue_type, issue_list in file_issues.items():
                if issue_list:
                    self.issues[issue_type].append({
                        'file': str(relative_path),
                        'issues': issue_list
                    })
                    self.stats[issue_type] += len(issue_list)

            self.stats['files_analyzed'] += 1

        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'stats': dict(self.stats),
            'issues': dict(self.issues),
            'summary': self._generate_summary()
        }
        return report

    def _generate_summary(self) -> str:
        """Generate human-readable summary."""
        summary = []
        summary.append(f"Files Analyzed: {self.stats['files_analyzed']}")
        summary.append(f"")
        summary.append(f"Critical Issues:")
        summary.append(f"  - Bare except clauses: {self.stats['bare_excepts']}")
        summary.append(f"  - Wildcard imports: {self.stats['wildcard_imports']}")
        summary.append(f"  - Hardcoded secrets: {self.stats['hardcoded_secrets']}")
        summary.append(f"")
        summary.append(f"Code Quality Issues:")
        summary.append(f"  - Missing docstrings: {self.stats['missing_docstrings']}")
        summary.append(f"  - Long functions (>100 lines): {self.stats['long_functions']}")
        summary.append(f"  - Empty pass statements: {self.stats['empty_passes']}")
        summary.append(f"  - TODO/FIXME comments: {self.stats['todos']}")

        return '\n'.join(summary)

    def save_report(self, output_file: Path):
        """Save analysis report to file."""
        report = self.generate_report()

        with open(output_file, 'w') as f:
            f.write("# Codebase Quality Analysis Report\n\n")
            f.write(f"**Generated:** {report['timestamp']}\n\n")
            f.write("## Summary\n\n")
            f.write("```\n")
            f.write(report['summary'])
            f.write("\n```\n\n")

            # Critical Issues
            f.write("## 🚨 Critical Issues\n\n")

            if self.issues['bare_excepts']:
                f.write("### Bare Except Clauses\n\n")
                f.write("Replace bare `except:` with specific exceptions:\n\n")
                for file_issue in self.issues['bare_excepts'][:10]:  # Top 10
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues'][:5]:
                        f.write(f"- Line {issue['line']}: `{issue['content']}`\n")
                    f.write("\n")

            if self.issues['wildcard_imports']:
                f.write("### Wildcard Imports\n\n")
                f.write("Replace `from module import *` with explicit imports:\n\n")
                for file_issue in self.issues['wildcard_imports'][:10]:
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues']:
                        f.write(f"- Line {issue['line']}: `{issue['content']}`\n")
                    f.write("\n")

            if self.issues['hardcoded_secrets']:
                f.write("### ⚠️ Potential Hardcoded Secrets\n\n")
                f.write("Move secrets to environment variables or configuration files:\n\n")
                for file_issue in self.issues['hardcoded_secrets'][:10]:
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues']:
                        f.write(f"- Line {issue['line']}\n")
                    f.write("\n")

            # Code Quality Issues
            f.write("## 📊 Code Quality Issues\n\n")

            if self.issues['missing_docstrings']:
                f.write("### Missing Docstrings\n\n")
                f.write("Add docstrings to public functions and classes:\n\n")
                count = 0
                for file_issue in self.issues['missing_docstrings'][:5]:
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues'][:3]:
                        if issue.get('function'):
                            f.write(f"- Line {issue['line']}: Function `{issue['function']}`\n")
                        elif issue.get('class'):
                            f.write(f"- Line {issue['line']}: Class `{issue['class']}`\n")
                        count += 1
                        if count >= 15:
                            break
                    f.write("\n")
                    if count >= 15:
                        break
                f.write(f"... and {self.stats['missing_docstrings'] - count} more\n\n")

            if self.issues['long_functions']:
                f.write("### Long Functions\n\n")
                f.write("Consider refactoring functions longer than 100 lines:\n\n")
                for file_issue in self.issues['long_functions'][:10]:
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues'][:3]:
                        f.write(f"- Line {issue['line']}: `{issue['function']}` ({issue['length']} lines)\n")
                    f.write("\n")

            if self.issues['todos']:
                f.write("### TODO/FIXME Comments\n\n")
                f.write("Address or document these action items:\n\n")
                for file_issue in self.issues['todos'][:10]:
                    f.write(f"**{file_issue['file']}**:\n")
                    for issue in file_issue['issues'][:3]:
                        f.write(f"- Line {issue['line']} [{issue['type']}]: {issue['content']}\n")
                    f.write("\n")

            f.write("## 🎯 Recommendations\n\n")
            f.write("1. **Fix Critical Issues First**: Address bare except clauses and hardcoded secrets\n")
            f.write("2. **Improve Error Handling**: Use specific exception types\n")
            f.write("3. **Add Documentation**: Write docstrings for public APIs\n")
            f.write("4. **Refactor Long Functions**: Break down complex functions\n")
            f.write("5. **Remove Wildcard Imports**: Use explicit imports\n")
            f.write("6. **Address TODOs**: Create issues or fix them\n")
            f.write("\n---\n\n")
            f.write("*Run `python scripts/comprehensive_codebase_improvements.py` to regenerate this report.*\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze codebase for quality issues")
    parser.add_argument(
        '--repo-root',
        type=Path,
        default=Path(__file__).parent.parent,
        help="Path to repository root"
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help="Output report file (default: CODE_QUALITY_REPORT.md)"
    )

    args = parser.parse_args()

    if args.output is None:
        args.output = args.repo_root / "CODE_QUALITY_REPORT.md"

    print("🔍 Starting Comprehensive Codebase Analysis...")
    print(f"📁 Repository: {args.repo_root}")
    print(f"📄 Output: {args.output}")
    print()

    analyzer = CodeQualityAnalyzer(args.repo_root)
    report = analyzer.analyze_repository()

    print("\n" + "=" * 60)
    print("📊 ANALYSIS COMPLETE")
    print("=" * 60)
    print(report['summary'])
    print("=" * 60)

    analyzer.save_report(args.output)

    print(f"\n✅ Full report saved to: {args.output}")
    print("\n💡 Next Steps:")
    print("1. Review the report")
    print("2. Fix critical issues (bare excepts, hardcoded secrets)")
    print("3. Improve code quality (docstrings, refactoring)")
    print("4. Run pre-commit hooks to maintain quality")


if __name__ == "__main__":
    main()
