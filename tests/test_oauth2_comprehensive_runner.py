"""
Comprehensive test runner for OAuth2 browser authentication enterprise test suite.

This script orchestrates the execution of all OAuth2 browser authentication tests
and provides comprehensive reporting on test results, coverage, and system readiness.

Test Suite Components:
1. Unit tests for session management and authentication middleware
2. Integration tests for complete OAuth2 browser flows
3. Security penetration tests for vulnerability assessment
4. Browser automation tests for user experience validation
5. Load and performance tests for scalability validation
6. Regression tests for backward compatibility
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest


class TestSuiteRunner:
    """Comprehensive test suite runner for OAuth2 browser authentication."""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        self.test_files = [
            "tests/test_oauth2_comprehensive_enterprise_suite.py",
            "tests/test_oauth2_browser_automation.py",
            "tests/test_oauth2_security_penetration.py",
            "tests/test_oauth2_load_performance.py"
        ]
        self.report_file = "oauth2_test_report.json"
    
    def run_test_suite(self, test_categories: Optional[List[str]] = None) -> Dict:
        """Run the complete OAuth2 test suite."""
        print("🚀 Starting OAuth2 Browser Authentication Enterprise Test Suite")
        print("=" * 80)
        
        self.start_time = datetime.now()
        
        # Verify test environment
        self._verify_test_environment()
        
        # Run test categories
        if not test_categories:
            test_categories = [
                "unit_tests",
                "integration_tests", 
                "security_tests",
                "browser_tests",
                "performance_tests",
                "regression_tests"
            ]
        
        for category in test_categories:
            print(f"\n📋 Running {category.replace('_', ' ').title()}...")
            print("-" * 60)
            
            try:
                result = self._run_test_category(category)
                self.test_results[category] = result
                
                if result["success"]:
                    print(f"✅ {category} completed successfully")
                else:
                    print(f"❌ {category} failed with {result['failures']} failures")
                    
            except Exception as e:
                print(f"💥 {category} crashed: {str(e)}")
                self.test_results[category] = {
                    "success": False,
                    "error": str(e),
                    "duration": 0,
                    "tests_run": 0,
                    "failures": 1
                }
        
        self.end_time = datetime.now()
        
        # Generate comprehensive report
        report = self._generate_report()
        self._save_report(report)
        self._print_summary(report)
        
        return report
    
    def _verify_test_environment(self):
        """Verify test environment is properly configured."""
        print("🔍 Verifying test environment...")
        
        # Check Python version
        if sys.version_info < (3, 8):
            raise RuntimeError("Python 3.8+ required for OAuth2 tests")
        
        # Check required packages
        required_packages = [
            "pytest", "fastapi", "redis", "motor", "pydantic",
            "selenium", "psutil", "asyncio"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"⚠️  Missing packages: {', '.join(missing_packages)}")
            print("   Install with: pip install " + " ".join(missing_packages))
        
        # Check test files exist
        missing_files = []
        for test_file in self.test_files:
            if not Path(test_file).exists():
                missing_files.append(test_file)
        
        if missing_files:
            print(f"⚠️  Missing test files: {', '.join(missing_files)}")
        
        # Check OAuth2 components exist
        oauth2_components = [
            "src/second_brain_database/routes/oauth2/session_manager.py",
            "src/second_brain_database/routes/oauth2/auth_middleware.py",
            "src/second_brain_database/routes/auth/browser_auth.py"
        ]
        
        missing_components = []
        for component in oauth2_components:
            if not Path(component).exists():
                missing_components.append(component)
        
        if missing_components:
            print(f"⚠️  Missing OAuth2 components: {', '.join(missing_components)}")
        
        print("✅ Environment verification completed")
    
    def _run_test_category(self, category: str) -> Dict:
        """Run a specific test category."""
        start_time = time.time()
        
        # Map categories to test files and markers
        category_mapping = {
            "unit_tests": {
                "file": "tests/test_oauth2_comprehensive_enterprise_suite.py",
                "markers": "TestSessionManagement or TestFlexibleAuthMiddleware",
                "description": "Unit tests for core components"
            },
            "integration_tests": {
                "file": "tests/test_oauth2_comprehensive_enterprise_suite.py", 
                "markers": "TestBrowserOAuth2Integration",
                "description": "Integration tests for complete flows"
            },
            "security_tests": {
                "file": "tests/test_oauth2_security_penetration.py",
                "markers": "",
                "description": "Security penetration tests"
            },
            "browser_tests": {
                "file": "tests/test_oauth2_browser_automation.py",
                "markers": "",
                "description": "Browser automation tests"
            },
            "performance_tests": {
                "file": "tests/test_oauth2_load_performance.py",
                "markers": "",
                "description": "Load and performance tests"
            },
            "regression_tests": {
                "file": "tests/test_oauth2_comprehensive_enterprise_suite.py",
                "markers": "TestRegressionTesting",
                "description": "Regression tests for backward compatibility"
            }
        }
        
        if category not in category_mapping:
            raise ValueError(f"Unknown test category: {category}")
        
        config = category_mapping[category]
        
        # Build pytest command
        cmd = ["python", "-m", "pytest", config["file"], "-v", "--tb=short"]
        
        if config["markers"]:
            cmd.extend(["-k", config["markers"]])
        
        # Add category-specific options
        if category == "performance_tests":
            cmd.extend(["-s", "--disable-warnings"])
        elif category == "browser_tests":
            cmd.extend(["--disable-warnings"])
        elif category == "security_tests":
            cmd.extend(["--tb=line"])
        
        try:
            # Run pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout per category
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse pytest output
            output_lines = result.stdout.split('\n')
            
            # Extract test statistics
            tests_run = 0
            failures = 0
            errors = 0
            
            for line in output_lines:
                if "failed" in line and "passed" in line:
                    # Parse line like "5 failed, 10 passed in 2.34s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "failed,":
                            failures = int(parts[i-1])
                        elif part == "passed":
                            tests_run = int(parts[i-1]) + failures
                elif "passed in" in line and "failed" not in line:
                    # Parse line like "15 passed in 1.23s"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == "passed":
                            tests_run = int(parts[i-1])
            
            return {
                "success": result.returncode == 0,
                "duration": duration,
                "tests_run": tests_run,
                "failures": failures,
                "errors": errors,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "description": config["description"]
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "duration": 600,
                "tests_run": 0,
                "failures": 1,
                "errors": 0,
                "stdout": "",
                "stderr": "Test category timed out after 10 minutes",
                "description": config["description"]
            }
        except Exception as e:
            return {
                "success": False,
                "duration": time.time() - start_time,
                "tests_run": 0,
                "failures": 1,
                "errors": 0,
                "stdout": "",
                "stderr": str(e),
                "description": config["description"]
            }
    
    def _generate_report(self) -> Dict:
        """Generate comprehensive test report."""
        total_duration = (self.end_time - self.start_time).total_seconds()
        
        # Calculate overall statistics
        total_tests = sum(result.get("tests_run", 0) for result in self.test_results.values())
        total_failures = sum(result.get("failures", 0) for result in self.test_results.values())
        total_errors = sum(result.get("errors", 0) for result in self.test_results.values())
        
        successful_categories = sum(1 for result in self.test_results.values() if result.get("success", False))
        total_categories = len(self.test_results)
        
        # Calculate success rates
        overall_success_rate = (total_tests - total_failures - total_errors) / total_tests if total_tests > 0 else 0
        category_success_rate = successful_categories / total_categories if total_categories > 0 else 0
        
        # Determine system readiness
        system_ready = (
            overall_success_rate >= 0.95 and  # 95% test success rate
            category_success_rate >= 0.8 and  # 80% category success rate
            total_failures == 0  # No critical failures
        )
        
        report = {
            "test_run_info": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "total_duration": total_duration,
                "test_environment": {
                    "python_version": sys.version,
                    "platform": sys.platform,
                    "working_directory": os.getcwd()
                }
            },
            "overall_statistics": {
                "total_tests": total_tests,
                "total_failures": total_failures,
                "total_errors": total_errors,
                "successful_categories": successful_categories,
                "total_categories": total_categories,
                "overall_success_rate": overall_success_rate,
                "category_success_rate": category_success_rate
            },
            "category_results": self.test_results,
            "system_readiness": {
                "ready_for_production": system_ready,
                "readiness_score": (overall_success_rate + category_success_rate) / 2,
                "critical_issues": total_failures + total_errors,
                "recommendations": self._generate_recommendations()
            },
            "coverage_analysis": self._analyze_test_coverage(),
            "performance_metrics": self._extract_performance_metrics()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check for failed categories
        failed_categories = [cat for cat, result in self.test_results.items() if not result.get("success", False)]
        
        if "security_tests" in failed_categories:
            recommendations.append("🔒 Security tests failed - Review and fix security vulnerabilities before deployment")
        
        if "performance_tests" in failed_categories:
            recommendations.append("⚡ Performance tests failed - Optimize system performance and resource usage")
        
        if "browser_tests" in failed_categories:
            recommendations.append("🌐 Browser tests failed - Fix user experience issues and cross-browser compatibility")
        
        if "integration_tests" in failed_categories:
            recommendations.append("🔗 Integration tests failed - Fix OAuth2 flow integration issues")
        
        if "unit_tests" in failed_categories:
            recommendations.append("🧪 Unit tests failed - Fix core component functionality")
        
        if "regression_tests" in failed_categories:
            recommendations.append("🔄 Regression tests failed - Fix backward compatibility issues")
        
        # Check for performance issues
        perf_result = self.test_results.get("performance_tests", {})
        if perf_result.get("duration", 0) > 300:  # 5 minutes
            recommendations.append("🐌 Performance tests took too long - Consider optimizing test execution")
        
        # Check for browser test issues
        browser_result = self.test_results.get("browser_tests", {})
        if "selenium" in browser_result.get("stderr", "").lower():
            recommendations.append("🤖 Browser automation issues detected - Ensure WebDriver is properly configured")
        
        if not recommendations:
            recommendations.append("✅ All tests passed - System is ready for production deployment")
        
        return recommendations
    
    def _analyze_test_coverage(self) -> Dict:
        """Analyze test coverage across different areas."""
        coverage_areas = {
            "session_management": "unit_tests" in self.test_results,
            "authentication_middleware": "unit_tests" in self.test_results,
            "oauth2_flows": "integration_tests" in self.test_results,
            "security_vulnerabilities": "security_tests" in self.test_results,
            "user_experience": "browser_tests" in self.test_results,
            "performance_scalability": "performance_tests" in self.test_results,
            "backward_compatibility": "regression_tests" in self.test_results
        }
        
        covered_areas = sum(coverage_areas.values())
        total_areas = len(coverage_areas)
        coverage_percentage = covered_areas / total_areas * 100
        
        return {
            "coverage_areas": coverage_areas,
            "covered_areas": covered_areas,
            "total_areas": total_areas,
            "coverage_percentage": coverage_percentage,
            "missing_coverage": [area for area, covered in coverage_areas.items() if not covered]
        }
    
    def _extract_performance_metrics(self) -> Dict:
        """Extract performance metrics from test results."""
        perf_result = self.test_results.get("performance_tests", {})
        
        # Parse performance data from stdout if available
        stdout = perf_result.get("stdout", "")
        
        metrics = {
            "load_test_completed": "Load Test Results" in stdout,
            "response_time_measured": "Response Time" in stdout,
            "memory_usage_measured": "Memory Usage" in stdout,
            "cpu_usage_measured": "CPU Usage" in stdout,
            "throughput_measured": "req/s" in stdout,
            "performance_duration": perf_result.get("duration", 0)
        }
        
        return metrics
    
    def _save_report(self, report: Dict):
        """Save test report to file."""
        try:
            with open(self.report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            print(f"📄 Test report saved to {self.report_file}")
        except Exception as e:
            print(f"⚠️  Failed to save report: {e}")
    
    def _print_summary(self, report: Dict):
        """Print test summary to console."""
        print("\n" + "=" * 80)
        print("📊 OAUTH2 BROWSER AUTHENTICATION TEST SUITE SUMMARY")
        print("=" * 80)
        
        # Overall statistics
        stats = report["overall_statistics"]
        print(f"🧪 Total Tests Run: {stats['total_tests']}")
        print(f"✅ Success Rate: {stats['overall_success_rate']:.1%}")
        print(f"❌ Failures: {stats['total_failures']}")
        print(f"💥 Errors: {stats['total_errors']}")
        print(f"📋 Categories: {stats['successful_categories']}/{stats['total_categories']} successful")
        
        # Duration
        duration = report["test_run_info"]["total_duration"]
        print(f"⏱️  Total Duration: {duration:.1f} seconds")
        
        # System readiness
        readiness = report["system_readiness"]
        print(f"\n🎯 SYSTEM READINESS")
        print(f"Production Ready: {'✅ YES' if readiness['ready_for_production'] else '❌ NO'}")
        print(f"Readiness Score: {readiness['readiness_score']:.1%}")
        print(f"Critical Issues: {readiness['critical_issues']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS")
        for rec in readiness["recommendations"]:
            print(f"  {rec}")
        
        # Coverage
        coverage = report["coverage_analysis"]
        print(f"\n📈 TEST COVERAGE")
        print(f"Coverage: {coverage['coverage_percentage']:.1f}% ({coverage['covered_areas']}/{coverage['total_areas']} areas)")
        
        if coverage["missing_coverage"]:
            print(f"Missing: {', '.join(coverage['missing_coverage'])}")
        
        # Category details
        print(f"\n📋 CATEGORY DETAILS")
        for category, result in report["category_results"].items():
            status = "✅" if result.get("success", False) else "❌"
            duration = result.get("duration", 0)
            tests = result.get("tests_run", 0)
            failures = result.get("failures", 0)
            
            print(f"  {status} {category.replace('_', ' ').title()}: "
                  f"{tests} tests, {failures} failures, {duration:.1f}s")
        
        print("\n" + "=" * 80)
        
        if readiness["ready_for_production"]:
            print("🎉 CONGRATULATIONS! OAuth2 browser authentication system is ready for production!")
        else:
            print("⚠️  ATTENTION REQUIRED! Please address the issues above before production deployment.")
        
        print("=" * 80)


def main():
    """Main entry point for test suite runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="OAuth2 Browser Authentication Test Suite Runner")
    parser.add_argument("--categories", nargs="+", 
                       choices=["unit_tests", "integration_tests", "security_tests", 
                               "browser_tests", "performance_tests", "regression_tests"],
                       help="Specific test categories to run")
    parser.add_argument("--quick", action="store_true",
                       help="Run quick test suite (unit and integration tests only)")
    parser.add_argument("--security-only", action="store_true",
                       help="Run security tests only")
    parser.add_argument("--performance-only", action="store_true",
                       help="Run performance tests only")
    
    args = parser.parse_args()
    
    # Determine test categories to run
    categories = None
    if args.quick:
        categories = ["unit_tests", "integration_tests", "regression_tests"]
    elif args.security_only:
        categories = ["security_tests"]
    elif args.performance_only:
        categories = ["performance_tests"]
    elif args.categories:
        categories = args.categories
    
    # Run test suite
    runner = TestSuiteRunner()
    
    try:
        report = runner.run_test_suite(categories)
        
        # Exit with appropriate code
        if report["system_readiness"]["ready_for_production"]:
            sys.exit(0)  # Success
        else:
            sys.exit(1)  # Failure
            
    except KeyboardInterrupt:
        print("\n⚠️  Test suite interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()