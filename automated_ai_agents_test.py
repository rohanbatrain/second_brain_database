#!/usr/bin/env python3
"""
Automated AI Agents Test Runner

Command-line version of the AI agents testing suite for automated testing,
CI/CD integration, and batch testing scenarios.

Usage:
    python automated_ai_agents_test.py --agents family,personal --output results.json
    python automated_ai_agents_test.py --comprehensive --verbose
    python automated_ai_agents_test.py --agent commerce --scenario 0 --user regular
"""

import asyncio
import argparse
import json
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.abspath('.'))

try:
    from ai_agents_real_world_test import AIAgentTester, REAL_WORLD_SCENARIOS, TEST_USER_CONTEXTS
    from src.second_brain_database.managers.logging_manager import get_logger
except ImportError as e:
    print(f"❌ Failed to import required modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)

logger = get_logger(prefix="[AutomatedTest]")

class AutomatedTestRunner:
    """Command-line test runner for AI agents."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.tester = AIAgentTester()
        
    def log(self, message: str, level: str = "info"):
        """Log message with optional verbose output."""
        if level == "error":
            print(f"❌ {message}")
            logger.error(message)
        elif level == "warning":
            print(f"⚠️  {message}")
            logger.warning(message)
        elif level == "success":
            print(f"✅ {message}")
            logger.info(message)
        elif self.verbose:
            print(f"ℹ️  {message}")
            logger.info(message)
    
    async def run_single_scenario(
        self, 
        agent_type: str, 
        scenario_index: int, 
        user_context_name: str = "regular_user"
    ) -> dict:
        """Run a single scenario test."""
        if agent_type not in REAL_WORLD_SCENARIOS:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        scenarios = REAL_WORLD_SCENARIOS[agent_type]["scenarios"]
        if scenario_index >= len(scenarios):
            raise ValueError(f"Scenario index {scenario_index} out of range for agent {agent_type}")
        
        scenario = scenarios[scenario_index]
        user_context = TEST_USER_CONTEXTS[user_context_name]
        
        self.log(f"Running scenario: {agent_type} - {scenario['title']}")
        
        result = await self.tester.test_agent_scenario(agent_type, scenario, user_context)
        
        if result["success"]:
            self.log(f"Scenario completed successfully in {result['execution_time']:.2f}s", "success")
        else:
            self.log(f"Scenario failed: {', '.join(result['errors'])}", "error")
        
        return result
    
    async def run_agent_tests(
        self, 
        agent_types: list, 
        user_context_name: str = "regular_user"
    ) -> dict:
        """Run all scenarios for specified agents."""
        results = {
            "test_start": datetime.now(timezone.utc).isoformat(),
            "agents_tested": agent_types,
            "user_context": user_context_name,
            "agent_results": {},
            "summary": {
                "total_scenarios": 0,
                "successful_scenarios": 0,
                "failed_scenarios": 0,
                "total_execution_time": 0
            }
        }
        
        for agent_type in agent_types:
            if agent_type not in REAL_WORLD_SCENARIOS:
                self.log(f"Skipping unknown agent: {agent_type}", "warning")
                continue
            
            self.log(f"Testing agent: {REAL_WORLD_SCENARIOS[agent_type]['name']}")
            
            agent_results = {
                "agent_name": REAL_WORLD_SCENARIOS[agent_type]["name"],
                "scenarios": [],
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "execution_time": 0
                }
            }
            
            # Choose appropriate user context for agent
            if agent_type == "security":
                context_name = "admin_user"
            elif agent_type == "family":
                context_name = "family_member"
            else:
                context_name = user_context_name
            
            user_context = TEST_USER_CONTEXTS[context_name]
            
            scenarios = REAL_WORLD_SCENARIOS[agent_type]["scenarios"]
            for i, scenario in enumerate(scenarios):
                self.log(f"  Running scenario {i+1}/{len(scenarios)}: {scenario['title']}")
                
                try:
                    result = await self.tester.test_agent_scenario(agent_type, scenario, user_context)
                    
                    agent_results["scenarios"].append(result)
                    agent_results["summary"]["total"] += 1
                    agent_results["summary"]["execution_time"] += result["execution_time"]
                    
                    if result["success"]:
                        agent_results["summary"]["passed"] += 1
                        results["summary"]["successful_scenarios"] += 1
                        self.log(f"    ✅ Passed ({result['execution_time']:.2f}s)")
                    else:
                        agent_results["summary"]["failed"] += 1
                        results["summary"]["failed_scenarios"] += 1
                        self.log(f"    ❌ Failed: {', '.join(result['errors'])}")
                    
                    results["summary"]["total_scenarios"] += 1
                    results["summary"]["total_execution_time"] += result["execution_time"]
                    
                except Exception as e:
                    self.log(f"    ❌ Exception: {str(e)}", "error")
                    agent_results["summary"]["failed"] += 1
                    results["summary"]["failed_scenarios"] += 1
                    results["summary"]["total_scenarios"] += 1
            
            results["agent_results"][agent_type] = agent_results
            
            # Agent summary
            summary = agent_results["summary"]
            success_rate = (summary["passed"] / max(summary["total"], 1)) * 100
            self.log(f"Agent {agent_type} completed: {success_rate:.1f}% success rate "
                    f"({summary['passed']}/{summary['total']} scenarios)")
        
        results["test_end"] = datetime.now(timezone.utc).isoformat()
        
        # Overall summary
        overall_success_rate = (results["summary"]["successful_scenarios"] / 
                               max(results["summary"]["total_scenarios"], 1)) * 100
        
        self.log(f"\n📊 Test Summary:")
        self.log(f"   Total scenarios: {results['summary']['total_scenarios']}")
        self.log(f"   Successful: {results['summary']['successful_scenarios']}")
        self.log(f"   Failed: {results['summary']['failed_scenarios']}")
        self.log(f"   Success rate: {overall_success_rate:.1f}%")
        self.log(f"   Total time: {results['summary']['total_execution_time']:.2f}s")
        
        if overall_success_rate >= 95:
            self.log("🎉 Excellent! All agents performing well.", "success")
        elif overall_success_rate >= 80:
            self.log("👍 Good performance with some issues to address.", "warning")
        else:
            self.log("⚠️  Poor performance - significant issues detected.", "error")
        
        return results
    
    async def run_comprehensive_test(self) -> dict:
        """Run comprehensive test across all agents."""
        self.log("Starting comprehensive test of all AI agents...")
        
        all_agents = list(REAL_WORLD_SCENARIOS.keys())
        return await self.run_agent_tests(all_agents)
    
    def save_results(self, results: dict, output_file: str):
        """Save test results to file."""
        try:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(results, f, indent=2)
            
            self.log(f"Results saved to: {output_path.absolute()}", "success")
            
        except Exception as e:
            self.log(f"Failed to save results: {str(e)}", "error")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated AI Agents Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test specific agents
  python automated_ai_agents_test.py --agents family,personal
  
  # Run comprehensive test
  python automated_ai_agents_test.py --comprehensive
  
  # Test single scenario
  python automated_ai_agents_test.py --agent commerce --scenario 0
  
  # Save results to file
  python automated_ai_agents_test.py --agents family --output results.json
  
  # Verbose output
  python automated_ai_agents_test.py --comprehensive --verbose
        """
    )
    
    # Test mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--comprehensive", 
        action="store_true",
        help="Run comprehensive test across all agents"
    )
    mode_group.add_argument(
        "--agents",
        type=str,
        help="Comma-separated list of agents to test (family,personal,workspace,commerce,security,voice)"
    )
    mode_group.add_argument(
        "--agent",
        type=str,
        help="Single agent to test (use with --scenario)"
    )
    
    # Scenario selection
    parser.add_argument(
        "--scenario",
        type=int,
        help="Scenario index to test (use with --agent)"
    )
    
    # User context
    parser.add_argument(
        "--user",
        choices=["regular", "admin", "family"],
        default="regular",
        help="User context for testing (default: regular)"
    )
    
    # Output options
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file for test results (JSON format)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()

