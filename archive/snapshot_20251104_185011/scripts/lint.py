#!/usr/bin/env python3
"""
Comprehensive linting automation script for Second Brain Database.

This script provides automated code quality checking and formatting using
multiple tools: pylint, black, isort, and mypy.
"""

import argparse
from pathlib import Path
import subprocess
import sys
from typing import List, Optional, Tuple


class LintingTool:
    """Base class for linting tools."""

    def __init__(self, name: str, command: List[str]):
        self.name = name
        self.command = command

    def run(self, paths: List[str], fix: bool = False) -> Tuple[int, str]:
        """Run the linting tool on specified paths."""
        cmd = self.command + paths
        if fix and self.supports_fix():
            cmd = self.get_fix_command(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, f"Error: {self.name} not found. Please install it first."

    def supports_fix(self) -> bool:
        """Check if the tool supports automatic fixing."""
        return False

    def get_fix_command(self, paths: List[str]) -> List[str]:
        """Get the command for automatic fixing."""
        return self.command + paths


class BlackFormatter(LintingTool):
    """Black code formatter."""

    def __init__(self):
        super().__init__("black", ["black", "--line-length", "120"])

    def supports_fix(self) -> bool:
        return True

    def run(self, paths: List[str], fix: bool = False) -> Tuple[int, str]:
        cmd = self.command.copy()
        if not fix:
            cmd.append("--check")
            cmd.append("--diff")
        cmd.extend(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, f"Error: {self.name} not found. Please install it first."


class IsortFormatter(LintingTool):
    """isort import formatter."""

    def __init__(self):
        super().__init__("isort", ["isort"])

    def supports_fix(self) -> bool:
        return True

    def run(self, paths: List[str], fix: bool = False) -> Tuple[int, str]:
        cmd = self.command.copy()
        if not fix:
            cmd.extend(["--check-only", "--diff"])
        cmd.extend(paths)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            return result.returncode, result.stdout + result.stderr
        except FileNotFoundError:
            return 1, f"Error: {self.name} not found. Please install it first."


class PylintChecker(LintingTool):
    """Pylint code quality checker."""

    def __init__(self):
        super().__init__("pylint", ["pylint"])


class MypyChecker(LintingTool):
    """Mypy type checker."""

    def __init__(self):
        super().__init__("mypy", ["mypy"])


class CodeQualityRunner:
    """Main runner for all code quality tools."""

    def __init__(self):
        self.tools = {
            "black": BlackFormatter(),
            "isort": IsortFormatter(),
            "pylint": PylintChecker(),
            "mypy": MypyChecker(),
        }
        self.default_paths = ["src/", "tests/"]

    def run_tool(self, tool_name: str, paths: List[str], fix: bool = False) -> bool:
        """Run a specific tool."""
        if tool_name not in self.tools:
            print(f"Error: Unknown tool '{tool_name}'")
            return False

        tool = self.tools[tool_name]
        print(f"\n{'='*60}")
        print(f"Running {tool.name}...")
        print(f"{'='*60}")

        returncode, output = tool.run(paths, fix)

        if output.strip():
            print(output)

        if returncode == 0:
            print(f"✅ {tool.name} passed!")
            return True
        else:
            print(f"❌ {tool.name} failed!")
            return False

    def run_all(self, paths: List[str], fix: bool = False, skip_tools: Optional[List[str]] = None) -> bool:
        """Run all linting tools."""
        skip_tools = skip_tools or []
        success = True

        # Order matters: format first, then check
        tool_order = ["black", "isort", "pylint", "mypy"]

        for tool_name in tool_order:
            if tool_name in skip_tools:
                print(f"⏭️  Skipping {tool_name}")
                continue

            if not self.run_tool(tool_name, paths, fix):
                success = False

        return success

    def get_python_files(self, paths: List[str]) -> List[str]:
        """Get all Python files from the given paths."""
        python_files = []

        for path_str in paths:
            path = Path(path_str)
            if path.is_file() and path.suffix == ".py":
                python_files.append(str(path))
            elif path.is_dir():
                python_files.extend(
                    str(p)
                    for p in path.rglob("*.py")
                    if not any(part.startswith(".") for part in p.parts) and "/__pycache__/" not in str(p)
                )

        return python_files


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run code quality tools on Second Brain Database codebase")
    parser.add_argument("paths", nargs="*", help="Paths to check (default: src/ tests/)")
    parser.add_argument("--fix", action="store_true", help="Automatically fix issues where possible")
    parser.add_argument("--tool", choices=["black", "isort", "pylint", "mypy"], help="Run only a specific tool")
    parser.add_argument(
        "--skip", action="append", choices=["black", "isort", "pylint", "mypy"], help="Skip specific tools"
    )
    parser.add_argument("--files-only", action="store_true", help="Only process Python files (not directories)")

    args = parser.parse_args()

    runner = CodeQualityRunner()
    paths = args.paths or runner.default_paths

    # Filter to Python files if requested
    if args.files_only:
        paths = runner.get_python_files(paths)
        if not paths:
            print("No Python files found in specified paths.")
            return 1

    print(f"🔍 Running code quality checks on: {', '.join(paths)}")

    if args.tool:
        # Run single tool
        success = runner.run_tool(args.tool, paths, args.fix)
    else:
        # Run all tools
        success = runner.run_all(paths, args.fix, args.skip)

    if success:
        print(f"\n🎉 All checks passed!")
        return 0
    else:
        print(f"\n💥 Some checks failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
