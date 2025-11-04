#!/usr/bin/env python3
"""
Structure Validator - Validates repository structure and naming conventions
"""
import os
import re
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass
import json


@dataclass
class ValidationIssue:
    """Represents a validation issue"""
    severity: str  # 'error', 'warning', 'info'
    category: str
    path: str
    message: str
    suggestion: str = ""


class StructureValidator:
    """Validates repository structure and conventions"""

    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.issues: List[ValidationIssue] = []

        # Expected directory structure
        self.expected_structure = {
            'src': 'Production source code',
            'tests': 'Test suite',
            'scripts': 'Development and maintenance scripts',
            'docs': 'Documentation',
            'infra': 'Infrastructure and deployment',
            'config': 'Configuration files',
            'automation': 'Automation workflows'
        }

        # Naming conventions
        self.naming_rules = {
            'python_files': r'^[a-z][a-z0-9_]*\.py$',
            'python_modules': r'^[a-z][a-z0-9_]*$',
            'python_classes': r'^[A-Z][a-zA-Z0-9]*$',
            'test_files': r'^test_.*\.py$|.*_test\.py$',
            'markdown_files': r'^[A-Z_][A-Z0-9_]*\.md$|^[a-z][a-z0-9_-]*\.md$'
        }

        # Files that should be in root
        self.root_files = {
            'README.md': 'required',
            'requirements.txt': 'recommended',
            'pyproject.toml': 'recommended',
            '.gitignore': 'required',
            'Makefile': 'recommended'
        }

        # Patterns that indicate files should be moved
        self.misplaced_patterns = {
            'test_*.py': {'current_dir': '.', 'should_be': 'tests/'},
            'Dockerfile*': {'current_dir': '.', 'should_be': 'infra/'},
            '*_config.json': {'current_dir': '.', 'should_be': 'config/'},
            '*.unused': {'current_dir': '*', 'should_be': 'legacy/'},
            '*.log': {'current_dir': '*', 'should_be': 'logs/'}
        }

    def validate_directory_structure(self):
        """Validate main directory structure"""
        print("🔍 Validating directory structure...")

        for expected_dir, description in self.expected_structure.items():
            dir_path = self.repo_root / expected_dir

            if not dir_path.exists():
                self.issues.append(ValidationIssue(
                    severity='warning',
                    category='structure',
                    path=expected_dir,
                    message=f"Expected directory '{expected_dir}' not found",
                    suggestion=f"Create {expected_dir}/ for {description}"
                ))
            elif not dir_path.is_dir():
                self.issues.append(ValidationIssue(
                    severity='error',
                    category='structure',
                    path=expected_dir,
                    message=f"'{expected_dir}' exists but is not a directory",
                    suggestion=f"Remove or rename the file and create directory"
                ))

    def validate_root_files(self):
        """Validate presence of important root files"""
        print("🔍 Validating root files...")

        for file_name, requirement in self.root_files.items():
            file_path = self.repo_root / file_name

            if not file_path.exists():
                severity = 'error' if requirement == 'required' else 'warning'
                self.issues.append(ValidationIssue(
                    severity=severity,
                    category='root_files',
                    path=file_name,
                    message=f"{requirement.title()} file '{file_name}' not found",
                    suggestion=f"Create {file_name} in repository root"
                ))

    def validate_naming_conventions(self):
        """Validate file and directory naming conventions"""
        print("🔍 Validating naming conventions...")

        for root, dirs, files in os.walk(self.repo_root):
            root_path = Path(root)

            # Skip hidden and excluded directories
            if any(part.startswith('.') for part in root_path.parts):
                continue

            # Validate directory names
            for dir_name in dirs:
                if dir_name.startswith('.') or dir_name in ['__pycache__', 'node_modules']:
                    continue

                # Check for spaces in directory names
                if ' ' in dir_name:
                    self.issues.append(ValidationIssue(
                        severity='warning',
                        category='naming',
                        path=str(root_path / dir_name),
                        message=f"Directory name contains spaces: '{dir_name}'",
                        suggestion=f"Rename to: '{dir_name.replace(' ', '_')}'"
                    ))

                # Check for uppercase in module directories (within src/)
                if 'src' in root_path.parts and dir_name[0].isupper():
                    self.issues.append(ValidationIssue(
                        severity='info',
                        category='naming',
                        path=str(root_path / dir_name),
                        message=f"Python package directory starts with uppercase: '{dir_name}'",
                        suggestion="Python packages should use lowercase names"
                    ))

            # Validate file names
            for file_name in files:
                file_path = root_path / file_name
                rel_path = file_path.relative_to(self.repo_root)

                # Check Python files
                if file_name.endswith('.py'):
                    if not re.match(self.naming_rules['python_files'], file_name):
                        # Exception for test files
                        if not re.match(self.naming_rules['test_files'], file_name):
                            self.issues.append(ValidationIssue(
                                severity='info',
                                category='naming',
                                path=str(rel_path),
                                message=f"Python file doesn't follow naming convention: '{file_name}'",
                                suggestion="Use lowercase with underscores (snake_case)"
                            ))

                # Check for spaces in filenames
                if ' ' in file_name:
                    self.issues.append(ValidationIssue(
                        severity='warning',
                        category='naming',
                        path=str(rel_path),
                        message=f"Filename contains spaces: '{file_name}'",
                        suggestion=f"Rename to: '{file_name.replace(' ', '_')}'"
                    ))

    def validate_file_placement(self):
        """Validate files are in correct directories"""
        print("🔍 Validating file placement...")

        for root, _, files in os.walk(self.repo_root):
            root_path = Path(root)

            for file_name in files:
                file_path = root_path / file_name
                rel_path = file_path.relative_to(self.repo_root)
                current_dir = str(rel_path.parent)

                # Check against misplaced patterns
                for pattern, rule in self.misplaced_patterns.items():
                    if file_path.match(pattern):
                        expected_dir = rule['should_be']

                        # Check if it's in wrong location
                        if rule['current_dir'] == '.' and root_path == self.repo_root:
                            if not str(rel_path).startswith(expected_dir):
                                self.issues.append(ValidationIssue(
                                    severity='warning',
                                    category='placement',
                                    path=str(rel_path),
                                    message=f"File should be in {expected_dir}: '{file_name}'",
                                    suggestion=f"Move to {expected_dir}{file_name}"
                                ))
                        elif rule['current_dir'] == '*':
                            if not str(rel_path).startswith(expected_dir):
                                self.issues.append(ValidationIssue(
                                    severity='warning',
                                    category='placement',
                                    path=str(rel_path),
                                    message=f"File should be in {expected_dir}: '{file_name}'",
                                    suggestion=f"Move to {expected_dir}{file_name}"
                                ))

    def validate_documentation(self):
        """Validate documentation completeness"""
        print("🔍 Validating documentation...")

        docs_dir = self.repo_root / 'docs'

        if not docs_dir.exists():
            return

        # Check for README in docs
        docs_readme = docs_dir / 'README.md'
        if not docs_readme.exists():
            self.issues.append(ValidationIssue(
                severity='info',
                category='documentation',
                path='docs/README.md',
                message="No README.md found in docs/",
                suggestion="Create docs/README.md as documentation index"
            ))

        # Check for duplicate or redundant docs
        md_files = list(docs_dir.rglob('*.md'))

        # Look for similar filenames
        file_names = [f.stem.lower() for f in md_files]
        duplicates = set()

        for i, name1 in enumerate(file_names):
            for name2 in file_names[i+1:]:
                # Check for very similar names
                if name1 in name2 or name2 in name1:
                    duplicates.add((md_files[i].name, md_files[file_names.index(name2)].name))

        for dup in duplicates:
            self.issues.append(ValidationIssue(
                severity='info',
                category='documentation',
                path=f"docs/{dup[0]} and docs/{dup[1]}",
                message=f"Potentially duplicate documentation: {dup[0]} and {dup[1]}",
                suggestion="Review and merge if redundant"
            ))

    def validate_python_imports(self):
        """Check for common import issues"""
        print("🔍 Validating Python imports...")

        src_dir = self.repo_root / 'src'

        if not src_dir.exists():
            return

        for py_file in src_dir.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Check for relative imports outside package
                if '../' in content:
                    self.issues.append(ValidationIssue(
                        severity='warning',
                        category='imports',
                        path=str(py_file.relative_to(self.repo_root)),
                        message="Contains parent directory imports (../)",
                        suggestion="Use absolute imports from package root"
                    ))

                # Check for wildcard imports
                if re.search(r'from .* import \*', content):
                    self.issues.append(ValidationIssue(
                        severity='info',
                        category='imports',
                        path=str(py_file.relative_to(self.repo_root)),
                        message="Contains wildcard imports (import *)",
                        suggestion="Import specific items instead of using *"
                    ))

            except Exception as e:
                pass  # Skip files that can't be read

    def run_validation(self) -> Dict:
        """Run all validations"""
        print("\n🔍 Starting Repository Structure Validation")
        print("="*60)

        self.issues.clear()

        # Run all validation checks
        self.validate_directory_structure()
        self.validate_root_files()
        self.validate_naming_conventions()
        self.validate_file_placement()
        self.validate_documentation()
        self.validate_python_imports()

        # Generate report
        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate validation report"""
        from datetime import datetime
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_issues': len(self.issues),
            'by_severity': {
                'error': 0,
                'warning': 0,
                'info': 0
            },
            'by_category': {},
            'issues': []
        }

        for issue in self.issues:
            # Count by severity
            report['by_severity'][issue.severity] += 1

            # Count by category
            if issue.category not in report['by_category']:
                report['by_category'][issue.category] = 0
            report['by_category'][issue.category] += 1

            # Add to issues list
            report['issues'].append({
                'severity': issue.severity,
                'category': issue.category,
                'path': issue.path,
                'message': issue.message,
                'suggestion': issue.suggestion
            })

        return report

    def print_report(self, report: Dict):
        """Print validation report to console"""
        print("\n" + "="*60)
        print("📊 VALIDATION REPORT")
        print("="*60)

        print(f"\nTotal issues found: {report['total_issues']}")

        print("\nBy Severity:")
        for severity, count in report['by_severity'].items():
            icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(severity, '•')
            print(f"  {icon} {severity.title()}: {count}")

        print("\nBy Category:")
        for category, count in sorted(report['by_category'].items()):
            print(f"  • {category}: {count}")

        # Print issues grouped by severity
        for severity in ['error', 'warning', 'info']:
            severity_issues = [i for i in report['issues'] if i['severity'] == severity]

            if severity_issues:
                icon = {'error': '❌', 'warning': '⚠️', 'info': 'ℹ️'}.get(severity, '•')
                print(f"\n{icon} {severity.upper()} Issues:")
                print("-"*60)

                for issue in severity_issues[:10]:  # Show first 10
                    print(f"\n  {issue['path']}")
                    print(f"  {issue['message']}")
                    if issue['suggestion']:
                        print(f"  💡 {issue['suggestion']}")

                if len(severity_issues) > 10:
                    print(f"\n  ... and {len(severity_issues) - 10} more {severity} issues")

    def save_report(self, report: Dict, output_path: str):
        """Save report to JSON file"""
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ Validation report saved to: {output_path}")


def main():
    """Main execution"""
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    print("🔍 Repository Structure Validator")
    print(f"Repository: {repo_root}\n")

    validator = StructureValidator(repo_root)
    report = validator.run_validation()

    validator.print_report(report)

    # Save report
    output_dir = Path(repo_root) / 'scripts' / 'repo_cleanup' / 'reports'
    output_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    validator.save_report(
        report,
        str(output_dir / f'validation_report_{timestamp}.json')
    )

    print("\n✨ Validation complete!")

    # Exit with error code if there are errors
    if report['by_severity']['error'] > 0:
        print("\n⚠️  Errors found - please address before proceeding with cleanup")
        exit(1)
    else:
        print("\n✅ No critical errors found")
        exit(0)


if __name__ == '__main__':
    main()