async def main():
    """Main function."""
    args = parse_arguments()
    
    # Map user context names
    user_context_map = {
        "regular": "regular_user",
        "admin": "admin_user", 
        "family": "family_member"
    }
    user_context_name = user_context_map[args.user]
    
    # Initialize test runner
    runner = AutomatedTestRunner(verbose=args.verbose)
    
    try:
        # Run tests based on mode
        if args.comprehensive:
            runner.log("🚀 Starting comprehensive AI agents test...")
            results = await runner.run_comprehensive_test()
            
        elif args.agents:
            agent_list = [agent.strip() for agent in args.agents.split(",")]
            runner.log(f"🚀 Testing selected agents: {', '.join(agent_list)}")
            results = await runner.run_agent_tests(agent_list, user_context_name)
            
        elif args.agent:
            if args.scenario is None:
                print("❌ --scenario is required when using --agent")
                sys.exit(1)
            
            runner.log(f"🚀 Testing single scenario: {args.agent} scenario {args.scenario}")
            results = await runner.run_single_scenario(args.agent, args.scenario, user_context_name)
            
        # Save results if requested
        if args.output:
            runner.save_results(results, args.output)
        
        # Exit with appropriate code
        if isinstance(results, dict):
            if "summary" in results:
                # Multi-scenario results
                success_rate = (results["summary"]["successful_scenarios"] / 
                               max(results["summary"]["total_scenarios"], 1)) * 100
                sys.exit(0 if success_rate >= 80 else 1)
            else:
                # Single scenario result
                sys.exit(0 if results.get("success", False) else 1)
        
    except KeyboardInterrupt:
        runner.log("Test interrupted by user", "warning")
        sys.exit(130)
    except Exception as e:
        runner.log(f"Test execution failed: {str(e)}", "error")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())