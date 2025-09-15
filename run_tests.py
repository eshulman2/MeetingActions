#!/usr/bin/env python3
"""
Test runner script for the Agents project.

This script provides a convenient way to run different types of tests
with proper configuration and coverage reporting.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description="Running command"):
    """Run a shell command and return the result."""
    print(f"\n{description}...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.stdout:
        print("STDOUT:")
        print(result.stdout)

    if result.stderr:
        print("STDERR:")
        print(result.stderr)

    return result.returncode == 0, result


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description="Run tests for the Agents project")
    parser.add_argument(
        "--type",
        choices=["unit", "integration", "performance", "all"],
        default="unit",
        help="Type of tests to run (default: unit)",
    )
    parser.add_argument(
        "--coverage", action="store_true", help="Run with coverage reporting"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument(
        "--html-cov", action="store_true", help="Generate HTML coverage report"
    )
    parser.add_argument(
        "tests", nargs="*", help="Specific test files or patterns to run"
    )

    args = parser.parse_args()

    # Set up environment
    project_root = Path(__file__).parent
    os.chdir(project_root)

    # Build pytest command
    cmd = ["python", "-m", "pytest"]

    # Add test paths based on type
    if args.tests:
        cmd.extend(args.tests)
    elif args.type == "unit":
        cmd.append("tests/unit")
    elif args.type == "integration":
        cmd.append("tests/integration")
    elif args.type == "performance":
        cmd.append("tests/performance")
    else:  # args.type == "all"
        cmd.append("tests/")

    # Add coverage options
    if args.coverage:
        cmd.extend(
            ["--cov=src", "--cov-report=term-missing", "--cov-report=xml:coverage.xml"]
        )

        if args.html_cov:
            cmd.append("--cov-report=html:htmlcov")

    # Add verbosity
    if args.verbose:
        cmd.append("-v")

    # Add markers for filtering
    if args.fast:
        cmd.extend(["-m", "not slow"])

    # Add other useful options
    cmd.extend(["--tb=short", "--strict-markers", "--strict-config"])

    print("=" * 80)
    print(f"Running {args.type} tests for Agents project")
    print("=" * 80)

    # Run the tests
    success, _ = run_command(cmd, f"Running {args.type} tests")

    if success:
        print("\n" + "=" * 80)
        print("✅ All tests passed!")

        if args.coverage and args.html_cov:
            html_path = project_root / "htmlcov" / "index.html"
            if html_path.exists():
                print(f"📊 HTML coverage report available at: {html_path}")

        print("=" * 80)
        return 0

    print("\n" + "=" * 80)
    print("❌ Some tests failed!")
    print("=" * 80)
    return 1


if __name__ == "__main__":
    sys.exit(main())
